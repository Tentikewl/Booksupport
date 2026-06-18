import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
BOOKS_DIR = DATA_DIR / "books"
CHROMA_DIR = DATA_DIR / "chroma_db"
OUTPUT_DIR = DATA_DIR / "output"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")

# LLM models
CHUNKER_MODEL = "claude-haiku-4-5-20251001"
EXTRACTOR_MODEL = "claude-sonnet-4-6"
SCENE_MODEL = "claude-sonnet-4-6"

# Embedding
EMBEDDING_MODEL = "text-embedding-3-small"

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
