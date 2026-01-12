import re
from typing import List, Dict, Any
from ..core.chunker_manager import ChunkerBase

from ..core.config import DEFAULT_CHUNKER_VERSION, DEFAULT_SENTENCES_PER_CHUNK

class SentenceChunker(ChunkerBase):
    @property
    def name(self) -> str:
        return "sentence_v1"

    @property
    def version(self) -> str:
        return DEFAULT_CHUNKER_VERSION

    def chunk(self, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
        sentences_per_chunk = config.get("sentences_per_chunk", DEFAULT_SENTENCES_PER_CHUNK)
        
        # Simple sentence splitting logic (can be improved with NLTK/SpaCy)
        # For MVP: split by . ! ? followed by space or newline
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        for i in range(0, len(sentences), sentences_per_chunk):
            chunk_sentences = sentences[i : i + sentences_per_chunk]
            content = " ".join(chunk_sentences)
            order = (i // sentences_per_chunk) + 1
            chunks.append({
                "id": f"chunk_{order:03d}",
                "order": order,
                "content": content
            })
            
        return {
            "chunks": chunks,
            "stats": {
                "num_chunks": len(chunks)
            }
        }
