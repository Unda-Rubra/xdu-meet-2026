"""Durable archive tokens and explicit upload bindings; no scheduled cloud work."""
import json
from pathlib import Path
import secrets
import sqlite3
import time
import uuid


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=20)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS create_tokens (key TEXT PRIMARY KEY, token TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS receipts (
                token TEXT PRIMARY KEY, attempt TEXT NOT NULL UNIQUE, archive TEXT NOT NULL,
                digest TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS round_uploads (
                key TEXT PRIMARY KEY, round INTEGER NOT NULL, status TEXT NOT NULL,
                plan TEXT NOT NULL, bound_at REAL NOT NULL);
        ''')
        self.db.commit()

    def close(self):
        self.db.close()

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        with self.db:
            self.db.execute('INSERT INTO metadata VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                            (key, json.dumps(value, ensure_ascii=False)))

    def token(self, key):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO create_tokens VALUES (?,?)', (key, str(uuid.uuid4())))
        return self.db.execute('SELECT token FROM create_tokens WHERE key=?', (key,)).fetchone()[0]

    def receipt(self, token):
        row = self.db.execute('SELECT * FROM receipts WHERE token=?', (token,)).fetchone()
        if row is None:
            raise ValueError('Unknown result token')
        return dict(row)

    def receipts(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM receipts ORDER BY created')]

    def register(self, attempt, archive, digest):
        previous = self.db.execute('SELECT * FROM receipts WHERE attempt=?', (attempt,)).fetchone()
        if previous:
            return dict(previous)
        token = secrets.token_urlsafe(24)
        with self.db:
            self.db.execute('INSERT INTO receipts VALUES (?,?,?,?,?)', (token, attempt, str(archive), digest, time.time()))
        return self.receipt(token)

    def upload(self, key):
        row = self.db.execute('SELECT * FROM round_uploads WHERE key=?', (key,)).fetchone()
        return {**dict(row), 'plan': json.loads(row['plan'])} if row else None

    def uploads(self, status):
        return [self.upload(row[0]) for row in self.db.execute(
            'SELECT key FROM round_uploads WHERE status=? ORDER BY bound_at', (status,)).fetchall()]

    def bind_upload(self, key, round_number, plan):
        with self.db:
            self.db.execute('INSERT INTO round_uploads VALUES (?,?,?,?,?)',
                            (key, round_number, 'pending', json.dumps(plan, ensure_ascii=False), time.time()))

    def mark_upload(self, key, status):
        with self.db:
            self.db.execute('UPDATE round_uploads SET status=? WHERE key=?', (status, key))
