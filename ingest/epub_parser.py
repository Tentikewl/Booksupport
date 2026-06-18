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

    # Split on common chapter markers
    pattern = re.compile(
        r"(?m)^(?:CHAPTER|Chapter|PART|Part)\s+(?:\d+|[IVXLC]+)[^\n]*$"
    )
    boundaries = [m.start() for m in pattern.finditer(raw)]

    if not boundaries:
        return {"chapter_01": raw}

    chapters: dict[str, str] = {}
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(raw)
        text = raw[start:end].strip()
        if text:
            chapters[f"chapter_{i + 1:02d}"] = text

    return chapters


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
