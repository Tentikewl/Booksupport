import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Load .env if present
_env = BASE_DIR / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())
DATA_DIR = BASE_DIR / "data"
BOOKS_DIR = DATA_DIR / "books"
CHROMA_DIR = DATA_DIR / "chroma_db"
OUTPUT_DIR = DATA_DIR / "output"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")

# LLM models
CHUNKER_MODEL = "claude-haiku-4-5-20251001"
EXTRACTOR_MODEL = "claude-haiku-4-5-20251001"
SCENE_MODEL = "claude-haiku-4-5-20251001"

# Image generation
IMAGE_MODEL = "black-forest-labs/flux-schnell"
IMAGE_WIDTH = 1344
IMAGE_HEIGHT = 768

# Chunking
LUMBERCHUNKER_WINDOW_TOKENS = 550
CHILD_CHUNK_TOKENS = 150

# Scene beat settings
MIN_BEATS_PER_CHAPTER = 3
MAX_BEATS_PER_CHAPTER = 5
VISUAL_STRENGTH_THRESHOLD = 0.6

# Introduction illustrations
MAX_INTROS_PER_CHAPTER = 5
