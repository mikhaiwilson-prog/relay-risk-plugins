from __future__ import annotations

import datetime
import json
import os
import secrets
import shutil
from pathlib import Path
from typing import Any, cast

from mcp.server.fastmcp import FastMCP

from ai_verify.c2pa_check import check_c2pa
from ai_verify.config import DEFAULT_OUT_DIR
from ai_verify.face_mask import FaceDetectionFailedError, mask_faces
from ai_verify.notify import notify_slack
from ai_verify.result_merger import merge_results

_DOWNLOADS_DIR = Path.home() / "Downloads"

mcp = FastMCP("ai-verify")


def _make_run_id() -> str:
    now = datetime.datetime.now()
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def _run_dir(run_id: str, out_dir: str | None) -> Path:
    base = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    return base / run_id


@mcp.tool()
def check_image(
    image_path: str,
    out_dir: str | None = None,
) -> dict[str, Any]:
    """
    Run the local AI-image verification pipeline.

    PRIVACY GUARDRAILS:
    - Face masking is mandatory. There is no flag to skip it.
    - The unmasked image is NEVER copied into the run directory.
    - The unmasked image path is NEVER surfaced in the return value.
    - If face detection fails, no image artifact is produced (no masked copy,
      no Downloads copy, no manual-check URLs). The analyst is told to verify
      the image is a selfie.

    On success returns: run_id, C2PA result, mask result, downloads_path,
    manual_check_urls, and artifact paths for the MASKED image only.
    """
    path = Path(image_path)
    run_id = _make_run_id()
    run_dir = _run_dir(run_id, out_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    # Face masking runs first. The pipeline refuses to produce any image
    # artifact (masked copy, Downloads copy, upload-URL guidance) unless
    # masking succeeds. The unmasked original is never copied or exposed.
    masked_path = run_dir / "masked.jpg"
    mask_result: dict[str, Any] | None = None
    mask_error: str | None = None
    try:
        mask_result = mask_faces(path, masked_path)
    except FaceDetectionFailedError as exc:
        mask_error = str(exc)
    except Exception as exc:
        mask_error = f"Masking failed: {exc}"

    downloads_copy: Path | None = None
    if mask_result and _DOWNLOADS_DIR.exists():
        downloads_copy = _DOWNLOADS_DIR / f"ai-verify-{run_id}.jpg"
        shutil.copy2(masked_path, downloads_copy)

    # C2PA reads metadata only — does not surface pixel data to the LLM.
    c2pa_result = check_c2pa(path)
    c2pa_result["run_id"] = run_id
    (run_dir / "c2pa.json").write_text(json.dumps(c2pa_result, indent=2))

    status: dict[str, Any] = {
        "run_id": run_id,
        "image": path.name,
        "run_dir": str(run_dir),
        "c2pa": c2pa_result,
        "mask": mask_result,
        "mask_error": mask_error,
        "downloads_path": str(downloads_copy) if downloads_copy else None,
        # Manual-check URLs are only surfaced when there's a masked image
        # available — never direct the analyst to upload an unmasked image.
        "manual_check_urls": (
            {
                "gemini": "https://gemini.google.com",
                "openai_verify": "https://openai.com/research/verify",
            }
            if mask_result
            else None
        ),
        "artifacts": {
            "masked": str(masked_path) if mask_result else None,
            "c2pa_json": str(run_dir / "c2pa.json"),
            "downloads_copy": str(downloads_copy) if downloads_copy else None,
            # NOTE: 'original' is intentionally NOT included — privacy guardrail.
        },
    }
    (run_dir / "status.json").write_text(json.dumps(status, indent=2))

    return status


@mcp.tool()
def merge_run(
    run_id: str,
    agent_json_path: str,
    out_dir: str | None = None,
    slack_notify: bool = False,
) -> dict[str, Any]:
    """
    Merge local C2PA results with manual findings from Gemini SynthID
    and/or OpenAI Verify.

    Writes final.json to the run directory and returns the final verdict.
    """
    run_dir = _run_dir(run_id, out_dir)

    c2pa_path = run_dir / "c2pa.json"
    if not c2pa_path.exists():
        return {"error": f"No c2pa.json found for run '{run_id}'. Run check_image first."}

    local = json.loads(c2pa_path.read_text())

    agent_path = Path(agent_json_path)
    if not agent_path.exists():
        return {"error": f"Agent JSON file not found: {agent_json_path}"}

    agent = json.loads(agent_path.read_text())
    final = merge_results(local, agent)

    (run_dir / "final.json").write_text(json.dumps(final, indent=2))

    if slack_notify:
        webhook = os.environ.get("AI_VERIFY_SLACK_WEBHOOK")
        if webhook:
            notify_slack(final, webhook)

    return final


@mcp.tool()
def show_run(run_id: str, out_dir: str | None = None) -> dict[str, Any]:
    """Show the final verdict for a completed run."""
    run_dir = _run_dir(run_id, out_dir)
    final_path = run_dir / "final.json"

    if not final_path.exists():
        return {"error": f"No final.json for run '{run_id}'. Run merge_run first."}

    return cast(dict[str, Any], json.loads(final_path.read_text()))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
