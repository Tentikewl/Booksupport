"""LumberChunker — narrative-aware segmentation using Claude."""
from __future__ import annotations
import re
from dataclasses import dataclass, field

import anthropic

import config


@dataclass
class Chunk:
    chunk_id: str
    chapter_id: str
    text: str
    position: float = 0.0  # fractional position through chapter (0.0–1.0)
    paragraphs: list[str] = field(default_factory=list)


def _count_tokens(text: str) -> int:
    # Rough approximation: 1 token ≈ 4 characters
    return len(text) // 4


def _split_paragraphs(text: str) -> list[str]:
    paras = re.split(r"\n{2,}", text)
    return [p.strip() for p in paras if p.strip()]


def _find_shift_point(group: list[str], client: anthropic.Anthropic) -> int:
    """Ask Claude Haiku where the content meaningfully shifts in this paragraph group."""
    numbered = "\n\n".join(f"[{i}] {p}" for i, p in enumerate(group))
    prompt = (
        "You are analysing a passage from a novel. "
        "Below are numbered paragraphs. "
        "Identify the paragraph index where the content meaningfully shifts "
        "(new scene, POV change, location change, time skip). "
        "Reply with ONLY the integer index. If there is no clear shift, reply 0.\n\n"
        f"{numbered}"
    )

    message = client.messages.create(
        model=config.CHUNKER_MODEL,
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    try:
        idx = int(re.search(r"\d+", raw).group())
        return max(0, min(idx, len(group) - 1))
    except (AttributeError, ValueError):
        return 0


def lumberchunk(
    chapter_text: str,
    chapter_id: str,
    window_tokens: int = config.LUMBERCHUNKER_WINDOW_TOKENS,
) -> list[Chunk]:
    """Segment a chapter into narrative-coherent chunks."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    paragraphs = _split_paragraphs(chapter_text)
    total_paragraphs = len(paragraphs)

    chunks: list[Chunk] = []
    group: list[str] = []
    group_tokens = 0
    consumed = 0  # paragraphs committed to finished chunks

    for para in paragraphs:
        para_tokens = _count_tokens(para)

        if group_tokens + para_tokens > window_tokens and group:
            shift_idx = _find_shift_point(group, client)

            if shift_idx == 0:
                # No clear shift — commit entire group as one chunk
                shift_idx = len(group)

            chunk_text = "\n\n".join(group[:shift_idx])
            if chunk_text.strip():
                pos = consumed / max(total_paragraphs, 1)
                chunk_id = f"{chapter_id}_seg_{len(chunks) + 1:03d}"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        chapter_id=chapter_id,
                        text=chunk_text,
                        position=pos,
                        paragraphs=group[:shift_idx],
                    )
                )
            consumed += shift_idx
            group = group[shift_idx:] + [para]
            group_tokens = sum(_count_tokens(p) for p in group)
        else:
            group.append(para)
            group_tokens += para_tokens

    if group:
        chunk_text = "\n\n".join(group)
        if chunk_text.strip():
            pos = consumed / max(total_paragraphs, 1)
            chunk_id = f"{chapter_id}_seg_{len(chunks) + 1:03d}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    chapter_id=chapter_id,
                    text=chunk_text,
                    position=pos,
                    paragraphs=group,
                )
            )

    return chunks


def fallback_chunk(
    chapter_text: str,
    chapter_id: str,
    target_tokens: int = 450,
    overlap_tokens: int = 68,
) -> list[Chunk]:
    """Simple recursive splitter fallback when LumberChunker is too expensive."""
    paragraphs = _split_paragraphs(chapter_text)
    chunks: list[Chunk] = []
    current: list[str] = []
    current_tokens = 0
    total = len(paragraphs)

    for i, para in enumerate(paragraphs):
        pt = _count_tokens(para)
        if current_tokens + pt > target_tokens and current:
            text = "\n\n".join(current)
            chunks.append(
                Chunk(
                    chunk_id=f"{chapter_id}_seg_{len(chunks) + 1:03d}",
                    chapter_id=chapter_id,
                    text=text,
                    position=(i - len(current)) / max(total, 1),
                    paragraphs=list(current),
                )
            )
            # keep overlap
            overlap: list[str] = []
            overlap_t = 0
            for p in reversed(current):
                if overlap_t + _count_tokens(p) > overlap_tokens:
                    break
                overlap.insert(0, p)
                overlap_t += _count_tokens(p)
            current = overlap + [para]
            current_tokens = sum(_count_tokens(p) for p in current)
        else:
            current.append(para)
            current_tokens += pt

    if current:
        chunks.append(
            Chunk(
                chunk_id=f"{chapter_id}_seg_{len(chunks) + 1:03d}",
                chapter_id=chapter_id,
                text="\n\n".join(current),
                position=(total - len(current)) / max(total, 1),
                paragraphs=list(current),
            )
        )

    return chunks
