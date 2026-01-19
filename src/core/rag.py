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
    CACHE_ENABLED,
    DEFAULT_RERANKER_BASE_URL,
    DEFAULT_RERANKER_API_KEY,
    DEFAULT_RERANKER_MODEL,
    DEFAULT_RERANK_TOP_N
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

    def _rerank(self, query: str, hits: List[Dict[str, Any]], top_n: int = 3, custom_template: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Reranks the search results using the primary LLM as a bypass (when dedicated reranker is unavailable).
        """
        if not hits:
            return []
        
        try:
            if custom_template:
                template = custom_template
            else:
                rerank_prompt_path = Path(__file__).parent.parent / "resources" / "prompts" / "rerank_bypass.txt"
                if not rerank_prompt_path.exists():
                    return hits[:top_n]
                
                with open(rerank_prompt_path, "r", encoding="utf-8") as f:
                    template = f.read()
            
            # Prepare text for LLM evaluation
            docs_text = ""
            for i, h in enumerate(hits):
                docs_text += f"\n--- FRAGMENT [{i}] ---\n{h['text']}\n"
            
            prompt = template.replace("{{query}}", query)
            prompt = prompt.replace("{{documents}}", docs_text)
            prompt = prompt.replace("{{top_n}}", str(top_n))
            
            # Call LLM (synchronous for simplicity in this utility)
            response = self.llm_client.chat.completions.create(
                model=DEFAULT_LLM_MODEL,
                messages=[{"role": "system", "content": "Jesteś asystentem selekcjonującym najbardziej trafne fragmenty tekstu. Odpowiadasz tylko w formacie JSON."},
                          {"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "text"}
            )
            
            content = response.choices[0].message.content.strip()
            
            # Robust JSON extraction (in case LLM includes markdown blocks)
            if "```" in content:
                # Try to extract content between ```json and ``` or just ```
                import re
                json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
            
            result_json = json.loads(content)
            top_indices = result_json.get("top_indices", [])
            
            reranked_hits = []
            for idx in top_indices:
                if isinstance(idx, int) and idx < len(hits):
                    reranked_hits.append(hits[idx])
            
            # If LLM failed to return valid indices, fallback to original Top-N
            return reranked_hits if reranked_hits else hits[:top_n]
                
        except Exception as e:
            print(f"DEBUG: LLM Rerank Bypass error: {str(e)}")
            return hits[:top_n]

    def _rewrite_query(self, query: str, custom_template: Optional[str] = None) -> str:
        """Rewrites the user query to be more effective for RAG retrieval."""
        try:
            if custom_template:
                template = custom_template
            else:
                rewrite_prompt_path = Path(__file__).parent.parent / "resources" / "prompts" / "magic_rewrite.txt"
                if not rewrite_prompt_path.exists():
                    return query
                with open(rewrite_prompt_path, "r", encoding="utf-8") as f:
                    template = f.read()
            
            prompt = template.replace("{{query}}", query)
            
            response = self.llm_client.chat.completions.create(
                model=DEFAULT_LLM_MODEL,
                messages=[{"role": "system", "content": "Jesteś ekspertem od optymalizacji zapytań RAG. Odpowiadasz tylko poprawionym zapytaniem."},
                          {"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200
            )
            
            rewritten = response.choices[0].message.content.strip()
            # Remove quotes if LLM added them
            if rewritten.startswith('"') and rewritten.endswith('"'):
                rewritten = rewritten[1:-1]
            return rewritten if rewritten else query
            
        except Exception as e:
            print(f"DEBUG: Magic Rewrite error: {str(e)}")
            return query

    def answer_question_stream(self, category: str, collection_name: str, query: str, top_k: int = 3, cache_filter_mode: str = "only_positive", model: str = DEFAULT_LLM_MODEL, temperature: float = 0.2, max_tokens: int = 1000, custom_prompt: Optional[str] = None, use_reranker: bool = False, rerank_top_n: int = 3, custom_rerank_prompt: Optional[str] = None, cache_threshold: float = 0.95, use_cache: bool = True, use_magic_rewrite: bool = False, custom_rewrite_prompt: Optional[str] = None):
        """Performs search and returns a generator for streaming the answer."""
        
        # 1. Load context state
        prompt_content = ""
        if custom_prompt:
            prompt_content = custom_prompt
        elif self.prompt_path.exists():
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                prompt_content = f.read()
        
        col_metadata = self._get_collection_metadata(category, collection_name)
        # Note: we might want to include model/temp in state hash if we want separate cache for different settings
        state_hash = self.cache.get_state_hash(category, collection_name, col_metadata, prompt_content)
        
        # Yield state_hash first for UI feedback logic
        yield {"type": "state", "content": state_hash}

        # 2. Check Cache (ON ORIGINAL QUERY)
        query_emb = None
        original_query = query
        if CACHE_ENABLED:
            try:
                # Get current collection metadata to check which embedding model to use
                col_meta = self._get_collection_metadata(category, collection_name)
                emb_model = col_meta.get("model", "text-embedding-embeddinggemma-300m-qat")
                
                # Fetch query embedding for semantic cache (needed for both check and save)
                # We do this for the original query to maintain cache consistency
                emb_res = self.vector_mgr.emb_client.embeddings.create(input=[original_query], model=emb_model)
                query_emb = emb_res.data[0].embedding
                
                if use_cache:
                    cached = self.cache.check_cache(original_query, state_hash, filter_mode=cache_filter_mode, query_embedding=query_emb, threshold=cache_threshold)
                    if cached:
                        sim = cached.get('similarity', 1.0)
                        orig_q = cached.get('query', 'N/A')
                        formatted_answer = f"🎯 :green[**[ODPOWIEDŹ Z BAZY | Sim: {sim:.3f} | PYTANIE: {orig_q}]**]\n\n{cached['answer']}"
                        yield {"type": "answer", "content": formatted_answer}
                        yield {"type": "sources", "content": cached["sources"]}
                        return
            except Exception as e:
                print(f"DEBUG: Cache processing error: {e}")
                # Fallback to exact match if embedding fails (only if use_cache is enabled)
                if use_cache:
                    cached = self.cache.check_cache(original_query, state_hash, filter_mode=cache_filter_mode)
                    if cached:
                        orig_q = cached.get('query', 'N/A')
                        formatted_answer = f"🎯 :green[**[ODPOWIEDŹ Z BAZY (Exact) | PYTANIE: {orig_q}]**]\n\n{cached['answer']}"
                        yield {"type": "answer", "content": formatted_answer}
                        yield {"type": "sources", "content": cached["sources"]}
                        return

        # 3. Magic Rewrite if enabled (ONLY ON CACHE MISS)
        rewrite_template = None
        if use_magic_rewrite:
            # Resolve rewrite template
            if custom_rewrite_prompt:
                rewrite_template = custom_rewrite_prompt
            else:
                rewrite_prompt_path = Path(__file__).parent.parent / "resources" / "prompts" / "magic_rewrite.txt"
                if rewrite_prompt_path.exists():
                    with open(rewrite_prompt_path, "r", encoding="utf-8") as f:
                        rewrite_template = f.read()
            
            query = self._rewrite_query(query, custom_template=rewrite_template)
            yield {"type": "rewritten_query", "content": query}

        # 4. Search vector store
        hits = self.vector_mgr.search(category, collection_name, query, k=top_k)
        
        plausible_hits = []
        if not hits:
            yield {"type": "answer", "content": "Nie znaleziono żadnych istotnych fragmentów w wybranej kolekcji."}
            yield {"type": "sources", "content": []}
            return

        # 3.5 Optional Reranking
        plausible_hits = []
        if use_reranker:
            plausible_hits = hits.copy()
            yield {"type": "plausible_sources", "content": plausible_hits}
            hits = self._rerank(query, hits, top_n=rerank_top_n, custom_template=custom_rerank_prompt)

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
                # Determine if query was actually rewritten
                rewritten = query if query != original_query else None
                
                # Resolve rerank template if used
                rerank_template = None
                if use_reranker:
                    if custom_rerank_prompt:
                        rerank_template = custom_rerank_prompt
                    else:
                        rerank_prompt_path = Path(__file__).parent.parent / "resources" / "prompts" / "rerank_bypass.txt"
                        if rerank_prompt_path.exists():
                            with open(rerank_prompt_path, "r", encoding="utf-8") as f:
                                rerank_template = f.read()

                # We save the original user query to the cache, so semantic lookup works next time
                self.cache.save_to_cache(
                    original_query, 
                    full_answer, 
                    hits, 
                    state_hash, 
                    category, 
                    collection_name, 
                    prompt_content, 
                    model_name=model, 
                    query_embedding=query_emb,
                    rewritten_query=rewritten,
                    rerank_used=use_reranker,
                    plausible_sources=plausible_hits if use_reranker else None,
                    rerank_prompt=rerank_template,
                    rewrite_prompt=rewrite_template
                )

            # Send sources at the end
            yield {"type": "sources", "content": hits}
            if plausible_hits:
                yield {"type": "plausible_sources", "content": plausible_hits}

        except Exception as e:
            yield {"type": "answer", "content": f"\n\nBłąd podczas generowania odpowiedzi: {str(e)}"}
            yield {"type": "sources", "content": hits}
