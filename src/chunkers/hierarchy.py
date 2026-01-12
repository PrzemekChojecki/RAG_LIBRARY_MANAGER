from typing import List, Dict, Any
import re
from ..core.chunker_manager import ChunkerBase
from ..core.config import DEFAULT_CHUNKER_VERSION

class HierarchyChunker(ChunkerBase):
    @property
    def name(self) -> str:
        return "hierarchy_v1"

    @property
    def version(self) -> str:
        return DEFAULT_CHUNKER_VERSION

    def chunk(self, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Chunks markdown text based on headers hierarchy.
        Configurable parameters:
        - max_chunk_size: int (default 2000) - split larger sections
        - include_path: bool (default True) - prepend header path to content
        """
        max_chunk_size = config.get("max_chunk_size", 2000)
        include_path = config.get("include_path", True)
        
        lines = text.split('\n')
        chunks = []
        
        # Stack to keep track of headers: [(level, text)]
        header_stack: List[tuple[int, str]] = []
        current_content: List[str] = []
        
        # Helper to flush current content
        def flush_chunk():
            if not current_content:
                return
            
            nonlocal chunks
            content_text = '\n'.join(current_content).strip()
            if not content_text:
                return

            # Construct path string
            path_str = " > ".join([h[1] for h in header_stack])
            
            # If content is too large, split by paragraphs
            if len(content_text) > max_chunk_size:
                sub_parts = content_text.split('\n\n')
                current_sub_chunk = []
                current_sub_len = 0
                
                for part in sub_parts:
                    part = part.strip()
                    if not part: continue
                    
                    # If adding this part exceeds max, flush sub chunk
                    if current_sub_len + len(part) > max_chunk_size and current_sub_chunk:
                        sub_content = "\n\n".join(current_sub_chunk)
                        full_content = f"Context: {path_str}\n\n{sub_content}" if include_path and path_str else sub_content
                        add_final_chunk(full_content)
                        current_sub_chunk = []
                        current_sub_len = 0
                    
                    current_sub_chunk.append(part)
                    current_sub_len += len(part)
                
                # Flush remaining sub chunk
                if current_sub_chunk:
                    sub_content = "\n\n".join(current_sub_chunk)
                    full_content = f"Context: {path_str}\n\n{sub_content}" if include_path and path_str else sub_content
                    add_final_chunk(full_content)
            else:
                # Normal chunk
                full_content = f"Context: {path_str}\n\n{content_text}" if include_path and path_str else content_text
                add_final_chunk(full_content)

        def add_final_chunk(content: str):
            order = len(chunks) + 1
            chunks.append({
                "id": f"chunk_{order:03d}",
                "order": order,
                "content": content
            })

        # Regex for markdown headers
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
        
        for line in lines:
            match = header_pattern.match(line)
            if match:
                # We found a header
                # 1. Flush whatever content we had before this header
                flush_chunk()
                current_content = []
                
                level = len(match.group(1))
                header_text = match.group(2).strip()
                
                # 2. Update stack
                # Remove headers of same or lower importance (higher level number = deeper)
                # Wait, standard markdown: # is H1 (level 1), ## is H2 (level 2).
                # If we are at level 2, and see a level 2, we pop the previous level 2.
                # If we are at level 2, and see a level 1, we pop everything back to level 0.
                while header_stack and header_stack[-1][0] >= level:
                    header_stack.pop()
                
                header_stack.append((level, header_text))
            else:
                current_content.append(line)
                
        # Flush last section
        flush_chunk()
        
        return {
            "chunks": chunks,
            "stats": {
                "num_chunks": len(chunks)
            }
        }
