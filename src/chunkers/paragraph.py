from typing import List, Dict, Any
from ..core.chunker_manager import ChunkerBase

from ..core.config import DEFAULT_CHUNKER_VERSION, DEFAULT_MIN_CHUNK_LENGTH

class ParagraphChunker(ChunkerBase):
    @property
    def name(self) -> str:
        return "paragraph_v1"

    @property
    def version(self) -> str:
        return DEFAULT_CHUNKER_VERSION

    def chunk(self, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
        min_length = config.get("min_length", DEFAULT_MIN_CHUNK_LENGTH)
        
        # Split by double newlines
        paragraphs = text.split("\n\n")
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        final_chunks = []
        current_chunk_content = []
        current_length = 0
        
        for p in paragraphs:
            current_chunk_content.append(p)
            current_length += len(p)
            
            # Logic: if current chunk is long enough, OR if it's not "short" by PRD rules
            # PRD: "if akapit < X znaków lub zawiera tylko 1 zdanie -> łącz z następnym"
            # Here we simplify: always merge until min_length is met
            if current_length >= min_length:
                order = len(final_chunks) + 1
                final_chunks.append({
                    "id": f"chunk_{order:03d}",
                    "order": order,
                    "content": "\n\n".join(current_chunk_content)
                })
                current_chunk_content = []
                current_length = 0
                
        # Handle remaining
        if current_chunk_content:
            order = len(final_chunks) + 1
            final_chunks.append({
                "id": f"chunk_{order:03d}",
                "order": order,
                "content": "\n\n".join(current_chunk_content)
            })
            
        return {
            "chunks": final_chunks,
            "stats": {
                "num_chunks": len(final_chunks)
            }
        }
