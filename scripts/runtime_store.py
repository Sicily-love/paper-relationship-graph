"""SQLite operational store for resumable local runtime state.

Paper files and graph snapshots remain portable files.  Mutable coordination
state (configuration snapshots, jobs and events) is kept in one transactional
store so the App, browser adapter and launchd share the same view.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


SCHEMA_VERSION = 1


class RuntimeStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS state (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(namespace, key)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request_id TEXT,
                    job_id TEXT,
                    status TEXT NOT NULL,
                    elapsed_ms INTEGER,
                    error_code TEXT,
                    details TEXT
                );
            """)
            connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))

    def put(self, namespace: str, key: str, value: Any) -> None:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO state(namespace,key,value,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(namespace,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                (namespace, key, encoded, datetime.now(timezone.utc).isoformat()),
            )

    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        with self.connect() as connection:
            row = connection.execute("SELECT value FROM state WHERE namespace=? AND key=?", (namespace, key)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return default

    def schema_version(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
        value = row["value"] if row is not None else SCHEMA_VERSION
        try:
            return int(value)
        except (TypeError, ValueError):
            return SCHEMA_VERSION

    def append_event(self, *, operation: str, request_id: str, status: str, elapsed_ms: int, job_id: str | None = None, error_code: str | None = None, details: dict | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO events(created_at,operation,request_id,job_id,status,elapsed_ms,error_code,details) VALUES(?,?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), operation, request_id, job_id, status, elapsed_ms, error_code,
                 json.dumps(details or {}, ensure_ascii=False)),
            )

    def migrate_json(self, *, config: Path, discovery: Path, tasks: Path) -> bool:
        """Import legacy JSON once; retain files as browser-facing snapshots."""
        if self.get("meta", "legacy_json_migrated", False):
            return False
        for namespace, path in (("config", config), ("discovery", discovery), ("tasks", tasks)):
            if path.is_file():
                try:
                    self.put(namespace, "current", json.loads(path.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    continue
        self.put("meta", "legacy_json_migrated", True)
        return True
