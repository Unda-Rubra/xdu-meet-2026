"""Durable local plans and import identities; never persist application credentials."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import time
import uuid


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=20)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
                plan TEXT NOT NULL, error TEXT, updated REAL NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_plan ON operations((1))
                WHERE status IN ('pending','running','failed');
            CREATE TABLE IF NOT EXISTS create_tokens (key TEXT PRIMARY KEY, token TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS snapshots (
                key TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL,
                revision INTEGER NOT NULL, archive TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS archives (path TEXT PRIMARY KEY, digest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS round_uploads (
                key TEXT PRIMARY KEY, round INTEGER NOT NULL, status TEXT NOT NULL,
                plan TEXT NOT NULL, bound_at REAL NOT NULL);
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        with self.db:
            self.db.execute("INSERT INTO metadata VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                            (key, json.dumps(value, ensure_ascii=False)))

    def token(self, key):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO create_tokens VALUES (?,?)", (key, str(uuid.uuid4())))
        return self.db.execute("SELECT token FROM create_tokens WHERE key=?", (key,)).fetchone()[0]

    def begin(self, kind, plan):
        operation = uuid.uuid4().hex
        with self.db:
            self.db.execute("INSERT INTO operations VALUES (?,?, 'pending',?,NULL,?)",
                            (operation, kind, json.dumps(plan, ensure_ascii=False), time.time()))
        return operation

    def active(self):
        row = self.db.execute("SELECT * FROM operations WHERE status IN ('pending','running','failed')").fetchone()
        return {**dict(row), 'plan': json.loads(row['plan'])} if row else None

    def finish(self, operation, error=None):
        with self.db:
            self.db.execute("UPDATE operations SET status=?,error=?,updated=? WHERE id=?",
                            ('failed' if error else 'done', error, time.time(), operation))

    def history(self):
        return [dict(row) for row in self.db.execute(
            "SELECT id,kind,status,error,updated FROM operations ORDER BY updated DESC LIMIT 30")]

    def remember_snapshot(self, key, snapshot, digest, archive):
        revision = snapshot.get('revision', 0)
        previous = self.db.execute("SELECT digest,revision FROM snapshots WHERE key=?", (key,)).fetchone()
        if previous and revision < previous['revision']:
            return
        if previous and revision == previous['revision'] and digest != previous['digest']:
            raise ValueError('Conflicting snapshots at the same revision: ' + key)
        with self.db:
            self.db.execute("INSERT INTO snapshots VALUES (?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET "
                            "payload=excluded.payload,digest=excluded.digest,revision=excluded.revision,archive=excluded.archive",
                            (key, json.dumps(snapshot, ensure_ascii=False), digest, revision, str(archive)))

    def snapshots(self):
        return [(json.loads(row['payload']), row['archive']) for row in self.db.execute('SELECT * FROM snapshots')]

    def upload(self, key):
        row = self.db.execute('SELECT * FROM round_uploads WHERE key=?', (key,)).fetchone()
        return {**dict(row), 'plan': json.loads(row['plan'])} if row else None

    def uploads(self, status):
        return [self.upload(row[0]) for row in self.db.execute(
            'SELECT key FROM round_uploads WHERE status=? ORDER BY bound_at', (status,)).fetchall()]

    def bind_upload(self, key, round_number, plan):
        with self.db:
            self.db.execute('INSERT INTO round_uploads VALUES (?,?,?, ?,?)',
                            (key, round_number, 'pending', json.dumps(plan, ensure_ascii=False), time.time()))

    def mark_upload(self, key, status):
        with self.db:
            self.db.execute('UPDATE round_uploads SET status=? WHERE key=?', (status, key))
