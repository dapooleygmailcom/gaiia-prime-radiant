import os
import sqlite3
import pytest
from unittest.mock import patch
from engine.rules.rule_feedback_interface import RuleFeedbackInterface

@pytest.fixture
def rfi():
    db_path = "state/event_log/test_rfi_feedback.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    interface = RuleFeedbackInterface(db_path=db_path)
    yield interface
    
    if os.path.exists(db_path):
        os.remove(db_path)

def test_rfi_log_and_validate(rfi):
    rfi.log_uncertain_query(
        query="What is a laser?",
        retrieved_chunks=[{"text": "A laser shoots light."}],
        interpretation="It does 10 damage.",
        confidence=0.4,
        simulation_id="sim1",
        turn_id="1"
    )
    
    unvalidated = rfi.get_unvalidated_logs()
    assert len(unvalidated) == 1
    
    query_hash = unvalidated[0]["query_hash"]
    
    # We pass push_to_rag_doll=False so it doesn't actually try to write to ChromaDB
    # in the middle of our simple unit test.
    success = rfi.validate_log(query_hash, correct=True, validated_by="admin", push_to_rag_doll=False)
    
    assert success is True
    
    # Should no longer be unvalidated
    unvalidated_after = rfi.get_unvalidated_logs()
    assert len(unvalidated_after) == 0

def test_rfi_writeback_mock(rfi):
    rfi.log_uncertain_query(
        query="Mocked query",
        retrieved_chunks=[],
        interpretation="Mocked interpretation",
        confidence=0.1,
        simulation_id="sim2",
        turn_id="1"
    )
    
    unvalidated = rfi.get_unvalidated_logs()
    query_hash = unvalidated[0]["query_hash"]
    
    with patch.object(rfi, 'writeback_to_rag_doll') as mock_writeback:
        rfi.validate_log(query_hash, correct=True, validated_by="user1", push_to_rag_doll=True)
        
        mock_writeback.assert_called_once()
        args = mock_writeback.call_args[0][0]
        assert args["query_hash"] == query_hash
        assert args["validated_by"] == "user1"
