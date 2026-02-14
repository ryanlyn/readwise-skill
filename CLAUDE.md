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

## Zip distribution

Build standalone skill zips (for any agent harness — Codex, OpenClaw, etc.):

```bash
python3 scripts/build_skill_zips.py --clean
```

Run packaging verification (build + unzip + CLI startup checks):

```bash
scripts/verify_skill_zips.sh
```

Artifacts are written to `dist/zips/`:
- `readwise-<version>.zip`
- `readwise-reader-<version>.zip`

CI publishes these zip artifacts on pushes to `main` after verification passes.

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
- **Global options** (`--dry-run`, `--raw`) can appear anywhere in the command.
- **Format and lint** after making changes:
  ```bash
  uv run ruff check --fix . && uv run ruff format .
  ```
