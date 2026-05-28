from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from ai_verify.face_mask import FaceDetectionFailedError, mask_faces


@pytest.fixture()
def small_jpeg(tmp_path: Path) -> Path:
    img = Image.new("RGB", (200, 200), color=(180, 180, 180))
    path = tmp_path / "input.jpg"
    img.save(str(path), format="JPEG")
    return path


def _mock_detection(
    origin_x: int = 50,
    origin_y: int = 50,
    width: int = 100,
    height: int = 100,
) -> MagicMock:
    """Return a mock detection with absolute-pixel bounding box (Tasks API style)."""
    det = MagicMock()
    bbox = MagicMock()
    bbox.origin_x, bbox.origin_y, bbox.width, bbox.height = origin_x, origin_y, width, height
    det.bounding_box = bbox
    return det


def _patch_detector(detections: list | None):
    """Patch _build_detector to return a context-manager mock that yields controlled results."""
    mock_detector = MagicMock()
    mock_detector.__enter__ = MagicMock(return_value=mock_detector)
    mock_detector.__exit__ = MagicMock(return_value=False)

    mock_result = MagicMock()
    mock_result.detections = detections
    mock_detector.detect.return_value = mock_result

    return patch("ai_verify.face_mask._build_detector", return_value=mock_detector)


def test_raises_when_no_face_detected(small_jpeg: Path, tmp_path: Path) -> None:
    with _patch_detector(None):
        with pytest.raises(FaceDetectionFailedError):
            mask_faces(small_jpeg, tmp_path / "out.jpg")


def test_raises_when_empty_detections(small_jpeg: Path, tmp_path: Path) -> None:
    with _patch_detector([]):
        with pytest.raises(FaceDetectionFailedError):
            mask_faces(small_jpeg, tmp_path / "out.jpg")


def test_output_file_created(small_jpeg: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.jpg"
    with _patch_detector([_mock_detection()]):
        result = mask_faces(small_jpeg, out)
    assert out.exists()
    assert result["faces_detected"] == 1
    assert result["faces_masked"] == 1


def test_grey_fill_default(small_jpeg: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.jpg"
    with _patch_detector([_mock_detection()]):
        result = mask_faces(small_jpeg, out)
    assert result["fill"] == "grey"


def test_noise_fill(small_jpeg: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.jpg"
    with _patch_detector([_mock_detection()]):
        result = mask_faces(small_jpeg, out, fill="noise")
    assert result["fill"] == "noise"
    assert out.exists()


def test_image_size_returned(small_jpeg: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.jpg"
    with _patch_detector([_mock_detection()]):
        result = mask_faces(small_jpeg, out)
    assert result["image_size"] == [200, 200]


def test_output_path_in_result(small_jpeg: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.jpg"
    with _patch_detector([_mock_detection()]):
        result = mask_faces(small_jpeg, out)
    assert result["output_path"] == str(out)


def test_exif_stripped(small_jpeg: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.jpg"
    with _patch_detector([_mock_detection()]):
        mask_faces(small_jpeg, out)
    img = Image.open(out)
    assert not img.info.get("exif")


def test_invalid_input_path_raises(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        mask_faces(Path("/nonexistent/image.jpg"), tmp_path / "out.jpg")


def test_multiple_faces(small_jpeg: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.jpg"
    detections = [
        _mock_detection(10, 10, 40, 40),
        _mock_detection(120, 120, 40, 40),
    ]
    with _patch_detector(detections):
        result = mask_faces(small_jpeg, out)
    assert result["faces_detected"] == 2
    assert result["faces_masked"] == 2


def test_model_path_env_var_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_verify.face_mask import _resolve_model_path
    fake_model = tmp_path / "custom.tflite"
    fake_model.write_bytes(b"fake")
    monkeypatch.setenv("AI_VERIFY_MODEL_PATH", str(fake_model))
    assert _resolve_model_path() == fake_model
