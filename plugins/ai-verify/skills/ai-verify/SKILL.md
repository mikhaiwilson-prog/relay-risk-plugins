---
name: ai-verify
description: >
  Runs the full AI image verification pipeline for trust-and-safety analysts.
  Use when an analyst wants to check whether a submitted selfie is AI-generated.
  Triggers on: "check this image for AI", "verify this selfie",
  "is this AI-generated", "/ai-verify <path>".
---

# AI Image Verification

You are assisting a trust-and-safety analyst in determining whether a submitted
selfie is AI-generated. This is an assistive tool — you surface signals, the
analyst makes the final call.

**False positives are very costly.** When signals are ambiguous, say so clearly
rather than leaning toward "AI". A wrong AI verdict could lock out a real user.

The browser checks happen in the analyst's Claude Desktop app under Cowork mode,
not here in Claude Code. This skill orchestrates the local pipeline and the
hand-off across both surfaces.

## Step 1 — Run the local pipeline

Call the `check_image` MCP tool:

```
check_image(image_path="<path the analyst provided>")
```

Report back:
- C2PA result (has manifest? AI assertion found?)
- Whether face masking succeeded (if not, explain why and stop — never proceed
  to remote checks with an unmasked face)
- The `run_id` (analyst needs this for Step 3)
- The `prompt_path` (analyst needs this for Step 2)

If face masking failed with `FaceDetectionFailedError`, tell the analyst:
"No face was detected in this image. The tool requires a clear face to mask
before sending to remote services. Please verify the image is a selfie."

## Step 2 — Hand off to Cowork

Tell the analyst:

> "Local checks complete. To run the Gemini SynthID and OpenAI Verify checks,
> open the Claude Desktop app, switch to Cowork, and paste the contents of:
>
> `<prompt_path from check_image result>`
>
> Make sure your Cowork tab group has gemini.google.com and openai.com/index/verify
> available (or let Cowork open them). Drag the masked image at `<masked path>`
> into the tab group so Cowork can upload it. When Cowork returns the JSON result,
> save it locally and come back with the path (or paste the JSON inline)."

Display the prompt content inline so the analyst can copy it easily.

## Step 3 — Merge results

When the analyst returns with the agent JSON (as a file path or pasted inline):

If pasted inline: write it to `<run_dir>/agent_result.json` first, then call:

```
merge_run(run_id="<run_id>", agent_json_path="<path to agent JSON>")
```

## Step 4 — Present the final verdict

Format the verdict clearly:

| Verdict | Emoji | Meaning |
|---|---|---|
| `ai_confirmed` | 🤖 | Strong AI signal — escalate |
| `ai_likely` | ⚠️ | One source flagged AI — senior review |
| `no_ai_signal` | ✅ | No AI signals found |
| `needs_manual_review` | ❓ | Mixed signals — additional context needed |
| `incomplete` | ⏸️ | A service was unavailable — re-run recommended |

Always include:
- The `reasoning` field verbatim
- Which signals fired (`signals.c2pa_local`, `signals.gemini`, `signals.openai`)
- The `run_id` so the analyst can reference it in their notes
- Confidence level

## Rules

- Never make an AI determination without running at least the local C2PA check.
- Never send an unmasked image to remote services — `check_image` enforces this,
  but remind the analyst if they try to skip masking with `no_mask=True`.
- If both remote services are unavailable, return `incomplete` — do not guess.
- Always show the analyst the raw `reasoning` from `merge_run`.
