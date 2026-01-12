from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
from datetime import datetime
from .storage import StorageManager

class ChunkerBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        pass

    @abstractmethod
    def chunk(self, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input: markdown_text, config
        Output: { "chunks": [{"id", "order", "content"}], "stats": {"num_chunks"} }
        """
        pass

class ChunkerManager:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.chunkers: Dict[str, ChunkerBase] = {}

    def register_chunker(self, chunker: ChunkerBase):
        self.chunkers[chunker.name] = chunker

    def run_chunking(self, category: str, doc_name: str, converted_filename: str, chunker_name: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        if chunker_name not in self.chunkers:
            return False, f"Chunker {chunker_name} not registered."
        
        chunker = self.chunkers[chunker_name]
        
        # Load converted MD
        converted_path = self.storage.get_document_dir(category, doc_name) / "converted" / converted_filename
        if not converted_path.exists():
            return False, f"Converted Markdown '{converted_filename}' not found."
        
        with open(converted_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Load metadata to get document_id
        metadata = self.storage.load_metadata(category, doc_name)
        doc_id = metadata["document_id"] if metadata else "unknown_id"

        # Run chunking
        result = chunker.chunk(text, config)
        
        # Format output content
        output_lines = []
        for chunk in result["chunks"]:
            # User request: format id as ID_DOKUMENTU:LP
            chunk_id = f"{doc_id}:{chunk['order']:03d}"
            chunk["id"] = chunk_id # Update in result for metadata consistency
            output_lines.append(f"<!-- chunk_id_start: {chunk_id} -->")
            output_lines.append(chunk["content"])
            output_lines.append(f"<!-- chunk_id_end: {chunk_id} -->")
            output_lines.append("")
        
        output_content = "\n".join(output_lines)
        
        # Save chunked file
        # User request: chunks should contain info about converter in name
        # converted_filename is expected to be: <doc_name>__<tool>__v<version>.md
        try:
            # Extract converter part: usually between the first and second double underscore or similar
            # A more robust way: split by "__"
            parts = converted_filename.replace(".md", "").split("__")
            converter_info = parts[1] if len(parts) > 1 else "unknown_conv"
        except Exception:
            converter_info = "unknown_conv"

        filename = f"{doc_name}__{converter_info}__{chunker.name}__v{chunker.version.replace('.', '_')}.md"
        chunked_dir = self.storage.get_document_dir(category, doc_name) / "chunked"
        output_path = chunked_dir / filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_content)

        if metadata:
            # Add/Update current run info
            new_entry = {
                "chunker": chunker.name,
                "chunker_version": chunker.version,
                "variant": config,
                "created_at": datetime.now().isoformat(),
                "num_chunks": result["stats"]["num_chunks"],
                "filename": filename
            }
            
            # Sync metadata with filesystem
            existing_files = {f.name for f in chunked_dir.glob("*.md")}
            
            # Keep only entries where file exists
            updated_chunking = [
                entry for entry in metadata.get("chunking", [])
                if entry.get("filename") in existing_files and entry.get("filename") != filename
            ]
            
            # Add new run
            updated_chunking.append(new_entry)
            metadata["chunking"] = updated_chunking
            self.storage.save_metadata(category, doc_name, metadata)

        return True, f"Successfully chunked using {chunker_name} -> {filename}"
