import os
import sqlite3
import pytest
from engine.rules.rule_cache import RuleCache

@pytest.fixture
def cache():
    db_path = "state/cache/test_rule_cache.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    rc = RuleCache(db_path=db_path)
    yield rc
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

def test_rule_cache_set_and_get(cache):
    query = "How much damage does a Vulcan III do?"
    value = {"text": "A Vulcan III does 3 damage", "source_chunks": []}
    
    cache.set(query, value)
    
    retrieved = cache.get(query)
    assert retrieved is not None
    assert retrieved["text"] == value["text"]
    
def test_rule_cache_miss(cache):
    query = "Nonexistent query"
    assert cache.get(query) is None

def test_rule_cache_clear(cache):
    query = "Some query"
    cache.set(query, {"a": 1})
    
    assert cache.get(query) is not None
    
    cache.clear()
    assert cache.get(query) is None
