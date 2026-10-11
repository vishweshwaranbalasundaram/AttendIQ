"""DBConnection: a Singleton that owns the one shared database connection.

Works with SQLite (zero setup, default) or MySQL. All SQL elsewhere in the project
is written once with %s placeholders; this class translates them for SQLite.
"""
import datetime as _dt
import decimal
import re
import sqlite3
import threading
from pathlib import Path

from attendiq import config

_DB_DIR = Path(__file__).resolve().parents[2] / "db"


def now_str() -> str:
    """UTC timestamp as 'YYYY-MM-DD HH:MM:SS' (portable across SQLite and MySQL)."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _clean(value):
    """Normalise driver-specific types so the rest of the code never sees them."""
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(value, _dt.datetime) else value.isoformat()
    return value


class DBConnection:
    _instance = None
    _guard = threading.Lock()

    # ---- Singleton plumbing -------------------------------------------------
    @classmethod
    def get_instance(cls) -> "DBConnection":
        with cls._guard:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls, backend: str = None, sqlite_path: str = None) -> "DBConnection":
        """Close the current connection and open a fresh one (used by tests and the seeder)."""
        with cls._guard:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = cls(backend, sqlite_path)
            return cls._instance

    def __init__(self, backend: str = None, sqlite_path: str = None):
        self.backend = (backend or config.DB_BACKEND).lower()
        self._lock = threading.RLock()
        if self.backend == "sqlite":
            path = sqlite_path or config.SQLITE_PATH
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        elif self.backend == "mysql":
            import mysql.connector  # imported lazily so SQLite users do not need it
            self._mysql = mysql.connector
            self._conn = self._mysql.connect(**config.MYSQL)
        else:
            raise ValueError(f"Unknown ATTENDIQ_DB backend: {self.backend}")

    # ---- Low level ----------------------------------------------------------
    def _sql(self, sql: str) -> str:
        return sql.replace("%s", "?") if self.backend == "sqlite" else sql

    def _ensure_alive(self):
        if self.backend == "mysql":
            self._conn.ping(reconnect=True, attempts=3, delay=1)

    def execute(self, sql: str, params=()) -> int:
        """Run INSERT/UPDATE/DELETE. Returns lastrowid (or 0)."""
        with self._lock:
            self._ensure_alive()
            cur = self._conn.cursor()
            try:
                cur.execute(self._sql(sql), tuple(params))
                self._conn.commit()
                return cur.lastrowid or 0
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cur.close()

    def execute_many(self, sql: str, rows) -> None:
        with self._lock:
            self._ensure_alive()
            cur = self._conn.cursor()
            try:
                cur.executemany(self._sql(sql), [tuple(r) for r in rows])
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cur.close()

    def query(self, sql: str, params=()) -> list:
        """Run a SELECT and return a list of dicts."""
        with self._lock:
            self._ensure_alive()
            if self.backend == "sqlite":
                cur = self._conn.execute(self._sql(sql), tuple(params))
                rows = [dict(r) for r in cur.fetchall()]
            else:
                cur = self._conn.cursor(dictionary=True)
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
                cur.close()
        return [{k: _clean(v) for k, v in row.items()} for row in rows]

    def query_one(self, sql: str, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # ---- Schema -------------------------------------------------------------
    def init_schema(self) -> None:
        """Create all tables (idempotent)."""
        script = (_DB_DIR / f"schema_{self.backend}.sql").read_text()
        with self._lock:
            if self.backend == "sqlite":
                self._conn.executescript(script)
                self._conn.commit()
            else:
                cur = self._conn.cursor()
                for stmt in filter(None, (s.strip() for s in re.split(r";\s*\n", script))):
                    cur.execute(stmt)
                self._conn.commit()
                cur.close()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
