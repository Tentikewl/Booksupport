"""Split parent chunks into child passages, embed, and index with entity metadata."""
from __future__ import annotations
import json
import re

import config
from ingest.chunker import Chunk, _count_tokens
from rag.vector_store import get_passages_collection


def _split_child_chunks(chunk: Chunk, target_tokens: int = config.CHILD_CHUNK_TOKENS) -> list[dict]:
    """Split a parent chunk into ~150-token child passages."""
    paragraphs = chunk.paragraphs if chunk.paragraphs else re.split(r"\n{2,}", chunk.text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    children: list[dict] = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        pt = _count_tokens(para)
        if current_tokens + pt > target_tokens and current:
            children.append("\n\n".join(current))
            current = [para]
            current_tokens = pt
        else:
            current.append(para)
            current_tokens += pt

    if current:
        children.append("\n\n".join(current))

    return children


def index_chunk(chunk: Chunk, entity_ids_present: list[str]) -> int:
    """Index child passages from a parent chunk. Returns number of passages added."""
    col = get_passages_collection()
    children = _split_child_chunks(chunk)

    if not children:
        return 0

    ids = []
    metas = []

    for i, text in enumerate(children):
        ids.append(f"{chunk.chunk_id}_child_{i:03d}")
        metas.append({
            "parent_chunk_id": chunk.chunk_id,
            "chapter": chunk.chapter_id,
            "entities_present": json.dumps(entity_ids_present),
            "chunk_position": chunk.position + (i / max(len(children), 1)) * 0.01,
        })

    col.add(ids=ids, documents=children, metadatas=metas)
    return len(ids)


def query_passages(
    query_text: str,
    chapter: str | None = None,
    n_results: int = 5,
) -> list[dict]:
    """Query child passages; returns list of {text, metadata} dicts."""
    col = get_passages_collection()

    where: dict | None = None
    if chapter:
        where = {"chapter": chapter}

    results = col.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    passages = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        entity_ids = json.loads(meta.get("entities_present", "[]"))
        passages.append({
            "text": doc,
            "parent_chunk_id": meta.get("parent_chunk_id", ""),
            "chapter": meta.get("chapter", ""),
            "entity_ids": entity_ids,
            "position": meta.get("chunk_position", 0.0),
            "distance": dist,
        })

    return passages
