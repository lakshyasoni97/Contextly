"""Central configuration loaded from .env"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- API ---
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

# --- Models ---
EMBEDDING_MODEL: str = "models/gemini-embedding-001"
LLM_MODEL: str = "models/gemini-flash-lite-latest"

# --- Paths ---
BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH: str = os.path.join(BASE_DIR, "chroma_db")
ICONS_DIR: str = os.path.join(BASE_DIR, "icons")
TAGS_PATH: str = os.path.join(BASE_DIR, "data", "tags.json")

# --- ChromaDB ---
COLLECTION_NAME: str = "lucide_icons"

# --- Search ---
TOP_K: int = 24              # max icons to return per query
EMBED_BATCH_SIZE: int = 50   # icons embedded per API call (free-tier safe)
MIN_TAGS: int = 3            # icons below this get LLM-generated tags
