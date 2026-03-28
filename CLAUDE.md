# Readwise Skill

Claude Code marketplace providing the `readwise` plugin for automating Readwise workflows.

## Scope

- Python development happens in `plugins/readwise/`.
- Prefer repo-local CLI paths over any installed plugin cache.

## Installation

In Claude Code:
```bash
/plugin marketplace add ryanlyn/readwise-skill
/plugin install readwise@readwise-skill
```

Then set `READWISE_TOKEN` (Readwise access token) as an environment variable or Claude Code secret.

## Development

Plugin source lives in `plugins/readwise/`.

```bash
cd plugins/readwise
uv sync --extra dev
uv run pytest -v
uv run python -m compileall skills/readwise skills/readwise-reader readwise_common
uv run ruff check --fix .
uv run ruff format .
```

- Normal `uv run pytest` runs the full test suite and enforces 100% coverage for `readwise_common`, `skills/readwise/scripts`, and `skills/readwise-reader/scripts`.
- `pytest` already starts the in-memory stub server from `tests/conftest.py`, so normal test runs do not need a separate server process.

## Local CLI workflows

Use local files when working in this repo:

```bash
cd plugins/readwise
uv run python skills/readwise/scripts/readwise_client.py --help
uv run python skills/readwise-reader/scripts/reader_client.py --help
```

- Both CLIs support global `--dry-run`, `--raw`, and `--token` options.
- Global options can appear anywhere in the command.

## Zip Distribution

Build standalone skill zips for agent harnesses such as Codex and OpenClaw:

```bash
uv run python scripts/build_skill_zips.py --clean
```

Run packaging verification:

```bash
bash scripts/verify_skill_zips.sh
```

- `scripts/verify_skill_zips.sh` builds the zip artifacts, unpacks them, runs `compileall`, and smoke-tests both CLIs with `--help`.
- Artifacts are written to `dist/zips/` as `readwise-<version>.zip` and `readwise-reader-<version>.zip`.
- CI publishes these zip artifacts on pushes to `main` after verification passes.

## Development Tips

- Shared code lives in `plugins/readwise/readwise_common/` for auth, HTTP retries, models, formatting utilities, and helpers.
- Models in `plugins/readwise/readwise_common/models.py` define Pydantic payloads for API requests and responses. Update these when adding new fields.
- CLI help text should include valid values for options like `books|articles|tweets|podcasts`. Agents read `--help` when unsure.
- `SKILL.md` is what agents see, so keep CLI examples and valid option values in sync with the actual code.

## Benchmarking

```bash
uv run python token_efficiency/run_benchmark.py --report token_efficiency/report.md
```

- Requires `OPENAI_API_KEY` and either `READWISE_TOKEN` or `READWISE_API_TOKEN`.
