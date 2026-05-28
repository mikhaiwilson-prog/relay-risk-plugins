---
name: ai-verify
description: >
  Runs local AI-image verification (C2PA + face masking) for trust-and-safety
  analysts. Use when an analyst wants to check whether a submitted selfie is
  AI-generated. Triggers on: "check this image for AI", "verify this selfie",
  "is this AI-generated", "/ai-verify <path>".
---

# AI Image Verification

You are assisting a trust-and-safety analyst in determining whether a submitted
selfie is AI-generated. This is an assistive tool — you surface signals, the
analyst makes the final call.

**False positives are very costly.** When signals are ambiguous, say so clearly
rather than leaning toward "AI". A wrong AI verdict could lock out a real user.

The remote verification services (Gemini SynthID, OpenAI Verify) are no longer
driven automatically — Cowork can't reliably reach them. Instead, the analyst
checks them manually in their own browser if local C2PA is inconclusive.

## Step 1 — Run the local pipeline

Call the `check_image` MCP tool:

```
check_image(image_path="<path the analyst provided>")
```

This performs C2PA manifest inspection (offline, deterministic) and face
masking with MediaPipe. A masked copy is dropped at
`~/Downloads/ai-verify-<run_id>.jpg` so the analyst can easily upload it later.

If face masking fails with `FaceDetectionFailedError`, tell the analyst:
"No face was detected. The tool requires a clear face to mask before any
manual remote check. Verify the image is a selfie."

## Step 2 — Present the verdict card

Based on the C2PA result, give the analyst ONE of three responses.

### Branch A: C2PA found an AI assertion (`has_ai_assertion=True`)

> 🤖 **AI confirmed by C2PA provenance**
> - Generator: `<claim_generator_name>`
> - Source type: `<ai_source_type>`
> - Signed by: `<signature_issuer>`
> - Run ID: `<run_id>`
>
> High confidence. No manual remote check needed — OpenAI Verify reads
> the same C2PA chunk we just parsed.

### Branch B: C2PA found valid provenance with NO AI assertion

> ✅ **Local C2PA is clean — no AI signal**
> - Signed by: `<signature_issuer>`
> - Run ID: `<run_id>`
>
> Strong evidence this is not AI. For an additional cross-check, upload the
> masked image at `~/Downloads/ai-verify-<run_id>.jpg` to either:
> - https://gemini.google.com — ask: "use SynthID verification on this image"
> - https://openai.com/research/verify
>
> If both come back clean, you're done. If either flags AI, run `merge_run`
> with the findings to record the final verdict.

### Branch C: No C2PA manifest (`has_c2pa=False`)

> ⏸️ **C2PA absent — local check inconclusive**
> - Run ID: `<run_id>`
>
> The image has no Content Credentials. This is normal for many cameras and
> for downstream-edited images, so absence is **not evidence of AI**.
> Recommend a manual remote check using the masked image at
> `~/Downloads/ai-verify-<run_id>.jpg`:
> - https://gemini.google.com — ask: "use SynthID verification on this image"
> - https://openai.com/research/verify
>
> Come back with what they showed and run `merge_run` if you want to record
> the verdict.

## Step 3 — Optional: record manual findings

If the analyst returns with findings from Gemini and/or OpenAI Verify, write
them to a JSON file (or build it inline):

```json
{
  "run_id": "<run_id>",
  "image": "<original filename>",
  "gemini": {"verdict": "ai_google" | "no_google_ai" | "...", "raw_response": "..."},
  "openai": {"verdict": "ai_detected" | "no_signal" | "...", "raw_response": "..."}
}
```

Then call:

```
merge_run(run_id="<run_id>", agent_json_path="<path>")
```

This combines local + manual findings into a final verdict.

## Verdict reference

| Verdict | Emoji | Meaning |
|---|---|---|
| `ai_confirmed` | 🤖 | Strong AI signal — escalate |
| `ai_likely` | ⚠️ | One source flagged AI — senior review |
| `no_ai_signal` | ✅ | No AI signals found |
| `needs_manual_review` | ❓ | Mixed signals — additional context needed |
| `incomplete` | ⏸️ | A service was unavailable — re-run recommended |

Always show the `reasoning` field verbatim when presenting a `merge_run` verdict.

## Rules

- Never make an AI determination without running at least the local C2PA check.
- Never send an unmasked image to remote services — `check_image` enforces this.
  Remind the analyst if they try to skip masking with `no_mask=True`.
- C2PA absence is **not** evidence of AI. Most legitimate photos lack C2PA too.
- Always show the reasoning behind your verdict.
