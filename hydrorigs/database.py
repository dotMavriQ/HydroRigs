import sqlite3
import time
import os
from pathlib import Path

DB_PATH = Path(os.getenv("HYDRORIGS_DB_TEST", str(Path.home() / ".local/share/hydrorigs/hydrorigs.db")))

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rigs (
            name TEXT PRIMARY KEY,
            tokens REAL,
            max_tokens REAL,
            refill_rate REAL,
            cooldown_until REAL,
            last_refill REAL,
            remaining INTEGER,
            reset_time REAL,
            last_synced REAL
        )
    """)
    conn.commit()
    conn.close()

def get_conn():
    return sqlite3.connect(DB_PATH)

def get_rig(name):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rigs WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "name": row[0],
            "tokens": row[1],
            "max_tokens": row[2],
            "refill_rate": row[3],
            "cooldown_until": row[4],
            "last_refill": row[5],
            "remaining": row[6],
            "reset_time": row[7],
            "last_synced": row[8]
        }
    return None

def update_rig(name, tokens=None, max_tokens=None, cooldown_until=None, last_refill=None, remaining=None, reset_time=None, last_synced=None):
    conn = get_conn()
    cursor = conn.cursor()
    updates = []
    params = []
    if tokens is not None:
        updates.append("tokens = ?")
        params.append(tokens)
    if max_tokens is not None:
        updates.append("max_tokens = ?")
        params.append(max_tokens)
    if cooldown_until is not None:
        updates.append("cooldown_until = ?")
        params.append(cooldown_until)
    if last_refill is not None:
        updates.append("last_refill = ?")
        params.append(last_refill)
    if remaining is not None:
        updates.append("remaining = ?")
        params.append(remaining)
    if reset_time is not None:
        updates.append("reset_time = ?")
        params.append(reset_time)
    if last_synced is not None:
        updates.append("last_synced = ?")
        params.append(last_synced)
    
    if updates:
        params.append(name)
        cursor.execute(f"UPDATE rigs SET {', '.join(updates)} WHERE name = ?", params)
        conn.commit()
    conn.close()

def upsert_rig(name, max_tokens, refill_rate):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO rigs (name, tokens, max_tokens, refill_rate, cooldown_until, last_refill, remaining, reset_time, last_synced)
        VALUES (?, ?, ?, ?, 0, ?, ?, 0, ?)
        ON CONFLICT(name) DO UPDATE SET
            max_tokens = excluded.max_tokens,
            refill_rate = excluded.refill_rate
    """, (name, max_tokens, max_tokens, refill_rate, time.time(), max_tokens, time.time()))
    conn.commit()
    conn.close()

def get_all_rigs():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rigs")
    rows = cursor.fetchall()
    conn.close()
    return [{
        "name": r[0],
        "tokens": r[1],
        "max_tokens": r[2],
        "refill_rate": r[3],
        "cooldown_until": r[4],
        "last_refill": r[5],
        "remaining": r[6],
        "reset_time": r[7],
        "last_synced": r[8]
    } for r in rows]
