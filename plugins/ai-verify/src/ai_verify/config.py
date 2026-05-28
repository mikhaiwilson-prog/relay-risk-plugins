from pathlib import Path

DEFAULT_OUT_DIR: Path = Path.home() / ".ai-verify" / "runs"

AI_GENERATOR_KEYWORDS: list[str] = [
    "chatgpt",
    "openai",
    "dall-e",
    "dalle",
    "gpt-image",
    "firefly",
    "adobe generative",
    "midjourney",
    "stable diffusion",
    "imagen",
    "gemini",
    "ideogram",
    "leonardo",
    "flux",
    "comfyui",
    "automatic1111",
    "runway",
    "pika",
    "sora",
]

FACE_DETECTION_CONFIDENCE: float = 0.5
SLACK_WEBHOOK_ENV_VAR: str = "AI_VERIFY_SLACK_WEBHOOK"
