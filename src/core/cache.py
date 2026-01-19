import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
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

    def check_cache(self, query: str, state_hash: str, filter_mode: str = "only_positive") -> Optional[Dict[str, Any]]:
        """Checks if a query exists for the given state, with filtered quality logic."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build SQL condition based on mode
        if filter_mode == "only_positive":
            condition = "coalesce(thumbs_up, 0) > 0 and coalesce(thumbs_down, 0) = 0"
        elif filter_mode == "pos_gt_neg":
            condition = "coalesce(thumbs_up, 0) > coalesce(thumbs_down, 0)"
        else:
            condition = "1=1" # No filter (return latest)

        cursor.execute(f'''
            SELECT id, answer, sources FROM rag_cache 
            WHERE query = ? AND state_hash = ? AND {condition}
            ORDER BY created_at DESC LIMIT 1
        ''', (query.strip(), state_hash))
        
        row = cursor.fetchone()
        
        if row:
            # Increment hit counter
            cursor.execute('UPDATE rag_cache SET hit_count = hit_count + 1 WHERE id = ?', (row["id"],))
            conn.commit()
            
            result = {
                "answer": row["answer"],
                "sources": json.loads(row["sources"])
            }
            conn.close()
            return result
        
        conn.close()
        return None

    def save_to_cache(self, query: str, answer: str, sources: List[Dict[str, Any]], state_hash: str, category: str, collection_name: str, prompt_content: str, model_name: str = ""):
        """Saves a new interaction to the cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO rag_cache (query, answer, sources, state_hash, category, collection_name, prompt_content, model_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (query.strip(), answer, json.dumps(sources), state_hash, category, collection_name, prompt_content, model_name))
        
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
