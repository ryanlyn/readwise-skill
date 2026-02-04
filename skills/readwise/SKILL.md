---
name: readwise
description: "Interact with the Readwise Original API for syncing highlights, exporting notes, and managing books/authors. Use whenever tasks require the legacy Readwise endpoints (not the Reader app)."
allowed-tools: Bash(uv run *)
---

# Readwise Original Skill

Use this skill to automate work with the Readwise "Original" API that powers highlight exports and metadata management.

## Quick start
1. Obtain a personal Readwise token and store it in the `READWISE_TOKEN` secret.
2. Use `uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/readwise/scripts/readwise_client.py ...` instead of calling the API directly; it handles retries, pagination, rate-limit surfacing, `--dry-run`, and tagging rules.
3. Keep requests below the documented rate limit (currently 60 req/min). Batch operations and pause between pages when processing large libraries.

## CLI commands
- `uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/readwise/scripts/readwise_client.py highlight create --text ... [--book-id ID] [--title ...] [--author ...] [--generated] [--tags t1,t2] [--dry-run]`
  Creates a highlight or batch (`--bulk-file ndjson`). Use `--book-id` to target an existing book (the CLI resolves it to title/author for the API). If `--generated` is set, `.generated` is appended to tags and `location_type` defaults to `none`.
- `... highlight update <id> [--title --note --tags --generated]` – partial updates, respects `--dry-run`.
- `... highlight show <id>` – fetch highlight details.
- `... highlight delete <id> [--yes]` – delete a highlight, `--yes` skips confirmation.
- `... highlights list --book-id 123 --tag focus --updated-after 2026-02-01` – cursor-based listing with optional limit.
- `... highlights review --since 2026-02-01` – wraps the daily review/export endpoint.
- `... books [--title ...] [--author ...] [--limit N]` – search books by title/author (case-insensitive substring match).
- `... book <id>` – fetch a single book's metadata.

Default output is human-readable markdown with only key fields. Use `--raw` to get full JSON with all fields.

## Disambiguating book matches

`books --title` performs a case-insensitive substring match and often returns multiple books with the same title. Readwise creates separate book entries per source (Kindle, API, supplemental, etc.), so duplicates are common. When multiple results come back, review them all and use judgement to determine whether they are duplicates of the same work or entirely separate books:

- **Duplicates** (same author, different sources): Readwise creates one entry per import source. A Kindle book, an API-created entry, and a supplemental entry for the same work will all share a title/author. Among duplicates, the entry with the most `num_highlights` is usually the primary one. `category=supplementals` entries are Readwise-generated companions, not user-created.
- **Distinct books**: Different authors or categories mean genuinely different works. Treat these as separate and ask the user which one they mean if the intent is ambiguous.

## Listing highlights for a book by name

1. Find the book ID: `... books --title "book name"`
2. If multiple results, review all entries to determine which are duplicates vs distinct books. For duplicates, query the entry with the most highlights. For distinct books, clarify with the user.
3. List its highlights: `... highlights list --book-id <id>`

## Adding a highlight to an existing book
1. Search for the book: `... books --title "when breath becomes air"`
2. Note the book `id` from the output.
3. Create the highlight: `... highlight create --text "the quote" --book-id <id> --generated`
   The CLI looks up the book's title/author/category and injects them into the payload so the Readwise API matches the highlight to the correct book.

## Data entry guidance
- **Generated snippets**: prefer the explicit `--generated` flag rather than manual tagging. The CLI injects `.generated` for discoverability and leaves other metadata untouched.
- **Highlight text**: supply `--text`, `--text-file`, or pipe content via stdin. The CLI refuses to guess. Bulk imports accept NDJSON rows with `text`, `title`, and `tags`.
- **Location best practices**: omit `--location` unless you can provide an absolute, client-agnostic reference (page number, character offset). When `--location` is omitted the payload leaves `location` blank so Readwise can reconcile it later. For generated quotes the CLI defaults to `location_type=none`.
- **Dry runs**: add `--dry-run` to print the exact payload without calling the API. Dry-run output always shows the full payload (no field filtering).

## Scripts
- `${CLAUDE_PLUGIN_ROOT}/skills/readwise/scripts/readwise_client.py`: full-featured CLI covering highlight create/read/update, daily review, and books list/detail. Commands surface remaining rate-limit headers when provided so agents can throttle work.
- Shared helpers live in `${CLAUDE_PLUGIN_ROOT}/readwise_common/` (auth, HTTP retries, tag/location utilities); import from there when extending functionality to keep behavior consistent.

## References
- `${CLAUDE_PLUGIN_ROOT}/skills/readwise/references/api.md`: mirrors endpoints, parameters, and payload schemas that evolve faster than this SKILL.
- Add more references (e.g., sample responses) as flows become concrete.

## Testing & validation
- Use the dry-run flag in the client to print payloads instead of sending them when iterating on workflows.
- Run `uv run --project ${CLAUDE_PLUGIN_ROOT} python -m compileall ${CLAUDE_PLUGIN_ROOT}/skills/readwise ${CLAUDE_PLUGIN_ROOT}/readwise_common` before distributing changes to catch syntax issues.
- For live smoke tests, set `READWISE_TOKEN` and exercise `highlight create --dry-run`, `highlight list`, and `highlights review` against a small limit to verify pagination + rate-limit logging.
