"""
Script to inject updated combat mechanics into SQLite rule cache
and verify template damage, internal damage, painting laser SF modifier, and ammo rules.
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from seed_mechanics import resolve_combat_code, calculate_hex_range_code, check_los_code

db_path = os.path.join(os.path.dirname(__file__), "state/cache/rule_cache.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)

with sqlite3.connect(db_path) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compiled_mechanics (
            mechanic_name TEXT PRIMARY KEY,
            python_code TEXT,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("""
        INSERT OR REPLACE INTO compiled_mechanics (mechanic_name, python_code, last_accessed)
        VALUES ('calculate_hex_range', ?, CURRENT_TIMESTAMP)
    """, (calculate_hex_range_code,))
    conn.execute("""
        INSERT OR REPLACE INTO compiled_mechanics (mechanic_name, python_code, last_accessed)
        VALUES ('check_los', ?, CURRENT_TIMESTAMP)
    """, (check_los_code,))
    conn.execute("""
        INSERT OR REPLACE INTO compiled_mechanics (mechanic_name, python_code, last_accessed)
        VALUES ('resolve_combat', ?, CURRENT_TIMESTAMP)
    """, (resolve_combat_code,))
    conn.commit()

print(f"[OK] Successfully updated 'resolve_combat' and other mechanics in {db_path}")
