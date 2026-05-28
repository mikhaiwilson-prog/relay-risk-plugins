import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from ai_verify.c2pa_check import check_c2pa

EXPECTED_KEYS = {
    "has_c2pa", "c2pa_valid", "validation_state", "claim_generator_name",
    "signature_issuer", "has_ai_assertion", "ai_source_type",
    "ai_software_agent", "raw_manifest", "error",
}


@pytest.fixture()
def plain_jpeg(tmp_path: Path) -> Path:
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    path = tmp_path / "test.jpg"
    img.save(str(path), format="JPEG")
    return path


def test_return_shape(plain_jpeg: Path) -> None:
    result = check_c2pa(plain_jpeg)
    assert set(result.keys()) == EXPECTED_KEYS


def test_plain_jpeg_has_no_c2pa(plain_jpeg: Path) -> None:
    result = check_c2pa(plain_jpeg)
    assert result["has_c2pa"] is False
    assert result["error"] is None


def test_plain_jpeg_no_ai_assertion(plain_jpeg: Path) -> None:
    result = check_c2pa(plain_jpeg)
    assert result["has_ai_assertion"] is False


def test_plain_jpeg_validation_fields_are_none(plain_jpeg: Path) -> None:
    result = check_c2pa(plain_jpeg)
    assert result["c2pa_valid"] is None
    assert result["validation_state"] is None
    assert result["raw_manifest"] is None


def test_nonexistent_file_returns_error() -> None:
    result = check_c2pa(Path("/nonexistent/image.jpg"))
    assert result["error"] is not None
    assert result["has_c2pa"] is False


def _mock_reader_with_manifest(manifest_store: dict):
    """Returns a mock c2pa.Reader that yields the given manifest_store."""
    mock_reader = MagicMock()
    mock_reader.json.return_value = json.dumps(manifest_store)
    return mock_reader


def _patch_try_create(manifest_store: dict | None):
    """Context manager that patches c2pa.Reader.try_create."""
    if manifest_store is None:
        return patch("c2pa.Reader.try_create", return_value=None)
    return patch("c2pa.Reader.try_create", return_value=_mock_reader_with_manifest(manifest_store))


def test_ai_assertion_via_digital_source_type(plain_jpeg: Path) -> None:
    manifest = {
        "active_manifest": "urn:test:m1",
        "manifests": {
            "urn:test:m1": {
                "validation_status": [],
                "claim_generator_info": [{"name": "TestApp"}],
                "signature_info": {"issuer": "Test CA"},
                "assertions": [
                    {
                        "label": "c2pa.actions",
                        "data": {
                            "actions": [
                                {
                                    "digitalSourceType": "trainedAlgorithmicMedia",
                                    "softwareAgent": {"name": "TestGenAI"},
                                }
                            ]
                        },
                    }
                ],
            }
        },
    }
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["has_c2pa"] is True
    assert result["has_ai_assertion"] is True
    assert result["ai_source_type"] == "trainedAlgorithmicMedia"
    assert result["ai_software_agent"] == "TestGenAI"


def test_composite_ai_source_type_detected(plain_jpeg: Path) -> None:
    manifest = {
        "active_manifest": "urn:test:m1",
        "manifests": {
            "urn:test:m1": {
                "validation_status": [],
                "claim_generator_info": [],
                "signature_info": {},
                "assertions": [
                    {
                        "label": "c2pa.actions",
                        "data": {
                            "actions": [
                                {"digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia"}
                            ]
                        },
                    }
                ],
            }
        },
    }
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["has_ai_assertion"] is True


def test_ai_assertion_via_keyword_fallback(plain_jpeg: Path) -> None:
    manifest = {
        "active_manifest": "urn:test:m1",
        "manifests": {
            "urn:test:m1": {
                "validation_status": [],
                "claim_generator_info": [{"name": "Midjourney v6"}],
                "signature_info": {},
                "assertions": [],
            }
        },
    }
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["has_ai_assertion"] is True
    assert result["claim_generator_name"] == "Midjourney v6"


def test_c2pa_present_no_ai_assertion(plain_jpeg: Path) -> None:
    manifest = {
        "active_manifest": "urn:test:m1",
        "manifests": {
            "urn:test:m1": {
                "validation_status": [],
                "claim_generator_info": [{"name": "Camera App"}],
                "signature_info": {"issuer": "Camera Vendor"},
                "assertions": [
                    {
                        "label": "c2pa.actions",
                        "data": {
                            "actions": [{"action": "c2pa.created"}]
                        },
                    }
                ],
            }
        },
    }
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["has_c2pa"] is True
    assert result["has_ai_assertion"] is False
    assert result["c2pa_valid"] is True
    assert result["claim_generator_name"] == "Camera App"
    assert result["signature_issuer"] == "Camera Vendor"


