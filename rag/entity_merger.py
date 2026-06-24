"""Deduplicate and merge entity records that refer to the same thing."""
from __future__ import annotations
import json
import re
import anthropic
import config


_MERGE_PROMPT = """\
You are reviewing a list of entities extracted from a book. Some may refer to the same character, location, or object under different names, titles, or epithets.

Identify groups of entities that are the SAME thing. Only group entities if you are confident they refer to the same canonical entity — do not guess.

Return a JSON array of merge groups. Each group is a list of entity IDs that should be merged.
Only include groups with 2+ members. If nothing should be merged, return [].

ENTITY LIST:
{entity_list}

Return ONLY valid JSON, no prose, no markdown fences.
"""


def _candidate_pairs(entities: list[dict]) -> list[dict]:
    """Pre-filter to same-type entities that have name overlap or cross-references."""
    by_type: dict[str, list[dict]] = {}
    for e in entities:
        by_type.setdefault(e["type"], []).append(e)

    candidates = []
    for type_group in by_type.values():
        if len(type_group) < 2:
            continue
        # Build a simplified list for Claude to review
        for e in type_group:
            candidates.append({
                "id": e["id"],
                "name": e.get("name", e["id"]),
                "aliases": e.get("aliases", []),
                "description_snippet": e.get("canonical_description", "")[:120],
            })
    return candidates


def find_merge_groups(entities: list[dict]) -> list[list[str]]:
    """Ask Claude Haiku to identify entities that should be merged. Returns groups of IDs."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    candidates = _candidate_pairs(entities)

    # Process in batches of 80 to stay within context
    batch_size = 80
    all_groups: list[list[str]] = []

    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        entity_list = "\n".join(
            f"- id: {c['id']} | name: {c['name']} | aliases: {c['aliases']} | desc: {c['description_snippet']}"
            for c in batch
        )
        msg = client.messages.create(
            model=config.EXTRACTOR_MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": _MERGE_PROMPT.format(entity_list=entity_list)}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        try:
            groups = json.loads(raw)
            if isinstance(groups, list):
                all_groups.extend(g for g in groups if isinstance(g, list) and len(g) >= 2)
        except json.JSONDecodeError:
            pass

    return all_groups


def merge_entities(entities: list[dict], groups: list[list[str]]) -> list[dict]:
    """
    Merge entity groups into single canonical records.
    The entity with the most visual_notes becomes the primary; others are folded in.
    """
    # Build lookup
    by_id = {e["id"]: e for e in entities}

    # Track which IDs get absorbed
    absorbed: set[str] = set()

    for group in groups:
        # Filter to IDs that actually exist
        valid = [eid for eid in group if eid in by_id]
        if len(valid) < 2:
            continue

        # Pick primary: most visual notes, then longest description
        primary_id = max(valid, key=lambda eid: (
            len(by_id[eid].get("visual_notes", [])),
            len(by_id[eid].get("canonical_description", "")),
        ))
        others = [eid for eid in valid if eid != primary_id]

        primary = by_id[primary_id]

        # Merge aliases
        all_aliases = set(primary.get("aliases", []))
        all_aliases.add(primary.get("name", primary_id))
        for eid in others:
            other = by_id[eid]
            all_aliases.add(other.get("name", eid))
            all_aliases.update(other.get("aliases", []))
        all_aliases.discard(primary.get("name", primary_id))
        primary["aliases"] = sorted(all_aliases)

        # Merge visual notes (deduplicate)
        all_notes = list(primary.get("visual_notes", []))
        seen_notes = set(n.lower() for n in all_notes)
        for eid in others:
            for note in by_id[eid].get("visual_notes", []):
                if note.lower() not in seen_notes:
                    all_notes.append(note)
                    seen_notes.add(note.lower())
        primary["visual_notes"] = all_notes

        # Use highest appearance count
        primary["appearance_count"] = max(
            by_id[eid].get("appearance_count", 1) for eid in valid
        )

        # Use earliest first_appearance
        appearances = [by_id[eid].get("first_appearance", "") for eid in valid]
        primary["first_appearance"] = min(a for a in appearances if a) if any(appearances) else ""

        # Mark others as absorbed
        absorbed.update(others)
        print(f"  Merged {[by_id[eid].get('name', eid) for eid in others]} → {primary.get('name', primary_id)}")

    # Return entities minus absorbed ones
    return [e for e in entities if e["id"] not in absorbed]


def run_merge_pass(export_path: str = "horus_rising_entities.json") -> None:
    """Full merge pass: load entities, find groups, merge, update ChromaDB and export."""
    from rag.vector_store import get_entities_collection, reset_collections

    print("Loading entities…")
    data = json.loads(__import__("pathlib").Path(export_path).read_text())
    print(f"  {len(data)} entities loaded")

    print("Finding merge candidates (calling Claude Haiku)…")
    groups = find_merge_groups(data)
    print(f"  {len(groups)} merge group(s) found")

    if not groups:
        print("Nothing to merge.")
        return

    for g in groups:
        names = [data[next(i for i, e in enumerate(data) if e["id"] == eid)].get("name", eid)
                 if any(e["id"] == eid for e in data) else eid
                 for eid in g]
        print(f"  Group: {names}")

    merged = merge_entities(data, groups)
    print(f"  {len(data) - len(merged)} entities removed, {len(merged)} remain")

    # Rebuild ChromaDB
    print("Rebuilding entity collection…")
    reset_collections()
    col = get_entities_collection()
    ids, docs, metas = [], [], []
    for e in merged:
        ids.append(e["id"])
        docs.append(e["canonical_description"])
        metas.append({
            "name": e.get("name", e["id"]),
            "type": e.get("type", "unknown"),
            "faction": e.get("faction") or "",
            "first_appearance": e.get("first_appearance", ""),
            "appearance_count": e.get("appearance_count", 1),
            "last_updated_chapter": e.get("last_updated_chapter", ""),
            "aliases": json.dumps(e.get("aliases", [])),
            "visual_notes": json.dumps(e.get("visual_notes", [])),
            "conflicts": json.dumps(e.get("conflicts", [])),
        })
    for i in range(0, len(ids), 100):
        col.add(ids=ids[i:i+100], documents=docs[i:i+100], metadatas=metas[i:i+100])

    # Save updated export
    __import__("pathlib").Path(export_path).write_text(json.dumps(merged, indent=2))
    print(f"  Saved {len(merged)} merged entities to {export_path}")
    print("Merge pass complete.")
