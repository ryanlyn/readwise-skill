---
name: readwise-reader
description: "Automate the Readwise Reader API for ingesting documents, syncing annotations, and orchestrating triage inside the Reader app. Use when tasks involve the Reader beta endpoints (articles, RSS, documents, read states)."
---

# Readwise Reader Skill

Use this skill to script workflows against the Readwise Reader product (saved articles, feeds, PDFs, newsletters). Install dependencies via `pip install -r requirements.txt` before running the CLI.

## Quick start
1. Generate a Reader token from https://readwise.io/reader_api and store it in `READWISE_READER_TOKEN`.
2. Call `python scripts/reader_client.py ...` whenever possible; it handles retries, file uploads, `.generated` tagging, and `--dry-run`.
3. Respect Reader's tighter rate limits (20 req/min). The CLI surfaces remaining budget whenever headers are present; throttle accordingly.

## CLI commands
- `python scripts/reader_client.py docs create --url <article> [--title ... --summary ... --tags ... --labels ... --generated --dry-run]` – creates a document. Accepts `--file` uploads (PDF/EPUB) and raw HTML via `--content`.
- `... docs list --category new --tag deep-work --limit 25` – paginated document listing with filters on category/tag/update time.
- `... docs update <id> [--state archive --labels "deep,focus" --title ...]` – patch metadata/state (`new`, `later`, `archive`). Supports `--dry-run`.
- `... docs pull --since 2026-02-01` – fetches documents updated since a timestamp for recap/triage workflows; combine with `--output markdown` for conversational summaries.

## Data guidance
- **Generated entries**: set `--generated` when saving synthetic journal entries or agent summaries. The CLI appends `.generated` to tags (and labels, when provided) so they are searchable in Reader.
- **Source inputs**: prefer `--url` when the content exists online. Use `--content` or `--file` for local snippets/PDFs. The CLI refuses to guess—supply at least one.
- **Metadata**: Reader tolerates arbitrary tags/labels, so lean on them for downstream automations (e.g., `.journal`, `.deepread`). Avoid overloading `summary` with custom formats—store structured metadata in labels/tags instead.
- **Dry runs**: `--dry-run` prints the JSON payload (and upload plan) without hitting the API. Use this before bulk imports or destructive updates.

## Scripts
- `scripts/reader_client.py`: CLI covering document create/list/update/pull plus upload handling. Integrates with shared utilities from `rw_shared/`.
- Extend with additional scripts (queue processors, RSS ingestors) by importing the `ReaderClient` and helpers defined here to keep authentication/retry behavior consistent.

## References
- `references/api.md`: endpoint matrix, payload notes, and example requests/responses segregated by resource.
- Expand with playbooks (e.g., ingestion recipes) as the skill matures.

## Testing & validation
- Use `python -m compileall readwise-reader rw_shared` before shipping changes.
- Smoke-test live calls (token required) with `docs create --dry-run`, `docs list --limit 5`, and `docs pull --since <yesterday>` to confirm pagination + tagging rules.
