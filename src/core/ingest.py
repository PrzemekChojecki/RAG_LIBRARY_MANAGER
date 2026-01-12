import streamlit as st
from pathlib import Path
from typing import Tuple, Optional
import uuid
from datetime import datetime
from .storage import StorageManager
from .config import DEFAULT_MAX_DOCS_PER_CATEGORY, ALLOWED_EXTENSIONS

class IngestManager:
    def __init__(self, storage: StorageManager):
        self.storage = storage

    def validate_file(self, filename: str, file_size_bytes: int, category: str) -> Tuple[bool, str]:
        # Extension check
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported file extension: {ext}. Only PDF and DOCX are allowed."

        # Size check - parameterised via streamlit config
        max_file_size_mb = st.config.get_option("server.maxUploadSize")
        size_mb = file_size_bytes / (1024 * 1024)
        if size_mb > max_file_size_mb:
            return False, f"File size ({size_mb:.2f} MB) exceeds limit of {max_file_size_mb} MB."

        # Category limit check
        existing_docs = self.storage.list_documents(category)
        if len(existing_docs) >= DEFAULT_MAX_DOCS_PER_CATEGORY:
            return False, f"Category '{category}' has reached the limit of {DEFAULT_MAX_DOCS_PER_CATEGORY} documents."

        # Unique name check
        doc_name = Path(filename).stem
        if doc_name in existing_docs:
            return False, f"Document '{doc_name}' already exists in category '{category}'."

        return True, ""

    def process_upload(self, category: str, filename: str, file_content: bytes) -> Tuple[bool, str]:
        doc_name = Path(filename).stem
        
        # Check if exists first to inform user
        existing_docs = self.storage.list_documents(category)
        if doc_name in existing_docs:
            return False, f"EXISTS:{doc_name}" # Special flag to handle in UI

        is_valid, error_msg = self.validate_file(filename, len(file_content), category)
        if not is_valid:
            return False, error_msg

        return self._ingest(category, filename, file_content)

    def _ingest(self, category: str, filename: str, file_content: bytes) -> Tuple[bool, str]:
        doc_name = Path(filename).stem
        # Ensure directory structure
        paths = self.storage.ensure_document_structure(category, doc_name)
        
        # Save original file
        original_path = paths["original"] / filename
        with open(original_path, "wb") as f:
            f.write(file_content)

        # Initialize metadata
        metadata = {
            "document_id": str(uuid.uuid4()),
            "original_filename": filename,
            "file_size_mb": round(len(file_content) / (1024 * 1024), 2),
            "created_at": datetime.now().isoformat(),
            "converted_at": None,
            "conversion": None,
            "chunking": []
        }
        self.storage.save_metadata(category, doc_name, metadata)

        return True, f"Successfully uploaded {filename} to {category}/{doc_name}"

    def update_document(self, category: str, filename: str, file_content: bytes, target_doc_name: Optional[str] = None) -> Tuple[bool, str]:
        # If target_doc_name is not provided, we assume it's based on the new filename
        doc_to_archive = target_doc_name if target_doc_name else Path(filename).stem
        
        # 1. Archive
        archive_name = self.storage.archive_document(category, doc_to_archive)
        if not archive_name:
            return False, f"Failed to archive existing document '{doc_to_archive}'."
        
        # 2. Delete existing
        self.storage.delete_document(category, doc_to_archive)
        
        # 3. Fresh ingest (this will use the NEW filename for the new structure)
        success, msg = self._ingest(category, filename, file_content)
        if success:
            return True, f"Document updated. Previous version '{doc_to_archive}' archived as {archive_name}"
        return False, msg
