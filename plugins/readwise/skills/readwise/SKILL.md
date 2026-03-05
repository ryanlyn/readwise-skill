---
name: readwise
description: "This skill should be used when the user asks to \"save a highlight to Readwise\", \"create a Readwise highlight\", \"show my Readwise books\", \"list highlights from a book\", \"review my daily highlights\", \"find highlights tagged with\", \"tag a highlight\", \"delete a highlight\", \"validate my Readwise token\", \"export highlights as markdown\", or needs guidance on the Readwise Original API (highlights, books, daily review)."
allowed-tools: Bash(uv run *)
---

# Readwise Original Skill

Use this skill to automate work with the Readwise "Original" API that powers highlight exports and metadata management.

## Quick start
1. Generate a token from https://readwise.io/access_token and store it in `READWISE_TOKEN`.
2. Use `uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/readwise/scripts/readwise_client.py ...` instead of calling the API directly; it handles retries, pagination, rate-limit surfacing, `--dry-run`, and tagging rules.
3. Keep requests below the documented rate limit (currently 60 req/min). Batch operations and pause between pages when processing large libraries.

## Example workflows
- "Summarize my daily review and save highlights to a note" — uses `highlights review` to fetch today's highlights, then formats them
- "Find all highlights from Meditations and export as markdown" — uses `books` to find the book ID, then `highlights list` to fetch
- "Save this quote to my Readwise" — uses `highlight create` with the quote text

## CLI commands

Global options `--dry-run` and `--raw` can appear anywhere in the command.

- `uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/readwise/scripts/readwise_client.py [--dry-run] [--raw] highlight create --text ... [--book-id ID] [--title ...] [--author ...] [--category ...] [--image-url ...] [--generated] [--tags t1,t2]`
  Creates a highlight or batch (`--bulk-file ndjson`). Use `--book-id` to target an existing book (the CLI resolves it to title/author/category for the API). **Always specify `--category`** when creating new sources—see "Category is critical" below. Use `--image-url` for cover images (recommended for `books` and `podcasts`, not needed for `articles` or `tweets`). If `--generated` is set, `.generated` is appended to tags and `location_type` defaults to `none`.
- `... [--dry-run] highlight update <id> [--title --note --tags --generated]` – partial updates.
- `... highlight show <id>` – fetch highlight details.
- `... highlight delete <id> [--yes]` – delete a highlight, `--yes` skips confirmation.
- `... highlights list [--book-id 123] [--tag focus] [--category books] [--updated-after 2026-02-01] [--limit 50]` – cursor-based listing. Dates are ISO format (e.g. `2026-02-01` or `2026-02-01T10:30:00Z`).
- `... highlights review` – fetches today's daily review highlights (no parameters; returns the curated spaced-repetition set).
- `... books [--title ...] [--author ...] [--limit N]` – search books by title/author (case-insensitive substring match).
- `... book <id>` – fetch a single book's metadata.
- `... auth validate` – confirms your token works by hitting the `/api/v2/auth/` endpoint.

Default output is human-readable markdown with only key fields. Use `--raw` to get full JSON with all fields.

## Disambiguating book matches

`books --title` performs a case-insensitive substring match and often returns multiple books with the same title. Readwise creates separate book entries per source (Kindle, API, supplemental, etc.), so duplicates are common. When multiple results come back, review them all and use judgement to determine whether they are duplicates of the same work or entirely separate books:

- **Duplicates** (same author, different sources): Readwise creates one entry per import source. A Kindle book and an API-created entry for the same work will share a title/author. Among duplicates, the entry with the most `num_highlights` is usually the primary one.
- **Distinct books**: Different authors or categories mean genuinely different works. Treat these as separate and ask the user which one they mean if the intent is ambiguous.

## Listing highlights for a book by name

1. Find the book ID: `... books --title "book name"`
2. If multiple results, review all entries to determine which are duplicates vs distinct books. For duplicates, query the entry with the most highlights. For distinct books, clarify with the user.
3. List its highlights: `... highlights list --book-id <id>`

