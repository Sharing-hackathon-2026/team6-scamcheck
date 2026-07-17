"""Privacy-preserving AI invocation audit backed by SQLite."""
from __future__ import annotations

from typing import Any

from .storage import SQLiteStore


def summarize_result(result: dict[str, Any]) -> str:
    """Create a short summary without writing the source message or prompt."""
    risk_level = result.get("risk_level")
    if isinstance(risk_level, str):
        return f"Mức rủi ro: {risk_level.replace('_', ' ')}"
    situation = result.get("situation")
    if isinstance(situation, str):
        return f"Tình huống ứng cứu: {situation.replace('_', ' ')}"
    return "Đã nhận kết quả kiểm tra"


def append_ai_log(
    session: Any,
    input_length: int,
    result: dict[str, Any],
    *,
    store: SQLiteStore,
    actor: str = "detective",
    status: str = "complete",
) -> None:
    """Persist one actual AI invocation as metadata under this browser session."""
    store.append_log(
        session_id=store.session_id(session),
        input_length=input_length,
        summary=summarize_result(result),
        actor=actor,
        status=status,
        risk_level=result.get("risk_level") if isinstance(result, dict) else None,
    )


def get_ai_log(
    session: Any,
    *,
    store: SQLiteStore,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Read this browser session's log without exposing its internal session id."""
    return store.list_logs(session_id=store.session_id(session), limit=limit)
