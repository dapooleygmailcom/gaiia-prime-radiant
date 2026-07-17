import hashlib
from collections import OrderedDict
from typing import Any, Optional

class RuleCache:
    """
    In-memory L1 cache using an LRU policy to map query strings/hashes
    to parsed rule objects retrieved from Gaiia RAG-Doll.
    """
    def __init__(self, maxsize: int = 256):
        self.maxsize = maxsize
        self.cache: OrderedDict[str, Any] = OrderedDict()

    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.encode("utf-8")).hexdigest()

    def get(self, query: str) -> Optional[Any]:
        qhash = self._hash_query(query)
        if qhash in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(qhash)
            return self.cache[qhash]
        return None

    def set(self, query: str, value: Any):
        qhash = self._hash_query(query)
        if qhash in self.cache:
            self.cache.move_to_end(qhash)
        self.cache[qhash] = value
        if len(self.cache) > self.maxsize:
            # Pop least recently used (first element)
            self.cache.popitem(last=False)

    def clear(self):
        self.cache.clear()
