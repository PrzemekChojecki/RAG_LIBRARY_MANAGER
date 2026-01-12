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
