# readwise-skill

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) marketplace plugin for automating [Readwise](https://readwise.io) workflows — syncing highlights, managing documents, and streamlining your reading pipeline.

## What you can do

Your reading library meets your coding assistant. Capture insights as you work with Claude.

### Readwise

- **Save quotes** — paste text, ask Claude to save it to Readwise
- **Query your library** — "Find my highlights from Meditations tagged with stoicism"
- **Daily review** — "Show today's Readwise highlights" to spark reflection

### Reader

- **Save for later** — "Save this URL to Reader"
- **Check your inbox** — "What's new in my Reader inbox?"
- **Triage** — "Archive everything I finished reading this week"

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- A [Readwise](https://readwise.io) account and access token

## Installation

In Claude Code:

```
/plugin marketplace add ryanlyn/readwise-skill
/plugin install readwise@readwise-skill
```

After installing, you should see the `readwise` and `readwise-reader` skills listed when you run `/plugin list`. Try asking Claude: **"Show my Readwise books"** to confirm everything is working.

If the plugin doesn't load, check that:
- You ran both `/plugin marketplace add` and `/plugin install`
- Claude Code is up to date

## Setup

Get your Readwise access token from https://readwise.io/access_token, then set it as a Claude Code secret (recommended) or shell environment variable:

```
# Claude Code secret (persists across sessions)
/secrets set READWISE_TOKEN <your-token>

# Or shell environment variable
export READWISE_TOKEN=<your-token>
```

Your token is sent only to `readwise.io` API endpoints. It is not sent to the model provider or stored by the plugin.

## Verify your setup

Ask Claude: **"Validate my Readwise token"** — both skills support `auth validate` and will confirm your token is working.

## Development

Plugin source lives in `plugins/readwise/`.

```
cd plugins/readwise
uv sync --extra dev
uv run pytest tests/ -v
```

Tests use a local stub server that mocks both APIs in-memory — no real API token needed.

## License

[MIT](LICENSE)
