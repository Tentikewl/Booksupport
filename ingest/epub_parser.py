from __future__ import annotations
import re
from pathlib import Path


def parse_epub(path: Path) -> dict[str, str]:
    """Return {chapter_id: text} mapping from an epub file."""
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
    except ImportError as e:
        raise ImportError("pip install ebooklib beautifulsoup4") from e

    book = epub.read_epub(str(path))
    chapters: dict[str, str] = {}

    items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    for idx, item in enumerate(items):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n")
        text = _clean(text)
        if len(text.strip()) < 100:
            continue
        chapter_id = f"chapter_{idx + 1:02d}"
        chapters[chapter_id] = text

    return chapters


def parse_txt(path: Path) -> dict[str, str]:
    """Split a plain-text file into chapters by detecting headings."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = _clean(raw)

    # Try standard "Chapter X" / "PART X" markers first
    standard = re.compile(
        r"(?m)^(?:CHAPTER|Chapter|PART|Part)\s+(?:\d+|[IVXLC]+)[^\n]*$"
    )
    boundaries = [m.start() for m in standard.finditer(raw)]

    # Fall back to word-number chapter headings (e.g. Black Library novels:
    # "ONE", "TWO" … on a line by themselves, separated by prose).
    # Filter out TOC runs where two markers appear within 10 lines of each other.
    if not boundaries:
        boundaries = _find_wordnum_chapters(raw)

    if not boundaries:
        return {"chapter_01": raw}

    chapters: dict[str, str] = {}
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(raw)
        text = raw[start:end].strip()
        if len(text) > 200:  # skip near-empty sections
            chapters[f"chapter_{i + 1:02d}"] = text

    return chapters


_WORD_NUMS = {
    "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE",
    "TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN",
    "SEVENTEEN", "EIGHTEEN", "NINETEEN", "TWENTY",
}
_WORDNUM_RE = re.compile(r"(?m)^(" + "|".join(_WORD_NUMS) + r")$")


def _find_wordnum_chapters(raw: str) -> list[int]:
    """Find chapter boundaries marked by standalone word-numbers, skipping TOC runs."""
    lines = raw.split("\n")
    line_starts: list[int] = []  # char offset of each line start
    pos = 0
    for line in lines:
        line_starts.append(pos)
        pos += len(line) + 1  # +1 for \n

    candidates: list[tuple[int, int]] = []  # (line_index, char_offset)
    for i, line in enumerate(lines):
        if line.strip() in _WORD_NUMS:
            candidates.append((i, line_starts[i]))

    if not candidates:
        return []

    # Filter: keep only candidates that are NOT part of a TOC run.
    # A run = two candidates whose line indices are within 3 of each other.
    def in_run(idx: int) -> bool:
        for j, (li, _) in enumerate(candidates):
            if j == idx:
                continue
            if abs(li - candidates[idx][0]) <= 3:
                return True
        return False

    body_candidates = [
        char_off
        for idx, (_, char_off) in enumerate(candidates)
        if not in_run(idx)
    ]

    # Also skip anything before the first 500 chars (always front matter)
    body_candidates = [c for c in body_candidates if c > 500]

    return sorted(body_candidates)


def load_book(path: Path) -> dict[str, str]:
    suffix = path.suffix.lower()
    if suffix == ".epub":
        return parse_epub(path)
    elif suffix in (".txt", ".text"):
        return parse_txt(path)
    else:
        raise ValueError(f"Unsupported format: {suffix}. Use .epub or .txt")


def _clean(text: str) -> str:
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
