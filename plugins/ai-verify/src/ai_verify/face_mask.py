from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision.face_detector import FaceDetector, FaceDetectorOptions
from PIL import Image

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)
_MODEL_CACHE_DIR = Path.home() / ".ai-verify" / "models"
_MODEL_FILENAME = "blaze_face_short_range.tflite"


def _resolve_model_path() -> Path:
    """Return path to the BlazeFace tflite model, downloading on first use."""
    override = os.environ.get("AI_VERIFY_MODEL_PATH")
    if override:
        return Path(override)

    model_path = _MODEL_CACHE_DIR / _MODEL_FILENAME
    if model_path.exists():
        return model_path

    _MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    import urllib.request
    try:
        urllib.request.urlretrieve(_MODEL_URL, str(model_path))
    except Exception:
        # Fall back to curl when the system SSL trust store is not set up
        # (common on fresh macOS Python 3.x installs).
        import subprocess
        subprocess.run(
            ["curl", "-fsSL", "-o", str(model_path), _MODEL_URL],
            check=True,
        )

    return model_path


class FaceDetectionFailedError(Exception):
    """Raised when no faces are found — prevents sending unmasked image to remote service."""


def _build_detector(min_confidence: float) -> FaceDetector:
    """Construct a FaceDetector using the BlazeFace short-range tflite model."""
    opts = FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(_resolve_model_path())),
        min_detection_confidence=min_confidence,
    )
    return FaceDetector.create_from_options(opts)


def mask_faces(
    input_path: Path,
    output_path: Path,
    expand_pct: float = 0.15,
    fill: str = "grey",
    min_confidence: float = 0.5,
) -> dict[str, Any]:
    """
    Detect and mask all faces in the image.

    Raises FaceDetectionFailedError if no faces are detected.
    Output is JPEG quality 95 with EXIF stripped.
    """
    pil_input = Image.open(str(input_path))
    img_rgb = np.array(pil_input.convert("RGB"))
    h, w = img_rgb.shape[:2]

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)

    with _build_detector(min_confidence) as detector:
        result = detector.detect(mp_image)

    detections = result.detections
    if not detections:
        raise FaceDetectionFailedError(
            f"No faces detected in '{input_path}' "
            f"(min_confidence={min_confidence}). "
            "Refusing to send unmasked image to a remote service."
        )

    masked = img_rgb.copy()
    for detection in detections:
        bbox = detection.bounding_box
        bx, by, bw, bh = bbox.origin_x, bbox.origin_y, bbox.width, bbox.height

        x1 = int(bx - expand_pct * bw)
        y1 = int(by - expand_pct * bh)
        x2 = int(bx + bw * (1 + expand_pct))
        y2 = int(by + bh * (1 + expand_pct))

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        region_h, region_w = y2 - y1, x2 - x1
        if region_h <= 0 or region_w <= 0:
            continue

        if fill == "grey":
            masked[y1:y2, x1:x2] = 128
        elif fill == "black":
            masked[y1:y2, x1:x2] = 0
        elif fill == "noise":
            masked[y1:y2, x1:x2] = np.random.randint(
                0, 256, (region_h, region_w, 3), dtype=np.uint8
            )

    pil_out = Image.fromarray(masked)
    pil_out.save(str(output_path), format="JPEG", quality=95)

    return {
        "faces_detected": len(detections),
        "faces_masked": len(detections),
        "image_size": [w, h],
        "fill": fill,
        "output_path": str(output_path),
    }
