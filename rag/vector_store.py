"""ChromaDB wrapper — two-collection hierarchical store."""
from __future__ import annotations
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

import config


_client: chromadb.PersistentClient | None = None


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(config.CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_entities_collection() -> chromadb.Collection:
    return get_client().get_or_create_collection(
        name="entities",
        metadata={"hnsw:space": "cosine"},
    )


def get_passages_collection() -> chromadb.Collection:
    return get_client().get_or_create_collection(
        name="passages",
        metadata={"hnsw:space": "cosine"},
    )


def reset_collections() -> None:
    """Drop and recreate both collections (use for fresh ingest)."""
    client = get_client()
    for name in ("entities", "passages"):
        try:
            client.delete_collection(name)
        except Exception:
            pass
    global _client
    _client = None  # force reconnect so collections are recreated fresh
