"""Local SQLite cache for search results and installed-state.

Stores JSON-encoded AppInfo lists per (source, query) with fetch timestamps,
plus an installed-package table that stays accurate via invalidation.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from ins.models import AppInfo

SCHEMA_VERSION = 1
_RETRIES = 3
_RETRY_DELAY = 0.05

_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_cache (
    source     TEXT NOT NULL,
    query      TEXT NOT NULL,
    data       TEXT NOT NULL,
    fetched_at REAL NOT NULL,
    PRIMARY KEY (source, query)
);
CREATE TABLE IF NOT EXISTS installed (
    source  TEXT NOT NULL,
    id      TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (source, id)
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def default_db_path() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return base / "ins" / "cache.db"


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class Cache:
    """Fail-soft cache: any storage error degrades to no caching, never breaks the CLI."""

    def __init__(self, path: Path | str | None = None, *, enabled: bool = True):
        self._path = Path(path) if path else default_db_path()
        self._ok = False
        if not enabled:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
            self._ok = True
        except (OSError, sqlite3.Error):
            self._ok = False

    def stats(self) -> dict:
        """Cache health stats for `ins doctor`."""
        entries = 0
        if self._ok:
            try:
                with self._connect() as conn:
                    entries = conn.execute("SELECT COUNT(*) FROM search_cache").fetchone()[0]
            except sqlite3.Error:
                pass
        size = 0
        try:
            size = self._path.stat().st_size
        except OSError:
            pass
        return {
            "enabled": self._ok,
            "entries": entries,
            "db_size": size,
            "path": str(self._path),
        }

    # ------------------------------------------------------------- lifecycle

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _retry(self, fn):
        last: Exception | None = None
        for _ in range(_RETRIES):
            try:
                return fn()
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                last = exc
                time.sleep(_RETRY_DELAY)
        raise last

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if row is not None and int(row["value"]) != SCHEMA_VERSION:
                conn.executescript(
                    "DROP TABLE IF EXISTS search_cache;"
                    "DROP TABLE IF EXISTS installed;"
                    "DROP TABLE IF EXISTS meta;"
                )
                conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    # --------------------------------------------------------- search cache

    def put_results(self, source: str, query: str, infos: list[AppInfo]) -> None:
        if not self._ok:
            return
        data = json.dumps([info.to_dict() for info in infos], ensure_ascii=False)

        def op() -> None:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO search_cache(source, query, data, fetched_at)"
                    " VALUES(?, ?, ?, ?)",
                    (source, query, data, time.time()),
                )

        try:
            self._retry(op)
        except sqlite3.Error:
            self._ok = False

    def get_results(self, source: str, query: str) -> tuple[list[AppInfo], float] | None:
        """(infos, fetched_at) for the entry, or None."""
        if not self._ok:
            return None
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT data, fetched_at FROM search_cache WHERE source=? AND query=?",
                    (source, query),
                ).fetchone()
        except sqlite3.Error:
            self._ok = False
            return None
        if row is None:
            return None
        return _decode_infos(row["data"]), row["fetched_at"]

    def get_fresh(self, source: str, query: str, ttl: int) -> list[AppInfo] | None:
        """Cached results younger than `ttl` seconds, else None."""
        if not self._ok:
            return None
        entry = self.get_results(source, query)
        if entry is None:
            return None
        infos, fetched_at = entry
        if time.time() - fetched_at > ttl:
            return None
        return infos

    def get_any(self, source: str, query: str) -> list[AppInfo] | None:
        """Cached results regardless of age (offline fallback), else None."""
        if not self._ok:
            return None
        entry = self.get_results(source, query)
        return entry[0] if entry is not None else None

    def invalidate(self, *, package_id: str | None = None, source: str | None = None, query: str | None = None) -> None:
        """Drop cached search rows matching any of the given criteria."""
        if not self._ok:
            return
        conditions: list[str] = []
        params: list[str] = []
        if package_id is not None:
            conditions.append("data LIKE ? ESCAPE '\\'")
            params.append(f'%"id": "{_like_escape(package_id)}"%')
        if source is not None:
            conditions.append("source = ?")
            params.append(source)
        if query is not None:
            conditions.append("query = ?")
            params.append(query)
        if not conditions:
            return

        def op() -> None:
            with self._connect() as conn:
                conn.execute(f"DELETE FROM search_cache WHERE {' AND '.join(conditions)}", params)

        try:
            self._retry(op)
        except sqlite3.Error:
            self._ok = False

    def clear(self) -> None:
        if not self._ok:
            return

        def op() -> None:
            with self._connect() as conn:
                conn.execute("DELETE FROM search_cache")
                conn.execute("DELETE FROM installed")

        try:
            self._retry(op)
        except sqlite3.Error:
            self._ok = False

    # ------------------------------------------------------- installed state

    def mark_installed(self, source: str, package_id: str, version: str = "") -> None:
        if not self._ok:
            return

        def op() -> None:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO installed(source, id, version) VALUES(?, ?, ?)",
                    (source, package_id, version),
                )

        try:
            self._retry(op)
        except sqlite3.Error:
            self._ok = False

    def mark_removed(self, source: str, package_id: str) -> None:
        if not self._ok:
            return

        def op() -> None:
            with self._connect() as conn:
                conn.execute("DELETE FROM installed WHERE source=? AND id=?", (source, package_id))

        try:
            self._retry(op)
        except sqlite3.Error:
            self._ok = False

    def refresh_installed(self, adapters) -> dict[str, int]:
        """Snapshot each adapter's installed list into the cache.

        Returns {source: count}; sources that fail are left untouched.
        """
        if not self._ok:
            return {}
        counts: dict[str, int] = {}
        for adapter in adapters:
            try:
                infos = adapter.list_installed()
            except Exception:
                continue
            try:
                self._replace_installed(adapter.name, infos)
                counts[adapter.name] = len(infos)
            except sqlite3.Error:
                self._ok = False
                break
        return counts

    def _replace_installed(self, source: str, infos: list[AppInfo]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM installed WHERE source=?", (source,))
            conn.executemany(
                "INSERT OR REPLACE INTO installed(source, id, version) VALUES(?, ?, ?)",
                [(source, info.id, info.version) for info in infos],
            )

    def get_installed(self, source: str | None = None) -> list[tuple[str, str, str]]:
        if not self._ok:
            return []
        try:
            with self._connect() as conn:
                if source is not None:
                    rows = conn.execute(
                        "SELECT source, id, version FROM installed WHERE source=? ORDER BY id",
                        (source,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT source, id, version FROM installed ORDER BY source, id"
                    ).fetchall()
        except sqlite3.Error:
            self._ok = False
            return []
        return [(r["source"], r["id"], r["version"]) for r in rows]


def _decode_infos(data: str) -> list[AppInfo]:
    try:
        raw = json.loads(data)
        return [AppInfo.from_dict(item) for item in raw]
    except (ValueError, TypeError):
        return []
