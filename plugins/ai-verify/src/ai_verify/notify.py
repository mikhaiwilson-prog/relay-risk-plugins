from __future__ import annotations

import os
from typing import Any

import requests

_VERDICT_EMOJI: dict[str, str] = {
    "ai_confirmed": "🤖",
    "ai_likely": "⚠️",
    "no_ai_signal": "✅",
    "needs_manual_review": "❓",
    "incomplete": "⏸️",
}


def notify_slack(final_result: dict[str, Any], webhook_url: str | None = None) -> None:
    """Post a verdict summary to Slack. No-ops if no webhook URL is configured."""
    url = webhook_url or os.environ.get("AI_VERIFY_SLACK_WEBHOOK")
    if not url:
        return

    verdict: str = final_result.get("overall_verdict", "unknown")
    emoji = _VERDICT_EMOJI.get(verdict, "❓")
    run_id: str = final_result.get("run_id", "unknown")
    reasoning: str = final_result.get("reasoning", "")
    signals: dict[str, Any] = final_result.get("signals", {})

    image_name: str = "unknown"
    raw = final_result.get("raw") or {}
    ag = raw.get("agent") or {}
    if ag.get("image"):
        image_name = ag["image"]

    signal_parts = [f"{k}={v}" for k, v in signals.items() if v]
    signals_str = " | ".join(signal_parts) or "none"

    text = (
        f"{emoji} *AI Verify — {verdict.upper()}*\n"
        f"Run: `{run_id}` | Image: `{image_name}`\n"
        f"_{reasoning}_\n"
        f"Signals: {signals_str}"
    )

    requests.post(url, json={"text": text}, timeout=10)
