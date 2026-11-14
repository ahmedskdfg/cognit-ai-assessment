"""SQLite persistence for a single-machine hackathon demonstration."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from threading import RLock

class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        with self.db() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS sessions(
              id TEXT PRIMARY KEY, alias TEXT NOT NULL, created_at TEXT NOT NULL,
              question_id TEXT NOT NULL, difficulty INTEGER NOT NULL,
              streak INTEGER NOT NULL DEFAULT 0, history_json TEXT NOT NULL DEFAULT '[]',
              stage TEXT NOT NULL DEFAULT 'assessment');
            CREATE TABLE IF NOT EXISTS attempts(
              id TEXT PRIMARY KEY, session_id TEXT NOT NULL, question_id TEXT NOT NULL,
              created_at TEXT NOT NULL, code TEXT NOT NULL, explanation TEXT NOT NULL,
              plan TEXT NOT NULL, test_json TEXT NOT NULL, concept_json TEXT NOT NULL,
              score REAL NOT NULL, concept_score REAL NOT NULL,
              assistance_used INTEGER NOT NULL, flags_json TEXT NOT NULL,
              feedback TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sessions(id));
            CREATE TABLE IF NOT EXISTS assistance(
              id TEXT PRIMARY KEY, session_id TEXT NOT NULL, question_id TEXT NOT NULL,
              created_at TEXT NOT NULL, mode TEXT NOT NULL, query TEXT NOT NULL,
              decision TEXT NOT NULL, response TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews(
              id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL, created_at TEXT NOT NULL,
              previous_score REAL NOT NULL, new_score REAL NOT NULL,
              note TEXT NOT NULL, approved INTEGER NOT NULL);
            ''')
    def db(self):
        conn = sqlite3.connect(self.path, timeout=15, isolation_level='DEFERRED')
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    def one(self, sql, params=()):
        with self.lock, self.db() as c:
            row = c.execute(sql, params).fetchone()
            return dict(row) if row else None
    def all(self, sql, params=()):
        with self.lock, self.db() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]
    def execute(self, sql, params=()):
        with self.lock, self.db() as c:
            c.execute(sql, params)
            c.commit()
