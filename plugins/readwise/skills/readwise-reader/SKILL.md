---
name: readwise-reader
description: "This skill should be used when the user asks to \"save an article to Reader\", \"save this URL to Readwise Reader\", \"show my Reader inbox\", \"list my Reader documents\", \"archive a document in Reader\", \"triage my reading list\", \"pull recent Reader updates\", \"check what's new in Reader\", \"validate my Readwise token for Reader\", or needs guidance on the Readwise Reader API (documents, articles, RSS, read states)."
allowed-tools: Bash(uv run *)
---

# Readwise Reader Skill

Use this skill to script workflows against the Readwise Reader product (saved articles, feeds, PDFs, newsletters).

## Quick start
1. Generate a token from https://readwise.io/access_token and store it in `READWISE_TOKEN`.
2. Call `uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/readwise-reader/scripts/reader_client.py ...` whenever possible; it handles retries, `.generated` tagging, and `--dry-run` against the `/api/v3` endpoints.
3. Respect Reader's tighter rate limits (20 req/min). The CLI surfaces remaining budget whenever headers are present; throttle accordingly.

## Example workflows
- "Save this article to Reader for later" — uses `docs create` with a URL
- "Show me what's new in my Reader inbox" — uses `docs list --category new`
- "Archive everything I've finished reading this week" — uses `docs pull` + `docs update --state archive`

## CLI commands
- `uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/readwise-reader/scripts/reader_client.py docs create --url <article> [--title ... --summary ... --location later --tags ... --labels ... --generated --dry-run]` – creates a document via URL or raw HTML (`--content`). Use `--location` to set where it lands (defaults to `later`). Reader API v3 does not support uploading local files directly.
- `... docs list [--location later] [--category article] [--tag deep-work] [--limit 25] [--id <doc-id>] [--with-content]` – paginated document listing. Defaults to `--location later`. Use `--id` to fetch a single document. Use `--with-content` to include `html_content` (article text, video transcripts).
- `... docs update <id> [--state archive --tags "deep,focus" --title ...]` – patch metadata/state (`new`, `later`, `archive`). Supports `--dry-run`.
- `... docs pull --since 2026-02-01` – fetches documents updated since a timestamp for recap/triage workflows.
- `... auth validate` – confirms your token works by hitting the `/api/v2/auth/` endpoint.

## Locations vs categories

**Locations** describe where a document sits in your reading workflow:
- `new` — inbox, freshly added items awaiting triage
- `later` — saved for later reading (the default for `docs list`)
- `shortlist` — prioritized for near-term reading
- `archive` — finished or dismissed
- `feed` — RSS/feed items not yet triaged

**Categories** describe the content type:
- `article`, `email`, `rss`, `highlight`, `note`, `pdf`, `epub`, `tweet`, `video`

When a user asks for their "inbox" or "reading list", query `--location later` (the default). Use `--location new` only when specifically checking for untriaged items.

Default output is human-readable markdown with only key fields. Use `--raw` to get full JSON with all fields.

## Fetching content & transcripts
Use `--with-content` to retrieve the full `html_content` field, which contains:
- **Articles**: full article text as HTML
- **Videos**: auto-generated transcript (for YouTube videos with captions)
- **PDFs/EPUBs**: extracted text content

This is disabled by default to keep responses fast. When you need to analyze, summarize, or extract quotes from a document, fetch it by ID with content:
```
... docs list --id <doc-id> --with-content --raw
```

## Data guidance
- **Generated entries**: set `--generated` when saving synthetic journal entries or agent summaries. The CLI appends `.generated` to tags (and labels, when provided) so they are searchable in Reader.
- **Source inputs**: prefer `--url` when the content exists online. Use `--content` for local snippets; Reader API v3 does not expose the legacy upload flow, so convert PDFs to shareable URLs before saving.
- **Metadata**: Reader tolerates arbitrary tags/labels, so lean on them for downstream automations (e.g., `.journal`, `.deepread`). Avoid overloading `summary` with custom formats—store structured metadata in labels/tags instead.
- **Dry runs**: `--dry-run` prints the payload without hitting the API. Dry-run output always shows the full payload (no field filtering).

## Scripts
- `${CLAUDE_PLUGIN_ROOT}/skills/readwise-reader/scripts/reader_client.py`: CLI covering document create/list/update/pull plus token validation against Reader API v3. Integrates with shared utilities from `${CLAUDE_PLUGIN_ROOT}/readwise_common/`.
- Shared helpers live in `${CLAUDE_PLUGIN_ROOT}/readwise_common/` (auth, HTTP retries, tag/location utilities); import from there when extending functionality to keep behavior consistent.

## Testing & validation
- Use `uv run --project ${CLAUDE_PLUGIN_ROOT} python -m compileall ${CLAUDE_PLUGIN_ROOT}/skills/readwise-reader ${CLAUDE_PLUGIN_ROOT}/readwise_common` before shipping changes.
- Smoke-test live calls (token required) with `docs create --dry-run`, `docs list --limit 5`, and `docs pull --since <yesterday>` to confirm pagination + tagging rules.
