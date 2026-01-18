from pathlib import Path

# UI Settings
CHUNK_HIGHLIGHT_COLOR = "#5AFF4B"

# Storage Settings
DATA_ROOT = Path("data")
ARCHIVE_ROOT = Path("archive")

# Ingestion Settings
DEFAULT_MAX_DOCS_PER_CATEGORY = 3
ALLOWED_EXTENSIONS = {'.pdf', '.docx'}

# Conversion Settings
DEFAULT_CONVERTER_VERSION = "1.0"

# Chunking Settings
DEFAULT_SENTENCES_PER_CHUNK = 8
DEFAULT_MIN_CHUNK_LENGTH = 400
DEFAULT_CHUNKER_VERSION = "1.0"
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200

# Embedding Settings
DEFAULT_EMBEDDING_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_EMBEDDING_API_KEY = "not_applicable"
DEFAULT_EMBEDDING_MODEL = "text-embedding-embeddinggemma-300m-qat"
DEFAULT_SEMANTIC_THRESHOLD_PERCENTILE = 90

DEFAULT_LLM_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_LLM_API_KEY = "not_applicable"
DEFAULT_LLM_MODEL = "bielik-4.5b-v3.0-instruct"

DEFAULT_ENRICH_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_ENRICH_API_KEY = "not_applicable"
DEFAULT_ENRICH_MODEL = "bielik-4.5b-v3.0-instruct"
DEFAULT_ENRICH_MAX_CHARS = 180

# RAG Cache & Quality Settings
RAG_CACHE_DB = DATA_ROOT / "rag_cache.db"
CACHE_SIMILARITY_THRESHOLD = 0.95  # How similar query must be to hit cache
CACHE_ENABLED = True