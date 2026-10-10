"""SQLite persistence layer (plain SQL, no ORM, to show SQL skills)."""
import sqlite3
from contextlib import contextmanager

from app.config import db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    category        TEXT,
    priority        TEXT,
    confidence      REAL,
    needs_review    INTEGER DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'NEW',
    assignee        TEXT,
    ai_suggestion   TEXT,
    autonomy        TEXT,            -- AUTO | APPROVAL | MANUAL
    risk            TEXT,            -- low | medium | high | critical
    policy_reason   TEXT,
    approval_status TEXT,            -- PENDING | APPROVED | CORRECTED
    injection_flags TEXT DEFAULT '[]',
    explanation     TEXT DEFAULT '[]',
    similar_ids     TEXT DEFAULT '[]',
    parent_id       INTEGER REFERENCES tickets(id),
    is_incident     INTEGER DEFAULT 0,
    sla_due         TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id   INTEGER NOT NULL REFERENCES tickets(id),
    from_status TEXT,
    to_status   TEXT NOT NULL,
    note        TEXT,
    changed_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS corrections (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id          INTEGER NOT NULL REFERENCES tickets(id),
    title              TEXT NOT NULL,
    description        TEXT NOT NULL,
    predicted_category TEXT,
    correct_category   TEXT NOT NULL,
    correct_priority   TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_parent ON tickets(parent_id);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
