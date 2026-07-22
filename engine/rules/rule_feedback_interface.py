import sqlite3
import json
import hashlib
from contextlib import closing
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
        if self.db_path != ":memory:":
            dirname = os.path.dirname(self.db_path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
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
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO rfi_logs 
                    (query_hash, query, retrieved_chunks, interpretation, confidence, simulation_id, turn_id, validated_by, correct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                    """,
                    (qhash, query, chunks_json, interpretation, confidence, simulation_id, turn_id)
                )

    def get_unvalidated_logs(self) -> List[Dict[str, Any]]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM rfi_logs WHERE validated_by IS NULL")
            return [dict(row) for row in cursor.fetchall()]

    def validate_log(self, query_hash: str, correct: bool, validated_by: str, push_to_rag_doll: bool = True) -> bool:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM rfi_logs WHERE query_hash = ?", (query_hash,))
            row = cursor.fetchone()
            if not row:
                return False
                
            with conn:
                cursor = conn.execute(
                    "UPDATE rfi_logs SET correct = ?, validated_by = ? WHERE query_hash = ?",
                    (1 if correct else 0, validated_by, query_hash)
                )
            
            if correct and push_to_rag_doll:
                row_dict = dict(row)
                row_dict["validated_by"] = validated_by
                row_dict["correct"] = 1
                self.writeback_to_rag_doll(row_dict)
                
            return cursor.rowcount > 0

    def writeback_to_rag_doll(self, log_record: Dict[str, Any]):
        """
        Pushes a validated interpretation back to the RAG-Doll ChromaDB as an `interpretation_record`.
        This requires the RAG-Doll endpoints/module to be available.
        """
        # Resolve RAG-Doll path to import chromadb indexer
        import os
        import sys
        
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        rag_doll_path = os.path.abspath(os.path.join(curr_dir, "../../../gaiia-rag-doll"))
        indexer_file = os.path.join(rag_doll_path, "engine/retrieval/rules_lawyer.py")
        
        if os.path.exists(indexer_file):
            import importlib.util
            spec = importlib.util.spec_from_file_location("engine.retrieval.rules_lawyer_rfi", indexer_file)
            if spec and spec.loader:
                rules_lawyer_module = importlib.util.module_from_spec(spec)
                sys.modules["engine.retrieval.rules_lawyer_rfi"] = rules_lawyer_module
                try:
                    spec.loader.exec_module(rules_lawyer_module)
                    collection = rules_lawyer_module._get_active_collection()
                    if collection:
                        import uuid
                        doc_id = f"rfi_validated_{uuid.uuid4().hex[:8]}"
                        
                        # We store the validated interpretation so future PATH 2 lookups find it
                        text = f"Validated Interpretation for: {log_record['query']}\n{log_record['interpretation']}"
                        
                        metadata = {
                            "source": "RFI_Feedback",
                            "type": "interpretation_record",
                            "query_hash": log_record["query_hash"],
                            "validated_by": log_record["validated_by"]
                        }
                        
                        collection.add(
                            documents=[text],
                            metadatas=[metadata],
                            ids=[doc_id]
                        )
                except Exception as e:
                    print(f"Failed to writeback to RAG-Doll: {e}")
