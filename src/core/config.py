from pathlib import Path

# UI Settings
CHUNK_HIGHLIGHT_COLOR = "#5AFF4B"

# Storage Settings
DATA_ROOT = Path("data")
ARCHIVE_ROOT = Path("archive")

# Ingestion Settings
DEFAULT_MAX_DOCS_PER_CATEGORY = 50
ALLOWED_EXTENSIONS = {'.pdf', '.docx'}

# Conversion Settings
DEFAULT_CONVERTER_VERSION = "1.0"

# Chunking Settings
DEFAULT_SENTENCES_PER_CHUNK = 8
DEFAULT_MIN_CHUNK_LENGTH = 400
DEFAULT_CHUNKER_VERSION = "1.0"
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200

# --- AI & RAG CORE SETTINGS ---

# LLM & Generation
DEFAULT_LLM_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_LLM_API_KEY = "not_applicable"
DEFAULT_LLM_MODEL = "bielik-4.5b-v3.0-instruct"
DEFAULT_TEMPERATURE = 0.2
AVAILABLE_LLM_MODELS = [
    "bielik-4.5b-v3.0-instruct",
    "mistralai/ministral-3-14b-reasoning",
    "gpt-oss-20b"
]

# Embedding & Search
DEFAULT_EMBEDDING_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_EMBEDDING_API_KEY = "not_applicable"
DEFAULT_EMBEDDING_MODEL = "text-embedding-embeddinggemma-300m-qat"
DEFAULT_SEMANTIC_THRESHOLD_PERCENTILE = 90
DEFAULT_CHAT_TOP_K = 5
DEFAULT_USE_MAGIC_REWRITE = False

# Reranker
DEFAULT_RERANKER_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_RERANKER_API_KEY = "not_applicable"
DEFAULT_RERANKER_MODEL = "gpt-oss-20b"
DEFAULT_USE_RERANKER = False
DEFAULT_RERANK_TOP_N = 3

# Cache & Quality
RAG_CACHE_DB = DATA_ROOT / "rag_cache.db"
CACHE_ENABLED = True
CACHE_SIMILARITY_THRESHOLD = 0.73  # How similar query must be to hit cache
DEFAULT_CACHE_MODE = "Only Positive" # Options: "Only Positive", "Positive > Negative"

# Enrichment (Internal)
DEFAULT_ENRICH_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_ENRICH_API_KEY = "not_applicable"
DEFAULT_ENRICH_MODEL = "bielik-4.5b-v3.0-instruct"
DEFAULT_ENRICH_MAX_CHARS = 180