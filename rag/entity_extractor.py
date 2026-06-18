"""Extract entities from narrative chunks and maintain a canonical RAG entity store."""
from __future__ import annotations
import json
import re
from typing import Any

import anthropic

import config
from rag.vector_store import get_entities_collection
from ingest.chunker import Chunk

_EXTRACTION_PROMPT = """\
You are an entity extraction assistant for narrative fiction.

Read the passage below and return a JSON array of entities found.

Each entity must have:
  "id"                  — snake_case unique identifier (e.g. "talos_valcoran")
  "type"                — one of: character | location | object | faction
  "name"                — display name
  "canonical_description" — rich visual description (physical appearance, clothing, features)
  "visual_notes"        — list of specific visual details or quirks (may be empty list)
  "aliases"             — list of alternate names / titles (may be empty list)
  "faction"             — faction or group (null if not applicable)
  "first_appearance"    — chapter_id provided below

Rules:
- Only extract entities that have meaningful visual descriptions or narrative importance.
- Do not duplicate entities already listed in KNOWN ENTITIES below.
- For entities in KNOWN ENTITIES, if the passage adds new visual detail, output them with type "update" and include only the new/changed fields plus the id.
- Return ONLY valid JSON — no prose, no markdown code fences.

CHAPTER: {chapter_id}
KNOWN ENTITIES: {known_ids}

PASSAGE:
{text}
"""


def _embed(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    resp = client.embeddings.create(model=config.EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in resp.data]


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=config.EXTRACTOR_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _parse_json_array(raw: str) -> list[dict]:
    raw = raw.strip()
    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return []
    except json.JSONDecodeError:
        return []


def extract_entities_from_chunk(chunk: Chunk) -> list[dict]:
    """Extract entities from a single chunk and upsert into the entity store."""
    col = get_entities_collection()

    # Fetch IDs already in store
    existing = col.get(include=[])
    known_ids: list[str] = existing["ids"] if existing["ids"] else []

    prompt = _EXTRACTION_PROMPT.format(
        chapter_id=chunk.chapter_id,
        known_ids=", ".join(known_ids) if known_ids else "none",
        text=chunk.text[:4000],  # cap to avoid huge prompts
    )

    raw = _call_claude(prompt)
    entities = _parse_json_array(raw)

    new_entities: list[dict] = []

    for entity in entities:
        if not entity.get("id") or not entity.get("type"):
            continue

        eid = entity["id"]
        etype = entity.get("type", "")

        if etype == "update":
            # Merge update into existing record
            _merge_entity(col, eid, entity, chunk.chapter_id)
        elif eid in known_ids:
            _merge_entity(col, eid, entity, chunk.chapter_id)
        else:
            # New entity
            entity.setdefault("aliases", [])
            entity.setdefault("visual_notes", [])
            entity.setdefault("faction", None)
            entity.setdefault("appearance_count", 1)
            entity.setdefault("last_updated_chapter", chunk.chapter_id)
            entity.setdefault("conflicts", [])
            entity["first_appearance"] = chunk.chapter_id

            description = entity.get("canonical_description", entity.get("name", eid))
            embedding = _embed([description])[0]

            col.add(
                ids=[eid],
                embeddings=[embedding],
                documents=[description],
                metadatas=[{
                    "name": entity.get("name", eid),
                    "type": entity.get("type", "unknown"),
                    "faction": entity.get("faction") or "",
                    "first_appearance": entity.get("first_appearance", ""),
                    "appearance_count": entity.get("appearance_count", 1),
                    "last_updated_chapter": chunk.chapter_id,
                    "aliases": json.dumps(entity.get("aliases", [])),
                    "visual_notes": json.dumps(entity.get("visual_notes", [])),
                    "conflicts": json.dumps([]),
                }],
            )
            new_entities.append(entity)
            known_ids.append(eid)

    return new_entities


def _merge_entity(col, eid: str, update: dict, chapter_id: str) -> None:
    """Merge new visual detail into an existing entity record."""
    result = col.get(ids=[eid], include=["metadatas", "documents"])
    if not result["ids"]:
        return

    meta = result["metadatas"][0]
    old_desc = result["documents"][0]

    new_desc = update.get("canonical_description")
    conflicts: list = json.loads(meta.get("conflicts", "[]"))

    if new_desc and new_desc != old_desc:
        conflicts.append({
            "chapter": chapter_id,
            "old": old_desc,
            "new": new_desc,
            "field": "canonical_description",
        })

    # Merge visual_notes
    old_notes: list = json.loads(meta.get("visual_notes", "[]"))
    new_notes: list = update.get("visual_notes", [])
    merged_notes = list(dict.fromkeys(old_notes + new_notes))

    # Update appearance count
    count = int(meta.get("appearance_count", 1)) + 1

    meta.update({
        "appearance_count": count,
        "last_updated_chapter": chapter_id,
        "visual_notes": json.dumps(merged_notes),
        "conflicts": json.dumps(conflicts),
    })

    final_desc = new_desc if new_desc else old_desc
    embedding = _embed([final_desc])[0]

    col.update(
        ids=[eid],
        embeddings=[embedding],
        documents=[final_desc],
        metadatas=[meta],
    )


def get_entity(eid: str) -> dict | None:
    col = get_entities_collection()
    result = col.get(ids=[eid], include=["metadatas", "documents"])
    if not result["ids"]:
        return None
    meta = result["metadatas"][0]
    return {
        "id": eid,
        "name": meta.get("name", eid),
        "type": meta.get("type", "unknown"),
        "canonical_description": result["documents"][0],
        "faction": meta.get("faction", ""),
        "first_appearance": meta.get("first_appearance", ""),
        "appearance_count": int(meta.get("appearance_count", 1)),
        "aliases": json.loads(meta.get("aliases", "[]")),
        "visual_notes": json.loads(meta.get("visual_notes", "[]")),
        "conflicts": json.loads(meta.get("conflicts", "[]")),
        "last_updated_chapter": meta.get("last_updated_chapter", ""),
    }


def get_all_entities() -> list[dict]:
    col = get_entities_collection()
    result = col.get(include=["metadatas", "documents"])
    entities = []
    for i, eid in enumerate(result["ids"]):
        meta = result["metadatas"][i]
        entities.append({
            "id": eid,
            "name": meta.get("name", eid),
            "type": meta.get("type", "unknown"),
            "canonical_description": result["documents"][i],
            "faction": meta.get("faction", ""),
            "first_appearance": meta.get("first_appearance", ""),
            "appearance_count": int(meta.get("appearance_count", 1)),
            "aliases": json.loads(meta.get("aliases", "[]")),
            "visual_notes": json.loads(meta.get("visual_notes", "[]")),
            "last_updated_chapter": meta.get("last_updated_chapter", ""),
        })
    return entities
