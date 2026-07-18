import hashlib
import sqlite3
import json
import os
from contextlib import closing
from typing import Any, Optional

class RuleCache:
    """
    Persistent L2 cache using SQLite to map query strings/hashes
    to parsed rule objects retrieved from Gaiia RAG-Doll.
    """
    def __init__(self, db_path: str = "state/cache/rule_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS rule_cache (
                        query_hash TEXT PRIMARY KEY,
                        query TEXT,
                        value_json TEXT,
                        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.encode("utf-8")).hexdigest()

    def get(self, query: str) -> Optional[Any]:
        qhash = self._hash_query(query)
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute("SELECT value_json FROM rule_cache WHERE query_hash = ?", (qhash,))
            row = cursor.fetchone()
            if row:
                with conn:
                    conn.execute("UPDATE rule_cache SET last_accessed = CURRENT_TIMESTAMP WHERE query_hash = ?", (qhash,))
                return json.loads(row[0])
        return None

    def set(self, query: str, value: Any):
        qhash = self._hash_query(query)
        value_json = json.dumps(value)
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO rule_cache (query_hash, query, value_json, last_accessed)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (qhash, query, value_json))

    def clear(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute("DELETE FROM rule_cache")