def test_empty_active_manifest_label_is_error(plain_jpeg: Path) -> None:
    manifest = {"active_manifest": "", "manifests": {}}
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["error"] is not None
    assert "Malformed" in result["error"] or "empty" in result["error"].lower()


# ── Regression tests for the lala.png false negative ─────────────────────

def _ai_actions_manifest(label: str, dst: str, sw_name: str = "gpt-image") -> dict:
    """Build a manifest with the given actions label + digitalSourceType."""
    return {
        "active_manifest": "urn:test:m1",
        "manifests": {
            "urn:test:m1": {
                "validation_status": [],
                "claim_generator_info": [{"name": "Generic Camera"}],
                "signature_info": {"issuer": "Some CA"},
                "assertions": [
                    {
                        "label": label,
                        "data": {
                            "actions": [
                                {
                                    "action": "c2pa.created",
                                    "digitalSourceType": dst,
                                    "softwareAgent": {"name": sw_name},
                                }
                            ]
                        },
                    }
                ],
            }
        },
    }


def test_c2pa_actions_v2_label_detected(plain_jpeg: Path) -> None:
    """Regression: lala.png used label `c2pa.actions.v2`, not `c2pa.actions`."""
    manifest = _ai_actions_manifest(
        "c2pa.actions.v2",
        "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    )
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["has_ai_assertion"] is True
    assert result["ai_source_type"] == (
        "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
    )
    assert result["ai_software_agent"] == "gpt-image"


def test_future_c2pa_actions_v3_label_detected(plain_jpeg: Path) -> None:
    """Prefix match: future v3+ labels should still work."""
    manifest = _ai_actions_manifest(
        "c2pa.actions.v3",
        "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    )
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["has_ai_assertion"] is True


def test_digital_source_type_in_parameters_detected(plain_jpeg: Path) -> None:
    """Photoshop/Firefly nest digitalSourceType under action.parameters."""
    manifest = {
        "active_manifest": "urn:test:m1",
        "manifests": {
            "urn:test:m1": {
                "validation_status": [],
                "claim_generator_info": [{"name": "Adobe Photoshop"}],
                "signature_info": {},
                "assertions": [
                    {
                        "label": "c2pa.actions.v2",
                        "data": {
                            "actions": [
                                {
                                    "action": "c2pa.created",
                                    "parameters": {
                                        "digitalSourceType": (
                                            "http://cv.iptc.org/newscodes/"
                                            "digitalsourcetype/"
                                            "compositeWithTrainedAlgorithmicMedia"
                                        ),
                                        "softwareAgent": "Firefly",
                                    },
                                }
                            ]
                        },
                    }
                ],
            }
        },
    }
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["has_ai_assertion"] is True
    assert result["ai_software_agent"] == "Firefly"


def test_composite_synthetic_iptc_value_detected(plain_jpeg: Path) -> None:
    manifest = _ai_actions_manifest(
        "c2pa.actions.v2",
        "http://cv.iptc.org/newscodes/digitalsourcetype/compositeSynthetic",
    )
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["has_ai_assertion"] is True


def test_signature_issuer_fallback_openai(plain_jpeg: Path) -> None:
    """If assertions and generator name both miss, OpenAI issuer alone flips it."""
    manifest = {
        "active_manifest": "urn:test:m1",
        "manifests": {
            "urn:test:m1": {
                "validation_status": [],
                "claim_generator_info": [{"name": "Some Anonymous Generator"}],
                "signature_info": {"issuer": "OpenAI OpCo, LLC"},
                "assertions": [],
            }
        },
    }
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["has_ai_assertion"] is True
    assert result["signature_issuer"] == "OpenAI OpCo, LLC"


def test_signature_issuer_unknown_does_not_flip(plain_jpeg: Path) -> None:
    """Unknown issuer + no other AI signal → no false positive."""
    manifest = {
        "active_manifest": "urn:test:m1",
        "manifests": {
            "urn:test:m1": {
                "validation_status": [],
                "claim_generator_info": [{"name": "Nikon Camera"}],
                "signature_info": {"issuer": "Nikon Corp."},
                "assertions": [
                    {"label": "c2pa.actions.v2", "data": {"actions": [{"action": "c2pa.created"}]}}
                ],
            }
        },
    }
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["has_ai_assertion"] is False


def test_lowercase_dst_substring_match(plain_jpeg: Path) -> None:
    """A producer that lowercases or stylizes the DST URL should still match."""
    manifest = _ai_actions_manifest(
        "c2pa.actions.v2",
        "http://example.com/synthetic/TRAINEDALGORITHMICMEDIA",
    )
    with _patch_try_create(manifest):
        result = check_c2pa(plain_jpeg)
    assert result["has_ai_assertion"] is True
