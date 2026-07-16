"""FSM ba persona và số call tránh được so với baseline ngây thơ."""
from __future__ import annotations

import pytest

from app.services.fsm import after_check, after_situation, stage5_call_savings


def test_relevant_verdict_waits_for_situation_instead_of_calling_rescuer_early():
    state = after_check("nguy_hiem", "complete")
    assert state.state == "awaiting_situation"
    assert state.personas_completed == ("detective", "psychologist")
    assert state.next_event == "situation_selected"
    assert state.to_dict()["metrics"] == {
        "actual_ai_calls": 2,
        "naive_ai_calls": 3,
        "calls_saved": 1,
    }


def test_safe_verdict_finishes_after_detective_and_cache_uses_zero_calls():
    safe = after_check("an_toan", "not_needed")
    cached = after_check("nguy_hiem", "complete", cache_hit=True)
    assert safe.state == "assessment_complete"
    assert safe.to_dict()["metrics"]["calls_saved"] == 2
    assert cached.actual_ai_calls == 0
    assert cached.to_dict()["metrics"]["calls_saved"] == 3


@pytest.mark.parametrize(
    ("situation", "called", "state", "actual"),
    [
        ("chua_lam_gi", False, "prevention_complete", 0),
        ("da_bam_link", True, "rescue_complete", 1),
        ("da_chuyen_tien", True, "rescue_complete", 1),
        ("da_cung_cap_otp", True, "rescue_complete", 1),
    ],
)
def test_four_situation_transitions(situation, called, state, actual):
    result = after_situation(situation, rescuer_called=called)
    assert result.state == state
    assert result.actual_ai_calls == actual


def test_invalid_transition_is_rejected_and_baseline_is_measurable():
    with pytest.raises(ValueError):
        after_situation("tu_nhap_them", rescuer_called=True)
    assert stage5_call_savings() == {
        "flows": 4,
        "naive_rescuer_calls": 4,
        "fsm_rescuer_calls": 3,
        "calls_saved": 1,
        "reduction_percent": 25.0,
    }
