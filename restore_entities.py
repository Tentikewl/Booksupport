"""Rebuild ChromaDB from committed JSON exports. Run this at the start of a new session."""
import json
from pathlib import Path


def restore_entities(json_path: str = "horus_rising_entities.json") -> None:
    from rag.vector_store import get_entities_collection, reset_collections

    data = json.loads(Path(json_path).read_text())
    print(f"Restoring {len(data)} entities…")

    reset_collections()
    col = get_entities_collection()

    ids, docs, metas = [], [], []
    for e in data:
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
        col.add(
            ids=ids[i:i+100],
            documents=docs[i:i+100],
            metadatas=metas[i:i+100],
        )
        print(f"  {min(i+100, len(ids))}/{len(ids)} entities…")

    print("Entity store ready.")


def restore_passages(json_path: str = "horus_rising_passages.json") -> None:
    from rag.vector_store import get_passages_collection

    data = json.loads(Path(json_path).read_text())
    print(f"Restoring {len(data)} passages…")

    col = get_passages_collection()

    ids, docs, metas = [], [], []
    for p in data:
        ids.append(p["id"])
        docs.append(p["text"])
        metas.append(p["metadata"])

    for i in range(0, len(ids), 100):
        col.add(
            ids=ids[i:i+100],
            documents=docs[i:i+100],
            metadatas=metas[i:i+100],
        )
        print(f"  {min(i+100, len(ids))}/{len(ids)} passages…")

    print("Passage store ready. Full RAG restored.")


if __name__ == "__main__":
    restore_entities()
    restore_passages()
