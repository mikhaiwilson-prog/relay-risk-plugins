# ai-verify

A Claude Code plugin that helps Relay trust-and-safety analysts decide whether
a submitted selfie is AI-generated. This is an assistive tool — it surfaces
signals; the analyst makes the final call.

The pipeline does the privacy-sensitive work locally (C2PA inspection + face
masking), then hands a paste-ready prompt to **Claude Desktop's Cowork mode**
for the browser-driven Gemini SynthID and OpenAI Verify checks.

Volume: ~20 images/day across ~5 analysts, each using their own personal
Google and OpenAI accounts.

## Install (via the Relay-Risk Plugins marketplace)

In Claude Code, run:

```
/plugin marketplace add mikhaiwilson-prog/relay-risk-plugins
/plugin install ai-verify@relay-risk-plugins
```

Restart Claude Code. The plugin contributes:
- `/ai-verify <image-path>` — slash command
- An `ai-verify` skill that orchestrates the pipeline
- An `ai-verify` MCP server exposing `check_image`, `merge_run`, `show_run`

The first time face masking runs, the tool downloads a ~230 KB BlazeFace
tflite model to `~/.ai-verify/models/`. Override the path with the
`AI_VERIFY_MODEL_PATH` env var.

## How it works

1. **Local C2PA check** — inspects the image's Content Credentials manifest for
   AI generation assertions. Deterministic and offline.
2. **Face masking** — uses MediaPipe to detect and mask all faces before any
   image leaves your machine.
3. **Cowork hand-off** — Claude Code prints a paste-ready prompt. You switch to
   Claude Desktop's Cowork mode, paste the prompt, and Cowork runs Gemini
   SynthID and OpenAI Verify in tabs you're signed into.
4. **Result merging** — paste the agent's returned JSON back into Claude Code;
   the plugin merges it with the local C2PA finding into a conservative verdict.

## Quickstart

In Claude Code:

```
/ai-verify ./selfie.jpg
```

The plugin will:
1. Run `check_image` locally (C2PA + face mask)
2. Print a prompt for you to paste into Claude Desktop → Cowork
3. After you return with the agent JSON, run `merge_run`
4. Show you the final verdict

### Manual / scripted use

```python
from ai_verify.mcp_server import check_image, merge_run

status = check_image(image_path="./selfie.jpg")
run_id = status["run_id"]

# Paste prompt.txt into Cowork, save agent JSON to agent_result.json

final = merge_run(run_id=run_id, agent_json_path="./agent_result.json")
print(final["overall_verdict"], final["reasoning"])
```

## Verdict reference

| Verdict | Confidence | Meaning |
|---|---|---|
| `ai_confirmed` | high | Strong AI signal — escalate |
| `ai_likely` | medium | One source flagged AI — senior review |
| `no_ai_signal` | low–medium | No signals found |
| `needs_manual_review` | low | Mixed signals |
| `incomplete` | low | A service was unavailable |

## Optional Slack notifications

Set `AI_VERIFY_SLACK_WEBHOOK` to a Slack incoming webhook URL and pass
`slack_notify=True` to `merge_run` to post the verdict to a channel.

## Limitations

**What this catches:**
- AI images that retain intact C2PA Content Credentials with an AI assertion
- Images flagged by Gemini SynthID (Google AI-generated content)
- Images flagged by OpenAI's Verify tool (DALL-E and other OpenAI generators)

**What this misses:**
- AI images whose C2PA metadata was stripped (most laundered or re-uploaded images)
- AI generators that don't embed C2PA and aren't covered by Gemini/OpenAI watermarks
- Images from older or niche AI models with no watermark support
- Images that have been heavily re-edited after generation

**This tool does not replace human judgment.** It surfaces signals for analysts
who make the final call.

## Terms of service note

Each analyst uses their own personal Google and OpenAI accounts for the Cowork
browser checks. This tool is for low-volume internal review only
(~20 images/day total). Review Google's and OpenAI's ToS before use; do not use
organizational or API accounts unless explicitly permitted.

## Development

Working on the plugin directly (no marketplace install):

```bash
git clone <repo>
cd ai-verify
pip install -e ".[dev]"
pytest                       # 45 tests
ruff check src tests
mypy src
```

To exercise the plugin locally in Claude Code, register the repo as a local
marketplace:

```
/plugin marketplace add /absolute/path/to/relay-risk-plugins
/plugin install ai-verify@relay-risk-plugins
```
