# Relay-Risk Plugins

Internal Claude Code plugin marketplace for Relay's risk and trust-and-safety
tooling.

## Use it

In Claude Code:

```
/plugin marketplace add relayfi/relay-risk-plugins
/plugin list
/plugin install <plugin-name>@relay-risk-plugins
```

## Plugins

| Name | Description |
|---|---|
| `ai-verify` | Assistive AI-image verification pipeline (local C2PA + face masking + Cowork hand-off to Gemini SynthID and OpenAI Verify). Source: [relayfi/ai-verify](https://github.com/relayfi/ai-verify) |

## Adding a plugin

1. Create a separate repo under the `relayfi/` GitHub org with a top-level
   `.claude-plugin/plugin.json` and the plugin's directory layout
   (`commands/`, `skills/`, `mcp-servers/`, etc.).
2. Add an entry to `.claude-plugin/marketplace.json` in this repo.
3. Open a PR. After merge, `/plugin marketplace update relay-risk-plugins`
   in Claude Code will surface the new plugin to the team.
