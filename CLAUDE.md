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

### Development tips

- **Use local files**: when working in this repo, always run CLIs from here rather than the installed plugin cache:
  ```bash
  uv run python skills/readwise-reader/scripts/reader_client.py docs list --help
  uv run python skills/readwise/scripts/readwise_client.py highlight create --help
  ```
- **Shared code** lives in `readwise_common/` — auth, HTTP retries, models, formatting utilities. Both skills import from here.
- **Models** (`readwise_common/models.py`) define Pydantic payloads for API requests/responses. Update these when adding new fields.
- **CLI help text** should include valid values for options (e.g. `books|articles|tweets|podcasts`). Agents read `--help` when unsure.
- **SKILL.md** is what agents see — keep CLI examples and valid option values in sync with the actual code.
- **Global options** (`--dry-run`, `--raw`) must come BEFORE the subcommand:
  ```bash
  # Correct
  ... --dry-run highlight create --text "..."

  # Wrong — will fail
  ... highlight create --text "..." --dry-run
  ```
- **Format and lint** after making changes:
  ```bash
  uv run ruff check --fix . && uv run ruff format .
  ```
