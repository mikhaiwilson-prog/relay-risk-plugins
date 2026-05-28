---
description: Run the AI image verification pipeline on a selfie (C2PA → mask → Cowork prompt → merge verdict)
argument-hint: <image-path>
---

Run the `ai-verify` skill on the image at `$1`.

Follow the skill's four-step protocol: local C2PA + face mask, then hand the rendered prompt to the analyst for Cowork, then merge the agent's returned JSON into a final verdict. Report each step's outcome to the analyst as you go.
