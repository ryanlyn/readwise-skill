# readwise-skill

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) marketplace plugin for automating [Readwise](https://readwise.io) workflows — syncing highlights, managing documents, and streamlining your reading pipeline.

## Skills

- **readwise** — Readwise Original API: highlights, books, daily review exports
- **readwise-reader** — Readwise Reader API: documents, annotations, triage

Both skills provide CLI scripts that handle authentication, retries, rate limits, pagination, and dry-run mode.

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
