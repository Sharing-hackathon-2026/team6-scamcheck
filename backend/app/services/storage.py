"""SQLite persistence for bounded cache and session-scoped AI call history."""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_SESSION_ID_KEY = "scamcheck_session_id"
_SESSION_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_RISK_LEVELS = {"an_toan", "nghi_ngo", "nguy_hiem"}
_ACTORS = {"detective", "psychologist", "rescuer", "unknown"}


def _iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="seconds")


class SQLiteStore:
    """One SQLite database shared by gunicorn workers through WAL mode.

    Cache keys are hashes supplied by ``build_cache_key``. AI history is scoped
    by a pseudonymous browser-session id and stores the submitted prompt plus
    the normalized Detective verdict for the history table requested by users.
    """

    def __init__(
        self,
        path: str,
        *,
        capacity: int = 256,
        ttl_seconds: int = 3600,
        log_retention_days: int = 30,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = str(path)
        self.capacity = max(1, int(capacity))
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.log_retention_seconds = max(1, int(log_retention_days)) * 86400
        self._clock = clock
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=8.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 8000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            if self.path != ":memory:":
                connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    accessed_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cache_expiry
                    ON cache_entries(expires_at);

                CREATE TABLE IF NOT EXISTS ai_request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_unix REAL NOT NULL,
                    actor TEXT NOT NULL,
                    status TEXT NOT NULL,
                    risk_level TEXT,
                    input_length INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    prompt_text TEXT NOT NULL DEFAULT '',
                    verdict_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_ai_logs_session_time
                    ON ai_request_logs(session_id, created_unix);
                CREATE INDEX IF NOT EXISTS idx_ai_logs_actor_risk
                    ON ai_request_logs(actor, risk_level);
                """
            )
            # Additive migration for databases deployed before prompt/verdict history.
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(ai_request_logs)").fetchall()
            }
            migrations = {
                "prompt_text": "ALTER TABLE ai_request_logs ADD COLUMN prompt_text TEXT NOT NULL DEFAULT ''",
                "verdict_json": "ALTER TABLE ai_request_logs ADD COLUMN verdict_json TEXT NOT NULL DEFAULT '{}'",
            }
            for column, statement in migrations.items():
                if column in columns:
                    continue
                try:
                    connection.execute(statement)
                except sqlite3.OperationalError as exc:
                    # Hai gunicorn worker có thể cùng migrate DB cũ lúc boot.
                    if "duplicate column name" not in str(exc).casefold():
                        raise

    # Cache API kept compatible with the previous in-memory TTLHashCache.
    def get(self, key: str) -> dict[str, Any] | None:
        now = self._clock()
        with self._connect() as connection:
            connection.execute("DELETE FROM cache_entries WHERE expires_at <= ?", (now,))
            row = connection.execute(
                "SELECT payload_json FROM cache_entries WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE cache_entries SET accessed_at = ? WHERE cache_key = ?",
                (now, key),
            )
        try:
            value = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            with self._connect() as connection:
                connection.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
            return None
        return value if isinstance(value, dict) else None

    def put(self, key: str, value: dict[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        now = self._clock()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cache_entries
                    (cache_key, payload_json, expires_at, created_at, accessed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    expires_at = excluded.expires_at,
                    created_at = excluded.created_at,
                    accessed_at = excluded.accessed_at
                """,
                (key, payload, now + self.ttl_seconds, _iso_utc(now), now),
            )
            connection.execute("DELETE FROM cache_entries WHERE expires_at <= ?", (now,))
            count = int(connection.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0])
            overflow = count - self.capacity
            if overflow > 0:
                connection.execute(
                    """
                    DELETE FROM cache_entries WHERE cache_key IN (
                        SELECT cache_key FROM cache_entries
                        ORDER BY accessed_at ASC LIMIT ?
                    )
                    """,
                    (overflow,),
                )

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM cache_entries")

    def __len__(self) -> int:
        now = self._clock()
        with self._connect() as connection:
            connection.execute("DELETE FROM cache_entries WHERE expires_at <= ?", (now,))
            return int(connection.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0])

    # Session and AI log API.
    @staticmethod
    def session_id(session: Any) -> str:
        existing = session.get(_SESSION_ID_KEY, "")
        if isinstance(existing, str) and _SESSION_ID_RE.fullmatch(existing):
            return existing
        identifier = uuid.uuid4().hex
        session[_SESSION_ID_KEY] = identifier
        if hasattr(session, "modified"):
            session.modified = True
        return identifier

    def append_log(
        self,
        *,
        session_id: str,
        input_length: int,
        summary: str,
        actor: str,
        status: str,
        risk_level: str | None,
        prompt: str = "",
        verdict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = self._clock()
        clean_actor = actor if actor in _ACTORS else "unknown"
        clean_risk = risk_level if risk_level in _RISK_LEVELS else None
        clean_status = str(status or "unknown")[:48]
        clean_summary = str(summary or "Đã nhận kết quả kiểm tra")[:240]
        clean_length = max(0, int(input_length))
        clean_prompt = str(prompt or "")[:5000]
        clean_verdict = verdict if isinstance(verdict, dict) else {}
        verdict_json = json.dumps(clean_verdict, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ai_request_logs
                    (session_id, created_at, created_unix, actor, status,
                     risk_level, input_length, summary, prompt_text, verdict_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    _iso_utc(now),
                    now,
                    clean_actor,
                    clean_status,
                    clean_risk,
                    clean_length,
                    clean_summary,
                    clean_prompt,
                    verdict_json,
                ),
            )
            self._prune_logs(connection, now)
        return {
            "at": _iso_utc(now),
            "actor": clean_actor,
            "status": clean_status,
            "risk_level": clean_risk,
            "input_length": clean_length,
            "summary": clean_summary,
            "prompt": clean_prompt,
            "verdict": clean_verdict,
        }

    def _prune_logs(self, connection: sqlite3.Connection, now: float) -> None:
        connection.execute(
            "DELETE FROM ai_request_logs WHERE created_unix < ?",
            (now - self.log_retention_seconds,),
        )

    def list_logs(
        self,
        *,
        session_id: str | None = None,
        limit: int | None = 500,
        include_session_id: bool = False,
    ) -> list[dict[str, Any]]:
        now = self._clock()
        where = "WHERE session_id = ?" if session_id else ""
        params: list[Any] = [session_id] if session_id else []
        limit_sql = ""
        if limit is not None:
            limit_sql = "LIMIT ?"
            params.append(max(1, min(int(limit), 10000)))
        query = f"""
            SELECT * FROM (
                SELECT id, session_id, created_at, actor, status, risk_level,
                       input_length, summary, prompt_text, verdict_json, created_unix
                FROM ai_request_logs {where}
                ORDER BY created_unix DESC, id DESC {limit_sql}
            ) ORDER BY created_unix ASC, id ASC
        """
        with self._connect() as connection:
            self._prune_logs(connection, now)
            rows = connection.execute(query, params).fetchall()
        logs = []
        for row in rows:
            try:
                verdict = json.loads(row["verdict_json"])
            except (TypeError, json.JSONDecodeError):
                verdict = {}
            if not isinstance(verdict, dict):
                verdict = {}
            risk_level = "an_toan" if row["risk_level"] == "khong_lien_quan" else row["risk_level"]
            item = {
                "id": row["id"],
                "at": row["created_at"],
                "actor": row["actor"],
                "status": row["status"],
                "risk_level": risk_level,
                "input_length": row["input_length"],
                "summary": row["summary"],
                "prompt": row["prompt_text"],
                "verdict": verdict,
            }
            if include_session_id:
                item["session_id"] = row["session_id"]
            logs.append(item)
        return logs

    def log_stats(self, *, session_id: str | None = None) -> dict[str, Any]:
        now = self._clock()
        where = "WHERE session_id = ?" if session_id else ""
        params: tuple[Any, ...] = (session_id,) if session_id else ()
        actor_where = f"{where} {'AND' if where else 'WHERE'} actor = 'detective'"
        with self._connect() as connection:
            self._prune_logs(connection, now)
            total_calls = int(connection.execute(
                f"SELECT COUNT(*) FROM ai_request_logs {where}", params
            ).fetchone()[0])
            risk_rows = connection.execute(
                f"""
                SELECT CASE
                         WHEN risk_level = 'khong_lien_quan' THEN 'an_toan'
                         ELSE risk_level
                       END AS risk_level,
                       COUNT(*) AS amount
                FROM ai_request_logs {actor_where}
                GROUP BY CASE
                         WHEN risk_level = 'khong_lien_quan' THEN 'an_toan'
                         ELSE risk_level
                       END
                """,
                params,
            ).fetchall()
            actor_rows = connection.execute(
                f"SELECT actor, COUNT(*) AS amount FROM ai_request_logs {where} GROUP BY actor",
                params,
            ).fetchall()
        risk_counts = {key: 0 for key in sorted(_RISK_LEVELS)}
        for row in risk_rows:
            if row["risk_level"] in risk_counts:
                risk_counts[row["risk_level"]] = int(row["amount"])
        return {
            "ai_calls": total_calls,
            "checks": sum(risk_counts.values()),
            "risk_counts": risk_counts,
            "actor_counts": {row["actor"]: int(row["amount"]) for row in actor_rows},
            "retention_days": self.log_retention_seconds // 86400,
        }
