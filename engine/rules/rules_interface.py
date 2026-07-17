import os
import sys
import json
import re
from typing import Dict, List, Any, Tuple

# Resolve RAG-Doll path to import rules_lawyer
curr_dir = os.path.dirname(os.path.abspath(__file__))
rag_doll_path = os.path.abspath(os.path.join(curr_dir, "../../../gaiia-rag-doll"))
rules_lawyer_file = os.path.join(rag_doll_path, "engine/retrieval/rules_lawyer.py")

ask_rules_lawyer_game = None
load_game_profile = None
_get_active_collection = None
_load_active_rule_index = None

# Dynamically load rules_lawyer from file path to bypass engine namespace conflicts
if os.path.exists(rules_lawyer_file):
    import importlib.util
    spec = importlib.util.spec_from_file_location("engine.retrieval.rules_lawyer", rules_lawyer_file)
    if spec and spec.loader:
        rules_lawyer_module = importlib.util.module_from_spec(spec)
        sys.modules["engine.retrieval.rules_lawyer"] = rules_lawyer_module
        try:
            spec.loader.exec_module(rules_lawyer_module)
            ask_rules_lawyer_game = getattr(rules_lawyer_module, "ask_rules_lawyer_game", None)
            load_game_profile = getattr(rules_lawyer_module, "load_game_profile", None)
            _get_active_collection = getattr(rules_lawyer_module, "_get_active_collection", None)
            _load_active_rule_index = getattr(rules_lawyer_module, "_load_active_rule_index", None)
        except Exception:
            pass

from engine.rules.rule_cache import RuleCache
from engine.rules.rule_feedback_interface import RuleFeedbackInterface

class RulesInterface:
    """
    Translates simulation rules queries to Gaiia RAG-Doll.
    Routes queries through three paths:
    - PATH 1: Exact Reference Match (Zero-LLM direct index search)
    - PATH 2: Semantic Search + Cache
    - PATH 3: Full RAG-Doll LLM Generation + Uncertainty RFI logging
    """
    def __init__(self, profile_path: str = "data/renegade_legion_profile.json"):
        self.profile_path = profile_path
        self.l1_cache = RuleCache()
        self.rfi = RuleFeedbackInterface()
        self.rule_index = {}
        
        # Resolve path relative to RAG-Doll if it exists
        abs_profile_path = profile_path
        if not os.path.exists(abs_profile_path) and os.path.exists(os.path.join(rag_doll_path, profile_path)):
            abs_profile_path = os.path.join(rag_doll_path, profile_path)

        if load_game_profile:
            load_game_profile(abs_profile_path)
            # Load exact rule index from file specified in profile
            with open(abs_profile_path, "r", encoding="utf-8") as f:
                profile_data = json.load(f)
                idx_file = profile_data.get("rule_index_file")
                abs_idx_file = idx_file
                if idx_file and not os.path.exists(abs_idx_file) and os.path.exists(os.path.join(rag_doll_path, idx_file)):
                    abs_idx_file = os.path.join(rag_doll_path, idx_file)
                if abs_idx_file and os.path.exists(abs_idx_file):
                    with open(abs_idx_file, "r", encoding="utf-8") as idx_f:
                        self.rule_index = json.load(idx_f)

    def query_rule(self, query: str, simulation_id: str = "default", turn_id: str = "0") -> Dict[str, Any]:
        """
        Queries RAG-Doll using three-path routing.
        Returns:
            {
                "text": str,
                "path_taken": str,
                "confidence": float,
                "source_chunks": List[Dict[str, Any]]
            }
        """
        # --- PATH 1: Exact Reference Match ---
        # Look for literal keywords matching the rule index keys
        clean_query = query.strip().upper()
        # Look for direct match of key in self.rule_index
        matched_key = None
        for key in self.rule_index.keys():
            if key in clean_query or clean_query in key:
                matched_key = key
                break

        if matched_key:
            # We found an exact matching key in our rules index
            entries = self.rule_index[matched_key]
            # Retrieve text from the database directly via entries
            collection = _get_active_collection()
            if collection and entries:
                chunk_id = entries[0].get("chunk_id")
                try:
                    res = collection.get(ids=[chunk_id], include=["documents", "metadatas"])
                    if res["documents"]:
                        return {
                            "text": res["documents"][0],
                            "path_taken": "PATH 1 (Exact Reference)",
                            "confidence": 1.0,
                            "source_chunks": [{"id": chunk_id, "metadata": res["metadatas"][0]}]
                        }
                except Exception:
                    pass

        # --- PATH 2: Semantic Cache ---
        cached = self.l1_cache.get(query)
        if cached:
            return {
                "text": cached["text"],
                "path_taken": "PATH 2 (L1 Cache)",
                "confidence": 0.9,
                "source_chunks": cached["source_chunks"]
            }

        # Perform semantic lookup (Path 2 direct fetch)
        collection = _get_active_collection()
        if collection:
            # Generate embedding using ollama or semantic query
            try:
                import ollama
                emb_resp = ollama.embeddings(model="nomic-embed-text", prompt=query)
                results = collection.query(
                    query_embeddings=[emb_resp["embedding"]],
                    n_results=3,
                    include=["documents", "metadatas"]
                )
                if results["documents"] and results["documents"][0]:
                    docs = results["documents"][0]
                    metas = results["metadatas"][0]
                    combined_text = "\n\n".join(docs)
                    retrieved = [{"text": d, "metadata": m} for d, m in zip(docs, metas)]
                    
                    # Store in L1 cache
                    self.l1_cache.set(query, {
                        "text": combined_text,
                        "source_chunks": retrieved
                    })

                    # If confidence/match looks highly relevant, return as PATH 2
                    return {
                        "text": combined_text,
                        "path_taken": "PATH 2 (Semantic)",
                        "confidence": 0.85,
                        "source_chunks": retrieved
                    }
            except Exception:
                pass

        # --- PATH 3: Full RAG-Doll LLM Fallback (Novel/Ambiguous Cases) ---
        if ask_rules_lawyer_game:
            try:
                answer, paired, debug_info = ask_rules_lawyer_game(query)
                source_chunks = [{"text": doc, "metadata": meta} for doc, meta in paired[:4]]
                
                # Log to RFI
                self.rfi.log_uncertain_query(
                    query=query,
                    retrieved_chunks=source_chunks,
                    interpretation=answer,
                    confidence=0.5,
                    simulation_id=simulation_id,
                    turn_id=turn_id
                )
                
                return {
                    "text": answer,
                    "path_taken": "PATH 3 (Uncertain LLM)",
                    "confidence": 0.5,
                    "source_chunks": source_chunks
                }
            except Exception as e:
                return {
                    "text": f"Error running RAG-Doll: {e}",
                    "path_taken": "PATH 3 (Failed)",
                    "confidence": 0.0,
                    "source_chunks": []
                }

        return {
            "text": "RAG-Doll rules lawyer not available.",
            "path_taken": "FALLBACK",
            "confidence": 0.0,
            "source_chunks": []
        }
