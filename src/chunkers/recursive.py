from typing import List, Dict, Any, Optional
import re
from ..core.chunker_manager import ChunkerBase
from ..core.config import DEFAULT_CHUNKER_VERSION, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP

class RecursiveChunker(ChunkerBase):
    @property
    def name(self) -> str:
        return "recursive_v1"

    @property
    def version(self) -> str:
        return DEFAULT_CHUNKER_VERSION

    def chunk(self, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively splits text by separators to keep chunks under a specific size.
        """
        chunk_size = config.get("chunk_size", DEFAULT_CHUNK_SIZE)
        chunk_overlap = config.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP)
        separators = config.get("separators", ["\n\n", "\n", " ", ""])
        
        # 1. Split text into atomic parts that are <= chunk_size (if possible)
        splits = self._split_text(text, separators, chunk_size)
        
        # 2. Merge parts into chunks with overlap
        chunks = self._merge_splits(splits, chunk_size, chunk_overlap, separator="")
        
        # 3. Format result
        final_chunks = []
        for i, content in enumerate(chunks):
            order = i + 1
            final_chunks.append({
                "id": f"chunk_{order:03d}",
                "order": order,
                "content": content
            })
            
        return {
            "chunks": final_chunks,
            "stats": {
                "num_chunks": len(final_chunks)
            }
        }

    def _split_text(self, text: str, separators: List[str], chunk_size: int) -> List[str]:
        """
        Recursively split text using the first valid separator.
        """
        final_chunks = []
        
        # Find the best separator (the one that appears and is highest priority)
        separator = separators[-1] # Default to last (usually empty string)
        new_separators = []
        
        for i, sep in enumerate(separators):
            if sep == "":
                separator = sep
                break
            # Use regex to check existence if needed, but strict string check is faster and usually sufficient
            # Note: LangChain uses regex escaping. We will assume simple string separators for now.
            if sep in text:
                separator = sep
                new_separators = separators[i+1:]
                break
                
        # Split
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text) # Character split if sep is empty string
            
        # Recover separator in splits to keep length accurate?
        # Standard approach: split loses the separator. 
        # But we might want to re-join later. 
        # Usually we don't keep the separator unless it's semantically meaningful like sentence end.
        # But for newlines, we often want to put them back or replace with space.
        # For simplicity here: we drop separator during split, but logic could be complex.
        # LangChain creates "splits" and then merges them using a separator.
        
        good_splits = []
        
        for split in splits:
            if len(split) < chunk_size:
                good_splits.append(split)
            else:
                if new_separators:
                    good_splits.extend(self._split_text(split, new_separators, chunk_size))
                else:
                    # No more separators, forced to take it (or hard chop)
                    # We'll validly assume we just take it if we ran out of separators
                    good_splits.append(split)
                    
        return good_splits

    def _merge_splits(self, splits: List[str], chunk_size: int, chunk_overlap: int, separator: str = " ") -> List[str]:
        """
        Merges small splits into chunks of max `chunk_size` with `chunk_overlap`.
        """
        chunks = []
        current_chunk = []
        current_len = 0
        
        for split in splits:
            # Calculate length if we add this split
            # We assume a separator (like space) is added between splits when merging
            # If default separator logic is complex, simplify to just adding length.
            # Here we assume joining with " " or "" depending on contexts, 
            # but usually for Markdown/Text " " is safe or implicit.
            # Let's assume input text had newlines, we split by them.
            # If we re-join without newlines, we lose structure.
            # Improved logic: _split_text should probably keep the separator attached to the chunk 
            # OR we just re-insert a generic separator. 
            # For this MVP: we will just use generic join separator "\n" if it looks like paragraph, " " otherwise.
            # Simpler: just use space for now or let the user choose. 
            # Actually, standard RCC often assumes " " join or keeps existing whitespace.
            # Let's stick to " " for join to be safe unless we track specific separators.
            
            len_split = len(split)
            
            if current_len + len_split + len(separator) > chunk_size:
                # Close current chunk
                if current_chunk:
                    text_content = separator.join(current_chunk)
                    chunks.append(text_content)
                    
                    # Logic for overlap:
                    # We need to keep some tail of current_chunk for the next chunk.
                    # We backtrack from the end of current_chunk until length is approx chunk_overlap
                    overlap_chunk = []
                    overlap_len = 0
                    
                    for s in reversed(current_chunk):
                        if overlap_len + len(s) < chunk_overlap:
                            overlap_chunk.insert(0, s)
                            overlap_len += len(s)
                        else:
                            break
                    
                    current_chunk = overlap_chunk
                    current_len = overlap_len
            
            current_chunk.append(split)
            current_len += len_split + len(separator)
            
        if current_chunk:
            chunks.append(separator.join(current_chunk))
            
        return chunks
