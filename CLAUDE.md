# Readwise Skill

Claude Code marketplace providing the `readwise` plugin for automating Readwise workflows.

## Installation

In Claude Code:
```
/plugin marketplace add ryanlyn/readwise-skill
/plugin install readwise@readwise-skill
```

Then set `READWISE_TOKEN` (Readwise access token) as an environment variable or Claude Code secret.

## Development

Plugin source lives in `plugins/readwise/`.

```
cd plugins/readwise
uv sync --extra dev
uv run pytest tests/ -v
```
