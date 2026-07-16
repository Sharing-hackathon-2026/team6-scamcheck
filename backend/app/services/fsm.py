"""Máy trạng thái điều phối ba persona, không để AI tự quyết định persona kế tiếp."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SITUATIONS = {
    "chua_lam_gi",
    "da_bam_link",
    "da_chuyen_tien",
    "da_cung_cap_otp",
}
_RELEVANT_RISKS = {"nghi_ngo", "nguy_hiem"}


@dataclass(frozen=True)
class OrchestrationState:
    """State + số call đo được so với cách ngây thơ luôn gọi cả ba persona."""

    state: str
    personas_completed: tuple[str, ...]
    next_event: str | None
    actual_ai_calls: int
    naive_ai_calls: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "personas_completed": list(self.personas_completed),
            "next_event": self.next_event,
            "metrics": {
                "actual_ai_calls": self.actual_ai_calls,
                "naive_ai_calls": self.naive_ai_calls,
                "calls_saved": max(0, self.naive_ai_calls - self.actual_ai_calls),
            },
        }


def after_check(
    risk_level: str,
    psychologist_status: str,
    *,
    cache_hit: bool = False,
) -> OrchestrationState:
    """Chuyển sau Thám tử/Cô tâm lý; tool name Gemini không tham gia quyết định."""
    if cache_hit:
        calls = 0
        completed = ("cached_assessment",)
    else:
        needs_psychologist = risk_level in _RELEVANT_RISKS
        calls = 1 + int(needs_psychologist)
        completed = ("detective", "psychologist") if needs_psychologist else ("detective",)

    if risk_level in _RELEVANT_RISKS:
        # Dù psychologist unavailable, verdict bảo vệ vẫn dẫn tới câu hỏi tình huống.
        return OrchestrationState(
            state="awaiting_situation",
            personas_completed=completed,
            next_event="situation_selected",
            actual_ai_calls=calls,
            naive_ai_calls=3,
        )
    return OrchestrationState(
        state="assessment_complete",
        personas_completed=completed,
        next_event=None,
        actual_ai_calls=calls,
        naive_ai_calls=3,
    )


def after_situation(situation: str, *, rescuer_called: bool) -> OrchestrationState:
    """Chuyển từ câu hỏi một lần sang prevention hoặc kế hoạch ứng cứu."""
    if situation not in SITUATIONS:
        raise ValueError("Tình huống không hợp lệ.")
    if situation == "chua_lam_gi":
        return OrchestrationState(
            state="prevention_complete",
            personas_completed=("rescuer_rules",),
            next_event=None,
            actual_ai_calls=0,
            naive_ai_calls=1,
        )
    return OrchestrationState(
        state="rescue_complete",
        personas_completed=("rescuer",) if rescuer_called else ("rescuer_guarded_fallback",),
        next_event=None,
        actual_ai_calls=int(rescuer_called),
        naive_ai_calls=1,
    )


def stage5_call_savings(situations: tuple[str, ...] = tuple(sorted(SITUATIONS))) -> dict[str, int | float]:
    """Đo baseline bốn flow: naïve gọi rescuer cho cả 'chưa làm gì', FSM thì không."""
    valid = [item for item in situations if item in SITUATIONS]
    naive = len(valid)
    actual = sum(item != "chua_lam_gi" for item in valid)
    saved = naive - actual
    return {
        "flows": len(valid),
        "naive_rescuer_calls": naive,
        "fsm_rescuer_calls": actual,
        "calls_saved": saved,
        "reduction_percent": round(saved * 100 / naive, 1) if naive else 0.0,
    }
