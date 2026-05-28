# ai-verify

A Claude Code plugin that helps Relay trust-and-safety analysts decide whether
a submitted selfie is AI-generated. This is an assistive tool — it surfaces
signals; the analyst makes the final call.

The pipeline does all the work locally (C2PA inspection + face masking) and
gives the analyst a verdict card. If the local check is inconclusive, the
card points the analyst at two manual cross-check URLs they can hit in their
own browser.

Volume: ~20 images/day across ~5 analysts.

## Install (via the Relay-Risk Plugins marketplace)

**Step 1** — install Python dependencies (once per machine):

```bash
pip install c2pa-python mediapipe opencv-python pillow requests mcp
```

**Step 2** — in Claude Code, add the marketplace and install the plugin:

```
/plugin marketplace add mikhaiwilson-prog/relay-risk-plugins
/plugin install ai-verify@relay-risk-plugins
```

Restart Claude Code. The plugin contributes:
- `/ai-verify <image-path>` — slash command
- An `ai-verify` skill that runs the pipeline and presents the verdict
- An `ai-verify` MCP server exposing `check_image`, `merge_run`, `show_run`

The first time face masking runs, the tool downloads a ~230 KB BlazeFace
tflite model to `~/.ai-verify/models/`. Override the path with the
`AI_VERIFY_MODEL_PATH` env var.

## How it works

1. **Local C2PA check** — inspects the image's Content Credentials manifest
   for AI generation assertions. Deterministic, offline. This is the strongest
   signal we have for AI images that haven't had their metadata stripped.
2. **Face masking** — uses MediaPipe to detect and mask all faces. A masked
   copy lands at `~/Downloads/ai-verify-<run_id>.jpg` for easy upload to
   remote services if needed.
3. **Verdict card** — the skill summarizes the C2PA result and either:
   - Confirms AI (when C2PA says so),
   - Confirms clean provenance (when C2PA is signed and AI-free), or
   - Tells the analyst the local check is inconclusive and points them at
     the two manual cross-check URLs.
4. **Optional manual cross-check** — if the analyst chooses to verify at
   Gemini SynthID and/or OpenAI Verify, they paste the findings back as
   JSON and run `merge_run` to record a combined verdict.

No browser automation. The analyst handles the (rare) remote check in their
own signed-in browser, on their own time.

## Quickstart

In Claude Code:

```
/ai-verify ./selfie.jpg
```

The plugin will:
1. Run `check_image` locally (C2PA + face mask)
2. Print a verdict card with the result
3. If inconclusive, point you at the two manual-check URLs

If you do a manual remote check and want to record it:

```
merge_run(run_id="<run_id>", agent_json_path="<path-to-findings.json>")
```

### Manual / scripted use

```python
from ai_verify.mcp_server import check_image, merge_run

status = check_image(image_path="./selfie.jpg")

if status["c2pa"]["has_ai_assertion"]:
    print("AI confirmed via C2PA")
else:
    print("Local check inconclusive; check manually at:")
    print(status["manual_check_urls"])
    # ...later, after manual check:
    # final = merge_run(run_id=status["run_id"], agent_json_path="...")
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

**What this catches reliably (local C2PA):**
- ChatGPT / DALL-E images (OpenAI signs C2PA into all generated images)
- Adobe Firefly images (Adobe signs C2PA)
- Other generators that ship intact C2PA Content Credentials

**What this misses (and the manual cross-check helps with):**
- AI images whose C2PA was stripped (re-uploaded, re-encoded, re-edited)
- Google AI images with SynthID but no C2PA (Gemini SynthID covers this)
- Generators that don't embed any provenance at all

**This tool does not replace human judgment.** It surfaces signals for
analysts who make the final call.

## Terms of service note

When the local check is inconclusive and an analyst chooses to cross-check
remotely, they do so in their own browser using their own personal Google /
OpenAI account. This plugin does not automate access to those services.

## Development

Working on the plugin directly (no marketplace install):

```bash
git clone <repo>
cd ai-verify
pip install -e ".[dev]"
pytest                       # ~40 tests
ruff check src tests
mypy src
```
