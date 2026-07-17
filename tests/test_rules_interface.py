import os
import json
from engine.rules.rules_interface import RulesInterface
from engine.rules.rule_feedback_interface import RuleFeedbackInterface

def test_rules_interface_exact_match(tmp_path):
    # Setup mock index file and mock profile
    import json
    idx_file = tmp_path / "mock_index.json"
    idx_data = {
        "SUPPRESSION": [{"chunk_id": "c1", "source_file": "centurion.pdf"}]
    }
    idx_file.write_text(json.dumps(idx_data))

    profile_file = tmp_path / "mock_profile.json"
    profile_data = {
        "game_name": "Test Game",
        "chroma_collection": "test-collection",
        "rule_index_file": str(idx_file)
    }
    profile_file.write_text(json.dumps(profile_data))

    # Initialize rules interface pointing to mock profile
    ri = RulesInterface(str(profile_file))
    
    # Mock ChromaDB get() call to return the text if hit
    class MockCollection:
        def get(self, ids, include):
            return {
                "documents": ["Suppression reduces movement and to-hit rolls."],
                "metadatas": [{"source_file": "centurion.pdf"}]
            }
    
    import engine.rules.rules_interface as rules_module
    rules_module._get_active_collection = lambda: MockCollection()

    res = ri.query_rule("Tell me about suppression rules")
    assert res["path_taken"] == "PATH 1 (Exact Reference)"
    assert res["confidence"] == 1.0
    assert "reduces movement" in res["text"]

def test_rules_interface_cache(tmp_path):
    profile_file = tmp_path / "mock_profile.json"
    profile_data = {
        "game_name": "Test Game",
        "chroma_collection": "test-collection",
        "rule_index_file": "mock_index.json"
    }
    profile_file.write_text(json.dumps(profile_data))

    ri = RulesInterface(str(profile_file))
    
    # Manually populate cache
    ri.l1_cache.set("Ranged combat resolution", {
        "text": "Woods give -2 penalty.",
        "source_chunks": []
    })

    res = ri.query_rule("Ranged combat resolution")
    assert res["path_taken"] == "PATH 2 (L1 Cache)"
    assert res["confidence"] == 0.9
    assert res["text"] == "Woods give -2 penalty."

def test_rfi_logging(tmp_path):
    db_file = tmp_path / "rfi.db"
    rfi = RuleFeedbackInterface(str(db_file))
    
    rfi.log_uncertain_query(
        query="Ambiguous rule 4",
        retrieved_chunks=[{"text": "Chunk text", "metadata": {}}],
        interpretation="Interpret as penalty.",
        confidence=0.5,
        simulation_id="sim_123",
        turn_id="3"
    )

    unval = rfi.get_unvalidated_logs()
    assert len(unval) == 1
    assert unval[0]["query"] == "Ambiguous rule 4"
    assert unval[0]["confidence"] == 0.5

    success = rfi.validate_log(unval[0]["query_hash"], correct=True, validated_by="test_user")
    assert success is True
    assert len(rfi.get_unvalidated_logs()) == 0
