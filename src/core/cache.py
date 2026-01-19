import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import numpy as np
from .config import RAG_CACHE_DB

class RAGCache:
    def __init__(self, db_path: Path = RAG_CACHE_DB):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initializes the SQLite database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rag_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                answer TEXT NOT NULL,
                sources TEXT,
                state_hash TEXT NOT NULL,
                thumbs_up INTEGER DEFAULT 0,
                thumbs_down INTEGER DEFAULT 0,
                hit_count INTEGER DEFAULT 0,
                category TEXT,
                collection_name TEXT,
                prompt_content TEXT,
                model_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add migrations / Cleanup unused columns
        cursor.execute("PRAGMA table_info(rag_cache)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add new columns if they don't exist
        if 'thumbs_up' not in columns:
            cursor.execute('ALTER TABLE rag_cache ADD COLUMN thumbs_up INTEGER DEFAULT 0')
        if 'thumbs_down' not in columns:
            cursor.execute('ALTER TABLE rag_cache ADD COLUMN thumbs_down INTEGER DEFAULT 0')
        if 'hit_count' not in columns:
            cursor.execute('ALTER TABLE rag_cache ADD COLUMN hit_count INTEGER DEFAULT 0')
        if 'model_name' not in columns:
            cursor.execute('ALTER TABLE rag_cache ADD COLUMN model_name TEXT')
        if 'query_embedding' not in columns:
            cursor.execute('ALTER TABLE rag_cache ADD COLUMN query_embedding TEXT')
        if 'rewritten_query' not in columns:
            cursor.execute('ALTER TABLE rag_cache ADD COLUMN rewritten_query TEXT')
        if 'rerank_used' not in columns:
            cursor.execute('ALTER TABLE rag_cache ADD COLUMN rerank_used INTEGER DEFAULT 0')
        if 'plausible_sources' not in columns:
            cursor.execute('ALTER TABLE rag_cache ADD COLUMN plausible_sources TEXT')
        if 'rerank_prompt' not in columns:
            cursor.execute('ALTER TABLE rag_cache ADD COLUMN rerank_prompt TEXT')
        if 'rewrite_prompt' not in columns:
            cursor.execute('ALTER TABLE rag_cache ADD COLUMN rewrite_prompt TEXT')
            
        # Drop old unused columns if they exist
        for col_to_drop in ['feedback', 'rating_comment']:
            if col_to_drop in columns:
                try:
                    cursor.execute(f'ALTER TABLE rag_cache DROP COLUMN {col_to_drop}')
                except sqlite3.OperationalError:
                    pass
        
        # Index for faster lookup
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_state_query ON rag_cache (state_hash, query)')
        conn.commit()
        conn.close()

    def get_state_hash(self, category: str, collection_name: str, collection_metadata: Dict[str, Any], prompt_content: str) -> str:
        """Creates a unique hash representing the current 'knowledge state'."""
        state_data = {
            "category": category,
            "collection_name": collection_name,
            "num_chunks": collection_metadata.get("num_chunks", 0),
            "created_at": collection_metadata.get("created_at", ""),
            "prompt": prompt_content
        }
        state_str = json.dumps(state_data, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()

    def check_cache(self, query: str, state_hash: str, filter_mode: str = "only_positive", query_embedding: Optional[List[float]] = None, threshold: float = 0.95) -> Optional[Dict[str, Any]]:
        """Checks if a query exists for the given state, supporting semantic similarity."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. First try exact match (fast)
        if filter_mode == "only_positive":
            condition = "coalesce(thumbs_up, 0) > 0 and coalesce(thumbs_down, 0) = 0"
        elif filter_mode == "pos_gt_neg":
            condition = "coalesce(thumbs_up, 0) > coalesce(thumbs_down, 0)"
        else:
            condition = "1 = 1"

        cursor.execute(f'''
            SELECT id, query, answer, sources FROM rag_cache 
            WHERE query = ? AND state_hash = ? AND {condition}
            ORDER BY created_at DESC LIMIT 1
        ''', (query.strip(), state_hash))
        
        row = cursor.fetchone()
        if row:
            cursor.execute('UPDATE rag_cache SET hit_count = hit_count + 1 WHERE id = ?', (row["id"],))
            conn.commit()
            result = {
                "query": row["query"],
                "answer": row["answer"], 
                "sources": json.loads(row["sources"]),
                "similarity": 1.0
            }
            conn.close()
            return result

        # 2. Semantic Search fallback
        if query_embedding and threshold < 1.0:
            cursor.execute(f'''
                SELECT id, query, query_embedding, answer, sources FROM rag_cache 
                WHERE state_hash = ? AND {condition} AND query_embedding IS NOT NULL
            ''', (state_hash,))
            
            candidates = cursor.fetchall()
            best_match = None
            max_sim = -1.0
            
            vec_a = np.array(query_embedding)
            norm_a = np.linalg.norm(vec_a)
            
            for cand in candidates:
                try:
                    vec_b = np.array(json.loads(cand["query_embedding"]))
                    dot = np.dot(vec_a, vec_b)
                    norm_b = np.linalg.norm(vec_b)
                    similarity = dot / (norm_a * norm_b) if (norm_a * norm_b) > 0 else 0
                    
                    if similarity >= threshold and similarity > max_sim:
                        max_sim = similarity
                        best_match = cand
                except:
                    continue
            
            if best_match:
                cursor.execute('UPDATE rag_cache SET hit_count = hit_count + 1 WHERE id = ?', (best_match["id"],))
                conn.commit()
                result = {
                    "query": best_match["query"],
                    "answer": best_match["answer"],
                    "sources": json.loads(best_match["sources"]),
                    "similarity": float(max_sim)
                }
                conn.close()
                return result

        conn.close()
        return None

    def save_to_cache(self, query: str, answer: str, sources: List[Dict[str, Any]], state_hash: str, category: str, collection_name: str, prompt_content: str, model_name: str = "", query_embedding: Optional[List[float]] = None, rewritten_query: Optional[str] = None, rerank_used: bool = False, plausible_sources: Optional[List[Dict[str, Any]]] = None, rerank_prompt: Optional[str] = None, rewrite_prompt: Optional[str] = None):
        """Saves a new interaction to the cache with prompt metadata."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO rag_cache (
                query, answer, sources, state_hash, category, collection_name, 
                prompt_content, model_name, query_embedding, rewritten_query, 
                rerank_used, plausible_sources, rerank_prompt, rewrite_prompt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            query.strip(), 
            answer, 
            json.dumps(sources), 
            state_hash, 
            category, 
            collection_name, 
            prompt_content, 
            model_name, 
            json.dumps(query_embedding) if query_embedding else None,
            rewritten_query,
            1 if rerank_used else 0,
            json.dumps(plausible_sources) if plausible_sources else None,
            rerank_prompt,
            rewrite_prompt
        ))
        
        conn.commit()
        conn.close()

    def update_feedback(self, query: str, state_hash: str, feedback_type: str):
        """Increments thumbs_up or thumbs_down for the most recent entry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        column = "thumbs_up" if feedback_type == "up" else "thumbs_down"
        
        # Get the ID of the last entry for this query/state
        cursor.execute('''
            SELECT id FROM rag_cache 
            WHERE query = ? AND state_hash = ? 
            ORDER BY created_at DESC LIMIT 1
        ''', (query.strip(), state_hash))
        
        row = cursor.fetchone()
        if row:
            cursor.execute(f'UPDATE rag_cache SET {column} = {column} + 1 WHERE id = ?', (row[0],))
        
        conn.commit()
        conn.close()

    def list_cache(self, category: Optional[str] = None, collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns entries from the cache with optional filtering."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT * FROM rag_cache'
        params = []
        conditions = []
        
        if category:
            conditions.append('category = ?')
            params.append(category)
        if collection_name:
            conditions.append('collection_name = ?')
            params.append(collection_name)
            
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY created_at DESC'
        
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def delete_cache_entry(self, entry_id: int):
        """Deletes a specific entry from the cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM rag_cache WHERE id = ?', (entry_id,))
        conn.commit()
        conn.close()

    def purge_all(self):
        """Deletes all entries from the cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM rag_cache')
        conn.commit()
        conn.close()
