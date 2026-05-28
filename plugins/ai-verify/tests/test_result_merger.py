from __future__ import annotations

import pytest

from ai_verify.result_merger import merge_results


def local(
    has_c2pa: bool = False,
    c2pa_valid: bool | None = None,
    has_ai_assertion: bool = False,
    error: str | None = None,
) -> dict:
    return {
        "run_id": "test-run",
        "has_c2pa": has_c2pa,
        "c2pa_valid": c2pa_valid,
        "has_ai_assertion": has_ai_assertion,
        "validation_state": "valid" if c2pa_valid else None,
        "claim_generator_name": None,
        "signature_issuer": None,
        "ai_source_type": None,
        "ai_software_agent": None,
        "raw_manifest": None,
        "error": error,
    }


def agent(gemini: str, openai: str) -> dict:
    return {
        "run_id": "test-run",
        "image": "test.jpg",
        "gemini": {"verdict": gemini, "raw_response": "", "screenshot_taken": False},
        "openai": {
            "verdict": openai,
            "c2pa_found": None,
            "synthid_found": None,
            "generator_info": None,
            "raw_response": "",
            "screenshot_taken": False,
        },
    }


@pytest.mark.parametrize("case,loc,ag,expected_verdict,expected_confidence", [
    (
        "local c2pa AI assertion → ai_confirmed high",
        local(has_c2pa=True, c2pa_valid=True, has_ai_assertion=True),
        None,
        "ai_confirmed", "high",
    ),
    (
        "both remote agree AI → ai_confirmed high",
        local(),
        agent("ai_google", "ai_detected"),
        "ai_confirmed", "high",
    ),
    (
        "only openai fires → ai_likely medium",
        local(),
        agent("no_google_ai", "ai_detected"),
        "ai_likely", "medium",
    ),
    (
        "only gemini fires → ai_likely medium",
        local(),
        agent("ai_google", "no_signal"),
        "ai_likely", "medium",
    ),
    (
        "valid c2pa no AI + both remote clean → no_ai_signal medium",
        local(has_c2pa=True, c2pa_valid=True, has_ai_assertion=False),
        agent("no_google_ai", "no_signal"),
        "no_ai_signal", "medium",
    ),
    (
        "no c2pa + both remote clean → no_ai_signal low",
        local(),
        agent("no_google_ai", "no_signal"),
        "no_ai_signal", "low",
    ),
    (
        "gemini quota_exhausted → incomplete low",
        local(),
        agent("quota_exhausted", "no_signal"),
        "incomplete", "low",
    ),
    (
        "gemini auth_required → incomplete low",
        local(),
        agent("auth_required", "no_signal"),
        "incomplete", "low",
    ),
    (
        "openai blocked → incomplete low",
        local(),
        agent("no_google_ai", "blocked"),
        "incomplete", "low",
    ),
    (
        "both services errored → incomplete low",
        local(),
        agent("error", "error"),
        "incomplete", "low",
    ),
    (
        "no agent provided → incomplete low",
        local(),
        None,
        "incomplete", "low",
    ),
    (
        "unclear gemini + no_signal openai → needs_manual_review",
        local(),
        agent("unclear", "no_signal"),
        "needs_manual_review", "low",
    ),
])
def test_decision_table(
    case: str,
    loc: dict,
    ag: dict | None,
    expected_verdict: str,
    expected_confidence: str,
) -> None:
    result = merge_results(loc, ag)
    assert result["overall_verdict"] == expected_verdict, f"CASE: {case}"
    assert result["confidence"] == expected_confidence, f"CASE: {case}"


def test_return_shape() -> None:
    result = merge_results(local(), None)
    assert set(result.keys()) == {
        "run_id", "overall_verdict", "confidence", "signals", "reasoning", "raw"
    }


def test_signals_shape() -> None:
    result = merge_results(local(), agent("ai_google", "ai_detected"))
    assert set(result["signals"].keys()) == {"c2pa_local", "gemini", "openai"}


def test_raw_preserves_inputs() -> None:
    loc = local(has_c2pa=True, c2pa_valid=True, has_ai_assertion=True)
    ag = agent("ai_google", "ai_detected")
    result = merge_results(loc, ag)
    assert result["raw"]["local"] is loc
    assert result["raw"]["agent"] is ag


def test_reasoning_is_non_empty_string() -> None:
    result = merge_results(local(), agent("no_google_ai", "no_signal"))
    assert isinstance(result["reasoning"], str)
    assert len(result["reasoning"]) > 0


def test_c2pa_error_signal_is_invalid() -> None:
    loc = local(error="some c2pa error")
    result = merge_results(loc, agent("no_google_ai", "no_signal"))
    assert result["signals"]["c2pa_local"] == "invalid"


def test_c2pa_absent_signal() -> None:
    result = merge_results(local(has_c2pa=False), agent("no_google_ai", "no_signal"))
    assert result["signals"]["c2pa_local"] == "absent"


def test_c2pa_ai_assertion_signal() -> None:
    loc = local(has_c2pa=True, c2pa_valid=True, has_ai_assertion=True)
    result = merge_results(loc, None)
    assert result["signals"]["c2pa_local"] == "ai_assertion"


def test_c2pa_valid_no_ai_signal() -> None:
    loc = local(has_c2pa=True, c2pa_valid=True, has_ai_assertion=False)
    result = merge_results(loc, agent("no_google_ai", "no_signal"))
    assert result["signals"]["c2pa_local"] == "valid_no_ai"
