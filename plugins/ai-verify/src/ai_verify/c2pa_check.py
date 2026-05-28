from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_verify.config import (
    AI_DIGITAL_SOURCE_TYPES,
    AI_GENERATOR_KEYWORDS,
    AI_SIGNATURE_ISSUERS,
)

_EMPTY: dict[str, Any] = {
    "has_c2pa": False,
    "c2pa_valid": None,
    "validation_state": None,
    "claim_generator_name": None,
    "signature_issuer": None,
    "has_ai_assertion": False,
    "ai_source_type": None,
    "ai_software_agent": None,
    "raw_manifest": None,
    "error": None,
}


def _action_dst(action: dict[str, Any]) -> str:
    """Read digitalSourceType from the action, with parameters fallback.

    Per C2PA 2.2 spec, digitalSourceType lives on the action object.
    Some producers (Photoshop generative fill, Firefly variations) place
    it inside action.parameters instead. Check both.
    """
    dst = action.get("digitalSourceType")
    if dst:
        return str(dst)
    params = action.get("parameters") or {}
    return str(params.get("digitalSourceType") or "")


def _action_software_agent(action: dict[str, Any]) -> str | None:
    """Read softwareAgent name; tolerates string and {name,...} dict forms."""
    sw = action.get("softwareAgent")
    if sw is None:
        params = action.get("parameters") or {}
        sw = params.get("softwareAgent")
    if isinstance(sw, dict):
        return sw.get("name")
    if isinstance(sw, str):
        return sw
    return None


def _is_ai_dst(dst: str) -> bool:
    """Case-insensitive check against the AI digitalSourceType vocabulary."""
    if not dst:
        return False
    dst_lower = dst.lower()
    return any(sub.lower() in dst_lower for sub in AI_DIGITAL_SOURCE_TYPES)


def _matches_ai_issuer(issuer: str | None) -> bool:
    if not issuer:
        return False
    issuer_lower = issuer.lower()
    return any(kw in issuer_lower for kw in AI_SIGNATURE_ISSUERS)


def check_c2pa(image_path: Path) -> dict[str, Any]:
    """
    Inspect image for C2PA manifest and AI assertions.

    Returns a flat dict with has_c2pa, validation, AI signal fields.
    Never raises — errors are surfaced in the 'error' key.
    """
    try:
        import c2pa
    except ImportError:
        return {**_EMPTY, "error": "c2pa-python not installed"}

    # Use try_create: returns None if no manifest found (clean negative),
    # raises C2paError for genuine errors (file not found, IO errors, etc.)
    try:
        # try_create returns None for images with no manifest (cleaner than
        # from_file which raises ManifestNotFound). Available in c2pa-python >= 0.7.
        reader = c2pa.Reader.try_create(str(image_path))
    except Exception as exc:
        return {**_EMPTY, "error": str(exc)}

    if reader is None:
        # No C2PA manifest present — clean negative, not an error
        return dict(_EMPTY)

    try:
        raw_json = reader.json()
    except Exception as exc:
        return {**_EMPTY, "error": f"Failed to read manifest JSON: {exc}"}

    try:
        manifest_store: dict[str, Any] = json.loads(raw_json)
    except Exception as exc:
        return {**_EMPTY, "error": f"JSON parse failed: {exc}"}

    active_label = manifest_store.get("active_manifest")
    if active_label is None:
        return dict(_EMPTY)
    if not active_label:
        return {**_EMPTY, "error": "Malformed manifest: empty active_manifest label"}

    manifest: dict[str, Any] = manifest_store.get("manifests", {}).get(active_label, {})

    validation_status: list[Any] = manifest.get("validation_status", [])
    c2pa_valid = len(validation_status) == 0
    validation_state = "valid" if c2pa_valid else str(validation_status)

    gen_info: list[Any] = manifest.get("claim_generator_info", [])
    claim_generator_name: str | None = gen_info[0].get("name") if gen_info else None

    sig_info: dict[str, Any] = manifest.get("signature_info", {})
    signature_issuer: str | None = sig_info.get("issuer")

    has_ai_assertion = False
    ai_source_type: str | None = None
    ai_software_agent: str | None = None

    # Per C2PA 2.2, action assertions can be labelled `c2pa.actions` or
    # `c2pa.actions.v2` (and future v3+). Match by prefix.
    for assertion in manifest.get("assertions", []):
        label: str = assertion.get("label", "")
        data: dict[str, Any] = assertion.get("data", {})

        if label.startswith("c2pa.actions"):
            for action in data.get("actions", []):
                dst = _action_dst(action)
                if _is_ai_dst(dst):
                    has_ai_assertion = True
                    ai_source_type = dst
                    ai_software_agent = _action_software_agent(action)
                    break
            if has_ai_assertion:
                break

    # Fallback 1: claim generator name keyword match (case-insensitive)
    if not has_ai_assertion and claim_generator_name:
        name_lower = claim_generator_name.lower()
        if any(kw in name_lower for kw in AI_GENERATOR_KEYWORDS):
            has_ai_assertion = True

    # Fallback 2: signature issuer matches a known AI signer
    # (low false-positive risk — these issuers sign their generative output)
    if not has_ai_assertion and _matches_ai_issuer(signature_issuer):
        has_ai_assertion = True

    return {
        "has_c2pa": True,
        "c2pa_valid": c2pa_valid,
        "validation_state": validation_state,
        "claim_generator_name": claim_generator_name,
        "signature_issuer": signature_issuer,
        "has_ai_assertion": has_ai_assertion,
        "ai_source_type": ai_source_type,
        "ai_software_agent": ai_software_agent,
        "raw_manifest": manifest_store,
        "error": None,
    }
