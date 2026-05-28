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
    "media service",  # OpenAI Media Service API
    "designer",  # Microsoft Designer / Image Creator
    "aurora",  # xAI Aurora
    "recraft",
    "nightcafe",
    "freepik",
    "magnific",
]

# IPTC digitalSourceType vocabulary values that indicate AI generation.
# Source: https://cv.iptc.org/newscodes/digitalsourcetype/
# We match by case-insensitive substring of the digitalSourceType IRI.
# Excludes "algorithmicMedia" (rule-based, not trained) and
# "algorithmicallyEnhanced" (debatable, would inflate false positives).
AI_DIGITAL_SOURCE_TYPES: list[str] = [
    "trainedAlgorithmicMedia",
    "compositeWithTrainedAlgorithmicMedia",
    "compositeSynthetic",
    "virtualRecording",
]

# Signature issuers known to sign C2PA manifests on AI-generated content.
# Match is case-insensitive substring. Used as a fallback signal AFTER
# assertion + keyword checks fail.
AI_SIGNATURE_ISSUERS: list[str] = [
    "openai opco",
    "adobe inc",
    "google llc",
    "stability ai",
    "black forest labs",
    "midjourney",
]

FACE_DETECTION_CONFIDENCE: float = 0.5
SLACK_WEBHOOK_ENV_VAR: str = "AI_VERIFY_SLACK_WEBHOOK"
