import faiss
import numpy as np
import json
import re
from pathlib import Path
from openai import OpenAI
import httpx
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from .config import (
    DATA_ROOT, 
    DEFAULT_EMBEDDING_BASE_URL, 
    DEFAULT_EMBEDDING_MODEL, 
    DEFAULT_EMBEDDING_API_KEY,
    DEFAULT_ENRICH_BASE_URL,
    DEFAULT_ENRICH_API_KEY,
    DEFAULT_ENRICH_MODEL,
    DEFAULT_ENRICH_MAX_CHARS
)
from .storage import StorageManager

class EnrichmentResponse(BaseModel):
    summary: str = Field(description=f"Merytoryczne podsumowanie fragmentu tekstu, maksymalnie {DEFAULT_ENRICH_MAX_CHARS} znaków")
    tags: List[str] = Field(description="Lista 2-3 tagów (słów kluczowych) opisujących tematykę fragmentu")

class VectorStoreManager:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        # Embeddings Client
        self.emb_client = OpenAI(
            base_url=DEFAULT_EMBEDDING_BASE_URL, 
            api_key=DEFAULT_EMBEDDING_API_KEY,
            http_client=httpx.Client(verify=False)
        )
        
        # Enrichment Client (Vanilla OpenAI)
        self.enrich_client = OpenAI(
            base_url=DEFAULT_ENRICH_BASE_URL,
            api_key=DEFAULT_ENRICH_API_KEY,
            http_client=httpx.Client(verify=False)
        )
        
        self.prompt_path = Path(__file__).parent.parent / "resources" / "prompts" / "enrich_chunk.txt"

    def _extract_chunks_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extracts chunks and their IDs from a markdown file."""
        chunks = []
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        pattern = r'<!-- chunk_id_start: (.*?) -->\n(.*?)\n<!-- chunk_id_end: \1 -->'
        matches = re.findall(pattern, content, re.DOTALL)

        for chunk_id, chunk_text in matches:
            chunks.append({
                "id": chunk_id,
                "text": chunk_text.strip(),
                "source_file": file_path.name
            })
        return chunks

    def _get_enrichment(self, text: str) -> Dict[str, Any]:
        """Calls LLM and validates output using Pydantic."""
        if not self.prompt_path.exists():
            return {"summary": "", "tags": []}
        
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
        
        prompt = prompt_template.replace("{{max_chars}}", str(DEFAULT_ENRICH_MAX_CHARS))
        prompt = prompt.replace("{{chunk_text}}", text)

        try:
            response = self.enrich_client.chat.completions.create(
                model=DEFAULT_ENRICH_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content
            
            # More aggressive regex-based JSON extraction
            # Look for the first '{' and the last '}'
            match = re.search(r'(\{.*\})', content, re.DOTALL)
            if match:
                content = match.group(1).strip()
            
            # Validate with Pydantic
            validated = EnrichmentResponse.model_validate_json(content)
            return validated.model_dump()
        except Exception as e:
            print(f"Enrichment error: {e}")
            return {"summary": "Error during enrichment", "tags": []}

    def create_collection(self, category: str, collection_name: str, chunk_files: List[Tuple[str, str]], model: str = DEFAULT_EMBEDDING_MODEL, enrich: bool = False, progress_callback: Optional[callable] = None) -> Tuple[bool, str]:
        """
        Creates a FAISS index for a set of chunk files in a category.
        chunk_files: List of (doc_name, chunk_filename)
        """
        all_chunks = []
        
        # Phase 1: Collect/Process Chunks
        total_chunks_to_process = 0
        if enrich:
            # First pass to count total chunks for progress bar
            for doc_name, chunk_filename in chunk_files:
                file_path = self.storage.get_document_dir(category, doc_name) / "chunked" / chunk_filename
                if file_path.exists():
                    all_chunks_temp = self._extract_chunks_from_file(file_path)
                    total_chunks_to_process += len(all_chunks_temp)
        
        chunks_processed_count = 0
        for doc_name, chunk_filename in chunk_files:
            file_path = self.storage.get_document_dir(category, doc_name) / "chunked" / chunk_filename
            if file_path.exists():
                file_chunks = self._extract_chunks_from_file(file_path)
                for c in file_chunks:
                    c["doc_name"] = doc_name
                    c["category"] = category
                    
                    if enrich:
                        enrichment = self._get_enrichment(c["text"])
                        c["summary"] = enrichment.get("summary", "")
                        c["tags"] = enrichment.get("tags", [])
                        
                        chunks_processed_count += 1
                        if progress_callback:
                            progress_callback(chunks_processed_count, total_chunks_to_process)
                
                all_chunks.extend(file_chunks)

        if not all_chunks:
            return False, "No chunks found in selected files."

        # Augmented text for indexing: Summary + Tags + Original Text
        # This significantly improves retrieval quality.
        texts_to_embed = []
        for c in all_chunks:
            augmented_parts = []
            if enrich:
                if c.get("summary"):
                    augmented_parts.append(f"Podsumowanie: {c['summary']}")
                if c.get("tags"):
                    augmented_parts.append(f"Tagi: {', '.join(c['tags'])}")
            
            augmented_parts.append(c["text"])
            texts_to_embed.append(" | ".join(augmented_parts))
        
        try:
            # Generate embeddings for the augmented texts
            response = self.emb_client.embeddings.create(input=texts_to_embed, model=model)
            embeddings = np.array([data.embedding for data in response.data]).astype('float32')

            # Create FAISS index
            dimension = embeddings.shape[1]
            index = faiss.IndexFlatL2(dimension)
            index.add(embeddings)

            # Save everything
            collection_dir = self.storage.root_path / category / "_vector_stores" / collection_name
            collection_dir.mkdir(parents=True, exist_ok=True)

            # Save index
            faiss.write_index(index, str(collection_dir / "index.faiss"))

            # Save metadata
            metadata = {
                "collection_name": collection_name,
                "category": category,
                "model": model,
                "created_at": datetime.now().isoformat(),
                "num_chunks": len(all_chunks),
                "chunks": all_chunks
            }
            with open(collection_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            return True, f"Successfully created collection '{collection_name}' with {len(all_chunks)} chunks."
        except Exception as e:
            return False, f"Error creating collection: {str(e)}"

    def search(self, category: str, collection_name: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Searches a specific collection for the most relevant chunks."""
        collection_dir = self.storage.root_path / category / "_vector_stores" / collection_name
        index_path = collection_dir / "index.faiss"
        meta_path = collection_dir / "metadata.json"

        if not index_path.exists() or not meta_path.exists():
            return []

        # Load index and metadata
        index = faiss.read_index(str(index_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Generate query embedding
        response = self.emb_client.embeddings.create(input=[query], model=metadata["model"])
        query_vector = np.array([response.data[0].embedding]).astype('float32')

        # Search index
        distances, indices = index.search(query_vector, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(metadata["chunks"]):
                chunk = metadata["chunks"][idx]
                chunk["score"] = float(dist)
                results.append(chunk)
        
        return results

    def list_collections(self, category: str) -> List[str]:
        vs_dir = self.storage.root_path / category / "_vector_stores"
        if not vs_dir.exists():
            return []
        return [d.name for d in vs_dir.iterdir() if d.is_dir()]

    def delete_collection(self, category: str, collection_name: str):
        import shutil
        collection_dir = self.storage.root_path / category / "_vector_stores" / collection_name
        if collection_dir.exists():
            shutil.rmtree(collection_dir)
