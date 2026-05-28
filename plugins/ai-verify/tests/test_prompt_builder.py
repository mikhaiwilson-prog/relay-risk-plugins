from __future__ import annotations

from pathlib import Path

import pytest

from ai_verify.prompt_builder import build_prompt


@pytest.fixture()
def run_setup(tmp_path: Path) -> dict:
    masked = tmp_path / "masked.jpg"
    masked.write_bytes(b"fake jpeg")
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    return {"masked": masked, "out_dir": out_dir}


def test_prompt_file_created(run_setup: dict) -> None:
    path = build_prompt(
        masked_image_path=run_setup["masked"],
        original_filename="selfie.jpg",
        run_id="20260528-120000-abc123",
        output_dir=run_setup["out_dir"],
    )
    assert path.exists()
    assert path.name == "prompt.txt"


def test_variables_substituted(run_setup: dict) -> None:
    path = build_prompt(
        masked_image_path=run_setup["masked"],
        original_filename="selfie.jpg",
        run_id="20260528-120000-abc123",
        output_dir=run_setup["out_dir"],
    )
    text = path.read_text()
    assert str(run_setup["masked"].absolute()) in text
    assert "selfie.jpg" in text
    assert "20260528-120000-abc123" in text


def test_no_unsubstituted_placeholders(run_setup: dict) -> None:
    path = build_prompt(
        masked_image_path=run_setup["masked"],
        original_filename="photo.png",
        run_id="20260528-120000-def456",
        output_dir=run_setup["out_dir"],
    )
    text = path.read_text()
    assert "${IMAGE_PATH}" not in text
    assert "${ORIGINAL_NAME}" not in text
    assert "${RUN_ID}" not in text


def test_returns_path_object(run_setup: dict) -> None:
    result = build_prompt(
        masked_image_path=run_setup["masked"],
        original_filename="img.jpg",
        run_id="abc",
        output_dir=run_setup["out_dir"],
    )
    assert isinstance(result, Path)
