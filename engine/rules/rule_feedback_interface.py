import sqlite3
import json
import hashlib
from typing import List, Dict, Any, Optional

class RuleFeedbackInterface:
    """
    RFI (Rule Feedback Interface) logging uncertainty cases to SQLite.
    Allows validation/corrections to be written back as new RAG-Doll entries.
    """
    def __init__(self, db_path: str = "state/event_log/rfi_feedback.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rfi_logs (
                    query_hash TEXT PRIMARY KEY,
                    query TEXT,
                    retrieved_chunks TEXT,
                    interpretation TEXT,
                    confidence REAL,
                    simulation_id TEXT,
                    turn_id TEXT,
                    validated_by TEXT,
                    correct INTEGER
                )
            """)
            conn.commit()

    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.encode("utf-8")).hexdigest()

    def log_uncertain_query(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        interpretation: str,
        confidence: float,
        simulation_id: str,
        turn_id: str
    ):
        qhash = self._hash_query(query)
        chunks_json = json.dumps(retrieved_chunks)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO rfi_logs 
                (query_hash, query, retrieved_chunks, interpretation, confidence, simulation_id, turn_id, validated_by, correct)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (qhash, query, chunks_json, interpretation, confidence, simulation_id, turn_id)
            )
            conn.commit()

    def get_unvalidated_logs(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM rfi_logs WHERE validated_by IS NULL")
            return [dict(row) for row in cursor.fetchall()]

    def validate_log(self, query_hash: str, correct: bool, validated_by: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE rfi_logs SET correct = ?, validated_by = ? WHERE query_hash = ?",
                (1 if correct else 0, validated_by, query_hash)
            )
            conn.commit()
            return cursor.rowcount > 0
