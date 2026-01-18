import json
import httpx
from pathlib import Path
from openai import OpenAI
from typing import List, Dict, Any, Optional
from .vector_store import VectorStoreManager
from .cache import RAGCache
from .config import (
    DEFAULT_LLM_BASE_URL, 
    DEFAULT_LLM_API_KEY, 
    DEFAULT_LLM_MODEL,
    CACHE_ENABLED
)

class RAGManager:
    def __init__(self, vector_mgr: VectorStoreManager):
        self.vector_mgr = vector_mgr
        self.cache = RAGCache()
        self.llm_client = OpenAI(
            base_url=DEFAULT_LLM_BASE_URL,
            api_key=DEFAULT_LLM_API_KEY,
            http_client=httpx.Client(verify=False)
        )
        self.prompt_path = Path(__file__).parent.parent / "resources" / "prompts" / "rag_assistant.txt"
        # print(f"DEBUG: RAGManager initialized. Methods: {dir(self)}")

    def _get_collection_metadata(self, category: str, collection_name: str) -> Dict[str, Any]:
        """Loads metadata for a specific collection."""
        meta_path = self.vector_mgr.storage.root_path / category / "_vector_stores" / collection_name / "metadata.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _build_context_string(self, hits: List[Dict[str, Any]]) -> str:
        """Formats search results into a context string for the LLM."""
        context_parts = []
        for hit in hits:
            source_info = f"[ŹRÓDŁO: {hit.get('doc_name')} | ID: {hit.get('id')}]"
            content = hit.get('text', '')
            
            enrichment = ""
            if hit.get('summary'):
                enrichment += f"\nPodsumowanie fragmentu: {hit['summary']}"
            if hit.get('tags'):
                enrichment += f"\nTagi: {', '.join(hit['tags'])}"
            
            context_parts.append(f"{source_info}{enrichment}\nTreść: {content}")
        
        return "\n\n---\n\n".join(context_parts)

    def answer_question_stream(self, category: str, collection_name: str, query: str, top_k: int = 3, cache_filter_mode: str = "only_positive", model: str = DEFAULT_LLM_MODEL, temperature: float = 0.2, max_tokens: int = 1000):
        """Performs search and returns a generator for streaming the answer."""
        
        # 1. Load context state
        prompt_content = ""
        if self.prompt_path.exists():
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                prompt_content = f.read()
        
        col_metadata = self._get_collection_metadata(category, collection_name)
        # Note: we might want to include model/temp in state hash if we want separate cache for different settings
        state_hash = self.cache.get_state_hash(category, collection_name, col_metadata, prompt_content)
        
        # Yield state_hash first for UI feedback logic
        yield {"type": "state", "content": state_hash}

        # 2. Check Cache
        if CACHE_ENABLED:
            cached = self.cache.check_cache(query, state_hash, filter_mode=cache_filter_mode)
            if cached:
                formatted_answer = f"🎯 :green[[ODPOWIEDŹ Z BAZY]]\n\n{cached['answer']}"
                yield {"type": "answer", "content": formatted_answer}
                yield {"type": "sources", "content": cached["sources"]}
                return

        # 3. Search vector store
        hits = self.vector_mgr.search(category, collection_name, query, k=top_k)
        
        if not hits:
            yield {"type": "answer", "content": "Nie znaleziono żadnych istotnych fragmentów w wybranej kolekcji."}
            yield {"type": "sources", "content": []}
            return

        # 4. Build Context
        context_str = self._build_context_string(hits)
        
        # 5. Build Final Prompt
        prompt = prompt_content.replace("{{context}}", context_str)
        prompt = prompt.replace("{{query}}", query)

        try:
            # 6. Call LLM with streaming
            stream = self.llm_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            full_answer = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_answer += content
                    yield {"type": "answer", "content": content}
            
            # 7. Save to Cache
            if CACHE_ENABLED:
                self.cache.save_to_cache(query, full_answer, hits, state_hash, category, collection_name, prompt_content, model_name=model)

            # Send sources at the end
            yield {"type": "sources", "content": hits}

        except Exception as e:
            yield {"type": "answer", "content": f"\n\nBłąd podczas generowania odpowiedzi: {str(e)}"}
            yield {"type": "sources", "content": hits}