## Adding a highlight to an existing book
1. Search for the book: `... books --title "when breath becomes air"`
2. Note the book `id` from the output.
3. Create the highlight: `... highlight create --text "the verbatim quote" --book-id <id>`
   The CLI looks up the book's title/author/category and injects them into the payload so the Readwise API matches the highlight to the correct book.
   Only add `--generated` if the text is a summary or paraphrase, not a direct quote.

## How Readwise matches sources

Readwise groups highlights into "books" (sources) using **(title, author, source_url)**. The API de-duplicates highlights by matching all four fields: **(title, author, source_url, text)**—including nulls.

**Critical**: All highlights from the same content—whether verbatim quotes or generated summaries—MUST use identical `(title, author, source_url)` values to be grouped together. Inconsistent attributes will scatter highlights across separate book entries.

- If you omit `--title`, highlights go into a generic "Quotes" book
- If you omit `--author`, it stays blank (or uses the URL domain if `source_url` is set)
- Use `--book-id` when adding to an existing book—the CLI fetches and injects the correct title/author/source_url

## Category is critical

**Always specify `--category` explicitly.** The API defaults to `articles` if `source_url` is present, otherwise `books`—but these defaults often miscategorize content. Valid categories: `books`, `articles`, `tweets`, `podcasts`.

| Content type | Category |
|--------------|----------|
| Physical/ebook | `books` |
| Blog post, web article | `articles` |
| Tweet/X post | `tweets` |
| Podcast episode | `podcasts` |
| **YouTube video** | `podcasts` |

**YouTube videos should use `podcasts`**, not `articles`. Readwise treats video content as podcast-like (time-based, spoken word). Using `articles` will cause display and organizational issues.

Mismatched categories create duplicate book entries and break the user's library organization. When in doubt, ask the user or check existing entries with `books --title`.

## Data entry guidance
- **Generated snippets**: Use `--generated` ONLY for highlights that are NOT verbatim quotes from the source content—e.g., AI-generated summaries, paraphrases, or synthesized insights. Do NOT use it for actual quotes or excerpts copied directly from the text. The CLI injects `.generated` for discoverability and sets `location_type=none` since generated content has no source location. Generated highlights should still use the SAME (title, author, source_url) as verbatim highlights from the same source.
- **Highlight text**: supply `--text`, `--text-file`, or pipe content via stdin. The CLI refuses to guess. Bulk imports accept NDJSON rows with `text`, `title`, and `tags`.
- **Location best practices**: omit `--location` unless you can provide an absolute, client-agnostic reference (page number, character offset). When `--location` is omitted the payload leaves `location` blank so Readwise can reconcile it later. Valid `--location-type` values: `page` (books), `time_offset` (podcasts/videos), `order` (articles). For generated quotes the CLI defaults to `location_type=none`.
- **Dry runs**: add `--dry-run` to print the exact payload without calling the API. Dry-run output always shows the full payload (no field filtering).

## Scripts
- `${CLAUDE_PLUGIN_ROOT}/skills/readwise/scripts/readwise_client.py`: full-featured CLI covering highlight create/read/update, daily review, and books list/detail. Commands surface remaining rate-limit headers when provided so agents can throttle work.
- Shared helpers live in `${CLAUDE_PLUGIN_ROOT}/readwise_common/` (auth, HTTP retries, tag/location utilities); import from there when extending functionality to keep behavior consistent.

## Testing & validation
- Use the dry-run flag in the client to print payloads instead of sending them when iterating on workflows.
- Run `uv run --project ${CLAUDE_PLUGIN_ROOT} python -m compileall ${CLAUDE_PLUGIN_ROOT}/skills/readwise ${CLAUDE_PLUGIN_ROOT}/readwise_common` before shipping changes to catch syntax issues.
- For live smoke tests, set `READWISE_TOKEN` and exercise `--dry-run highlight create`, `highlights list`, and `highlights review` against a small limit to verify pagination + rate-limit logging.
