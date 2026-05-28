from __future__ import annotations

from typing import Any

_INCOMPLETE_VERDICTS = frozenset({"quota_exhausted", "auth_required", "error", "blocked"})


def _c2pa_signal(local: dict[str, Any]) -> str:
    if local.get("error"):
        return "invalid"
    if not local.get("has_c2pa"):
        return "absent"
    if local.get("has_ai_assertion") and local.get("c2pa_valid"):
        return "ai_assertion"
    if local.get("c2pa_valid") and not local.get("has_ai_assertion"):
        return "valid_no_ai"
    return "invalid"


def merge_results(local: dict[str, Any], agent: dict[str, Any] | None) -> dict[str, Any]:
    """
    Combine local C2PA result with agent JSON from Claude in Chrome.

    Conservative: prefers 'needs_manual_review' over a wrong 'ai_confirmed'.
    """
    run_id: str = local.get("run_id") or (agent or {}).get("run_id") or "unknown"

    c2pa_sig = _c2pa_signal(local)

    gemini_verdict: str | None = None
    openai_verdict: str | None = None
    if agent:
        gemini_verdict = (agent.get("gemini") or {}).get("verdict")
        openai_verdict = (agent.get("openai") or {}).get("verdict")

    if c2pa_sig == "ai_assertion":
        verdict, confidence = "ai_confirmed", "high"
        reasoning = "Local C2PA manifest contains a valid AI assertion."

    elif agent and openai_verdict == "ai_detected" and gemini_verdict == "ai_google":
        verdict, confidence = "ai_confirmed", "high"
        reasoning = "Both Gemini SynthID and OpenAI Verify independently flagged AI generation."

    elif agent and (openai_verdict == "ai_detected" or gemini_verdict == "ai_google"):
        verdict, confidence = "ai_likely", "medium"
        source = "OpenAI Verify" if openai_verdict == "ai_detected" else "Gemini SynthID"
        reasoning = f"{source} flagged AI generation; other service inconclusive."

    elif (
        c2pa_sig == "valid_no_ai"
        and agent
        and openai_verdict == "no_signal"
        and gemini_verdict == "no_google_ai"
    ):
        verdict, confidence = "no_ai_signal", "medium"
        reasoning = (
            "Valid signed C2PA provenance with no AI assertion; "
            "both remote services confirm no AI signal."
        )

    elif agent and openai_verdict == "no_signal" and gemini_verdict == "no_google_ai":
        verdict, confidence = "no_ai_signal", "low"
        reasoning = "No AI signals detected — absence of evidence only, no positive provenance."

    elif agent and (
        gemini_verdict in _INCOMPLETE_VERDICTS or openai_verdict in _INCOMPLETE_VERDICTS
    ):
        missing: list[str] = []
        if gemini_verdict in _INCOMPLETE_VERDICTS:
            missing.append(f"Gemini ({gemini_verdict})")
        if openai_verdict in _INCOMPLETE_VERDICTS:
            missing.append(f"OpenAI ({openai_verdict})")
        verdict, confidence = "incomplete", "low"
        reasoning = (
            f"Incomplete results from: {', '.join(missing)}. "
            "Re-run or check service availability."
        )

    elif agent is None:
        verdict, confidence = "incomplete", "low"
        reasoning = "No agent results provided; only local C2PA check completed."

    else:
        verdict, confidence = "needs_manual_review", "low"
        reasoning = "Mixed or unclear signals; manual analyst review required."

    return {
        "run_id": run_id,
        "overall_verdict": verdict,
        "confidence": confidence,
        "signals": {
            "c2pa_local": c2pa_sig,
            "gemini": gemini_verdict,
            "openai": openai_verdict,
        },
        "reasoning": reasoning,
        "raw": {"local": local, "agent": agent},
    }
