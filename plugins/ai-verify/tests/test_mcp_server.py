"""
Guardrail tests for check_image.

These verify the privacy contract: when face detection fails, no image
artifact is produced, and the unmasked original is never copied or
exposed in the return value.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from ai_verify.face_mask import FaceDetectionFailedError
from ai_verify.mcp_server import check_image


@pytest.fixture()
def plain_jpeg(tmp_path: Path) -> Path:
    img = Image.new("RGB", (200, 200), color=(180, 180, 180))
    path = tmp_path / "input.jpg"
    img.save(str(path), format="JPEG")
    return path


def test_check_image_signature_has_no_no_mask_param() -> None:
    """The no_mask escape hatch must not exist — masking is mandatory."""
    import inspect
    sig = inspect.signature(check_image)
    assert "no_mask" not in sig.parameters


def test_face_detection_failure_returns_no_image_artifacts(
    plain_jpeg: Path, tmp_path: Path
) -> None:
    """When masking fails, no masked file, no downloads copy, no URLs."""
    with patch(
        "ai_verify.mcp_server.mask_faces",
        side_effect=FaceDetectionFailedError("no face"),
    ):
        result = check_image(str(plain_jpeg), out_dir=str(tmp_path))

    assert result["mask"] is None
    assert result["mask_error"] is not None
    assert "no face" in result["mask_error"]
    assert result["downloads_path"] is None
    assert result["manual_check_urls"] is None
    assert result["artifacts"]["masked"] is None
    assert result["artifacts"]["downloads_copy"] is None


def test_return_value_never_exposes_original_path(
    plain_jpeg: Path, tmp_path: Path
) -> None:
    """The original image path must not appear in artifacts."""
    mock_mask = MagicMock(
        return_value={
            "faces_detected": 1,
            "faces_masked": 1,
            "image_size": [200, 200],
            "fill": "grey",
            "output_path": str(tmp_path / "fake-masked.jpg"),
        }
    )
    with patch("ai_verify.mcp_server.mask_faces", mock_mask):
        # Touch a fake masked file so downstream copy_to_downloads works
        (tmp_path / "fake-masked.jpg").write_bytes(b"x")
        with patch("ai_verify.mcp_server._DOWNLOADS_DIR", tmp_path / "nope"):
            result = check_image(str(plain_jpeg), out_dir=str(tmp_path))

    assert "original" not in result["artifacts"]


def test_run_dir_does_not_contain_original_copy(
    plain_jpeg: Path, tmp_path: Path
) -> None:
    """Even after a successful run, the original is never copied to run_dir."""
    mock_mask = MagicMock(
        return_value={
            "faces_detected": 1,
            "faces_masked": 1,
            "image_size": [200, 200],
            "fill": "grey",
            "output_path": "",
        }
    )

    def write_fake_masked(_inp: Path, out: Path, **_kw: object) -> dict:
        out.write_bytes(b"masked")
        return mock_mask.return_value

    with patch("ai_verify.mcp_server.mask_faces", side_effect=write_fake_masked):
        with patch("ai_verify.mcp_server._DOWNLOADS_DIR", tmp_path / "nope"):
            result = check_image(str(plain_jpeg), out_dir=str(tmp_path))

    run_dir = Path(result["run_dir"])
    # Only the masked image, c2pa.json, and status.json should be in run_dir.
    files = sorted(p.name for p in run_dir.iterdir())
    assert "masked.jpg" in files
    assert "c2pa.json" in files
    assert "status.json" in files
    # No original copy at all
    assert not any(f.startswith("original") for f in files), (
        f"Privacy guardrail violated: original copy in run_dir: {files}"
    )


def test_ai_confirmed_skips_masking(plain_jpeg: Path, tmp_path: Path) -> None:
    """When C2PA confirms AI, mask is skipped and no image artifact is produced."""
    ai_c2pa = {
        "has_c2pa": True,
        "c2pa_valid": True,
        "validation_state": "valid",
        "claim_generator_name": "OpenAI Media Service API",
        "signature_issuer": "OpenAI OpCo, LLC",
        "has_ai_assertion": True,
        "ai_source_type": "trainedAlgorithmicMedia",
        "ai_software_agent": "gpt-image",
        "raw_manifest": {},
        "error": None,
    }
    mask_called = MagicMock()
    with patch("ai_verify.mcp_server.check_c2pa", return_value=ai_c2pa), \
         patch("ai_verify.mcp_server.mask_faces", side_effect=mask_called):
        result = check_image(str(plain_jpeg), out_dir=str(tmp_path))

    mask_called.assert_not_called()
    assert result["mask"] is None
    assert result["mask_error"] is None
    assert result["mask_skipped_reason"]
    assert "AI confirmed" in result["mask_skipped_reason"]
    assert result["downloads_path"] is None
    assert result["manual_check_urls"] is None
    assert result["artifacts"]["masked"] is None

    run_dir = Path(result["run_dir"])
    # No masked.jpg produced
    assert not (run_dir / "masked.jpg").exists()
