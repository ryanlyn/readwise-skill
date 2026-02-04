# Readwise Skill Plugin

Claude Code plugin providing two skills for automating Readwise workflows.

## Setup

1. Install dependencies: `uv sync --extra dev`
2. Set environment variable:
   - `READWISE_TOKEN` — single token for both the Readwise Original and Reader APIs

## Skills

- **readwise** — Readwise Original API: highlights, books, daily review exports
- **readwise-reader** — Readwise Reader API: documents, annotations, triage

Both skills use CLI scripts under `skills/*/scripts/` that handle authentication, retries, rate limits, pagination, and dry-run mode.

## Project structure

- `skills/readwise/` — Readwise Original skill (SKILL.md + CLI + API reference)
- `skills/readwise-reader/` — Readwise Reader skill (SKILL.md + CLI + API reference)
- `readwise_common/` — shared Python package (auth, HTTP, formatting, utilities)
- `tests/` — pytest suite with an in-memory Flask stub server
- `.claude-plugin/plugin.json` — plugin manifest

## Testing

```
uv sync --extra dev
uv run pytest tests/
```

Tests use a local stub server (`tests/stub_server/`) that mocks both APIs in-memory. No real API tokens needed.

## Conventions

- Use `--generated` flag (not manual `.generated` tags) when saving agent-produced content
- Use `--dry-run` before any write operation to preview the payload
- Prefer `--output json` for programmatic consumption, `--output markdown` for human-readable output
