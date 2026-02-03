---
name: readwise
description: "Interact with the Readwise Original API for syncing highlights, exporting notes, and managing books/authors. Use whenever tasks require the legacy Readwise endpoints (not the Reader app)."
---

# Readwise Original Skill

Use this skill to automate work with the Readwise "Original" API that powers highlight exports and metadata management. Run `pip install -r requirements.txt` once so the bundled CLI scripts have `requests` available.

## Quick start
1. Obtain a personal Readwise token and store it in the `READWISE_TOKEN` secret.
2. Use `python scripts/readwise_client.py ...` instead of calling the API directly; it handles retries, pagination, rate-limit surfacing, `--dry-run`, and tagging rules.
3. Keep requests below the documented rate limit (currently 60 req/min). Batch operations and pause between pages when processing large libraries.

## CLI commands
- `python scripts/readwise_client.py highlight create --text ... [--generated] [--tags t1,t2] [--dry-run]`  
  Creates a highlight or batch (`--bulk-file ndjson`). If `--generated` is set, `.generated` is appended to tags and `location_type` defaults to `none`.
- `... highlight update <id> [--title --note --tags --generated]` – partial updates, respects `--dry-run`.
- `... highlight delete <id> [--yes]` – prompts before deleting unless `--yes`.
- `... highlight show <id>` – fetch highlight details.
- `... highlights list --book-id 123 --tag focus --updated-after 2026-02-01` – cursor-based listing with optional limit + output format (`--output json|markdown|plain`).
- `... highlights review --since 2026-02-01` – wraps the daily review/export endpoint and returns JSON you can render to Markdown/CSV upstream.
- `... books list [--author]` and `... book <id>` – inspect Readwise book metadata for deduping or highlight filtering.

## Data entry guidance
- **Generated snippets**: prefer the explicit `--generated` flag rather than manual tagging. The CLI injects `.generated` for discoverability and leaves other metadata untouched.
- **Highlight text**: supply `--text`, `--text-file`, or pipe content via stdin. The CLI refuses to guess. Bulk imports accept NDJSON rows with `text`, `title`, and `tags`.
- **Location best practices**: omit `--location` unless you can provide an absolute, client-agnostic reference (page number, character offset). When `--location` is omitted the payload leaves `location` blank so Readwise can reconcile it later. For generated quotes the CLI defaults to `location_type=none`.
- **Dry runs**: add `--dry-run` to print the exact JSON payload without calling the API. Useful when iterating on agent prompts.

## Scripts
- `scripts/readwise_client.py`: full-featured CLI covering highlight CRUD, daily review, and books list/detail. Commands surface remaining rate-limit headers when provided so agents can throttle work.
- Shared helpers live in `rw_shared/` (auth, HTTP retries, tag/location utilities); import from there when extending functionality to keep behavior consistent.

## References
- `references/api.md`: mirrors endpoints, parameters, and payload schemas that evolve faster than this SKILL.
- Add more references (e.g., sample responses) as flows become concrete.

## Testing & validation
- Use the dry-run flag in the client to print payloads instead of sending them when iterating on workflows.
- Run `python -m compileall readwise rw_shared` before distributing changes to catch syntax issues.
- For live smoke tests, set `READWISE_TOKEN` and exercise `highlight create --dry-run`, `highlight list`, and `highlights review` against a small limit to verify pagination + rate-limit logging.
