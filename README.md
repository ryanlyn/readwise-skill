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

Then set `READWISE_TOKEN` as an environment variable or Claude Code secret.

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
