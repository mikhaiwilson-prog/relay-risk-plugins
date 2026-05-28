from __future__ import annotations

import string
from pathlib import Path


def _template_path() -> Path:
    """Resolve prompts/cowork_prompt.md relative to project root."""
    here = Path(__file__).resolve()
    # src/ai_verify/prompt_builder.py → up 3 levels to project root
    return here.parent.parent.parent / "prompts" / "cowork_prompt.md"


def build_prompt(
    masked_image_path: Path,
    original_filename: str,
    run_id: str,
    output_dir: Path,
) -> Path:
    """Render the Cowork prompt template and write it to output_dir/prompt.txt."""
    template_text = _template_path().read_text()
    template = string.Template(template_text)
    rendered = template.substitute(
        IMAGE_PATH=str(masked_image_path.absolute()),
        ORIGINAL_NAME=original_filename,
        RUN_ID=run_id,
    )
    prompt_path = output_dir / "prompt.txt"
    prompt_path.write_text(rendered)
    return prompt_path
