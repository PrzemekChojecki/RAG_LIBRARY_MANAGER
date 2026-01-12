import os
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
from datetime import datetime
from markitdown import MarkItDown
import pymupdf.layout
import pymupdf4llm
from .storage import StorageManager
from .config import DEFAULT_CONVERTER_VERSION

class ConverterManager:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.mid = MarkItDown()

    def convert_to_markdown(self, category: str, doc_name: str, tool: str = "markitdown") -> Tuple[bool, str]:
        # Get paths
        doc_dir = self.storage.get_document_dir(category, doc_name)
        original_dir = doc_dir / "original"
        converted_dir = doc_dir / "converted"
        
        # Find original file
        original_files = list(original_dir.glob("*"))
        if not original_files:
            return False, "Original file not found."
        
        original_path = original_files[0]
        tool_version = DEFAULT_CONVERTER_VERSION
        filename = f"{doc_name}__{tool}__v{tool_version.replace('.', '_')}.md"
        output_path = converted_dir / filename
        
        try:
            if tool == "markitdown":
                result = self.mid.convert(str(original_path))
                md_content = result.text_content
            elif tool == "pymupdf4llm":
                if original_path.suffix.lower() != ".pdf":
                    return False, "PyMuPDF4LLM only supports PDF files."
                md_content = pymupdf4llm.to_markdown(str(original_path))
            else:
                return False, f"Unknown conversion tool: {tool}"

            # Save Markdown
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            # Update Metadata
            metadata = self.storage.load_metadata(category, doc_name)
            if metadata:
                metadata["converted_at"] = datetime.now().isoformat()
                # Ensure conversion info reflects the selected tool
                metadata["conversion"] = {
                    "tool": tool,
                    "version": tool_version,
                    "filename": filename
                }
                # Also list available conversions if needed, but for now we keep the last one in metadata
                # matching the "only valid chunks" spirit for conversion as well?
                # User didn't explicitly say conversion metadata must be a list, 
                # but "tworzy nowy z dodatkiem" suggests we might have multiple.
                self.storage.save_metadata(category, doc_name, metadata)

            return True, f"Successfully converted using {tool} -> {filename}"

        except Exception as e:
            return False, f"Conversion failed: {str(e)}"
