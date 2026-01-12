from typing import List, Dict, Any
import re
import numpy as np
from openai import OpenAI
from ..core.chunker_manager import ChunkerBase
from ..core.config import (
    DEFAULT_CHUNKER_VERSION, 
    DEFAULT_EMBEDDING_BASE_URL, 
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_SEMANTIC_THRESHOLD_PERCENTILE
)

class SemanticChunker(ChunkerBase):
    @property
    def name(self) -> str:
        return "semantic_v1"

    @property
    def version(self) -> str:
        return DEFAULT_CHUNKER_VERSION

    def chunk(self, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Chunks text based on semantic similarity of sentences.
        """
        base_url = config.get("base_url", DEFAULT_EMBEDDING_BASE_URL)
        model_name = config.get("model_name", DEFAULT_EMBEDDING_MODEL)
        threshold_percentile = config.get("threshold_percentile", DEFAULT_SEMANTIC_THRESHOLD_PERCENTILE)
        
        # 1. Split into sentences
        # Simple splitting - can be improved
        # Split by .!? followed by space/newline
        raw_sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [{'text': s.strip(), 'index': i} for i, s in enumerate(raw_sentences) if s.strip()]
        
        if not sentences:
             return {"chunks": [], "stats": {"num_chunks": 0}}
             
        if len(sentences) == 1:
            return {
                "chunks": [{
                    "id": "chunk_001",
                    "order": 1,
                    "content": sentences[0]['text']
                }],
                "stats": {"num_chunks": 1}
            }

        # 2. Get embeddings
        client = OpenAI(base_url=base_url, api_key="lm-studio") # dummy key for local
        
        try:
            # Batch sentences for embedding
            # Note: For very large docs, might need to chunk the embedding calls
            batch_size = 100
            all_embeddings = []
            
            texts_to_embed = [s['text'] for s in sentences]
            
            for i in range(0, len(texts_to_embed), batch_size):
                batch = texts_to_embed[i : i + batch_size]
                response = client.embeddings.create(input=batch, model=model_name)
                # Ensure ordered
                batch_embeddings = [d.embedding for d in response.data]
                all_embeddings.extend(batch_embeddings)
                
        except Exception as e:
            # Fallback or error
            # For now, return error chunk
            return {
                "chunks": [{
                    "id": "error", 
                    "order": 0, 
                    "content": f"Embedding Error: {str(e)}"
                }],
                "stats": {"num_chunks": 0}
            }

        # 3. Calculate Cosine Distances between adjacent sentences
        embeddings = np.array(all_embeddings)
        
        # Normalize embeddings to strict unit length for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms
        
        distances = []
        for i in range(len(embeddings) - 1):
            # Cosine similarity
            sim = np.dot(embeddings[i], embeddings[i+1])
            # Distance = 1 - similarity
            dist = 1 - sim
            distances.append(dist)
            
        # 4. Determine Threshold
        if not distances:
             # Should not happen if len > 1
             threshold = 0
        else:
            threshold = np.percentile(distances, threshold_percentile)
            
        # 5. Group sentences
        chunks = []
        current_chunk_sentences = [sentences[0]['text']]
        
        for i, dist in enumerate(distances):
            # dist corresponds to gap between sentence[i] and sentence[i+1]
            if dist > threshold:
                # Breakpoint found
                chunks.append(" ".join(current_chunk_sentences))
                current_chunk_sentences = [sentences[i+1]['text']]
            else:
                current_chunk_sentences.append(sentences[i+1]['text'])
                
        if current_chunk_sentences:
            chunks.append(" ".join(current_chunk_sentences))
            
        # 6. Format result
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
