---
name: readwise-reader
description: "Automate the Readwise Reader API for ingesting documents, syncing annotations, and orchestrating triage inside the Reader app. Use when tasks involve the Reader endpoints (articles, RSS, documents, read states)."
allowed-tools: Bash(python *), Bash(pip install *)
---

# Readwise Reader Skill

Use this skill to script workflows against the Readwise Reader product (saved articles, feeds, PDFs, newsletters). Install dependencies via `pip install ${CLAUDE_PLUGIN_ROOT}` before running the CLI.

## Quick start
1. Generate a Reader token from https://readwise.io/reader_api and store it in `READWISE_READER_TOKEN`.
2. Call `python ${CLAUDE_PLUGIN_ROOT}/skills/readwise-reader/scripts/reader_client.py ...` whenever possible; it handles retries, `.generated` tagging, and `--dry-run` against the `/api/v3` endpoints.
3. Respect Reader's tighter rate limits (20 req/min). The CLI surfaces remaining budget whenever headers are present; throttle accordingly.

## CLI commands
- `python ${CLAUDE_PLUGIN_ROOT}/skills/readwise-reader/scripts/reader_client.py docs create --url <article> [--title ... --summary ... --tags ... --labels ... --generated --dry-run]` – creates a document via URL or raw HTML (`--content`). Reader API v3 does not support uploading local files directly.
- `... docs list --category new --tag deep-work --limit 25` – paginated document listing with filters on id/category/tag/location/update time.
- `... docs update <id> [--state archive --tags "deep,focus" --title ...]` – patch metadata/state (`new`, `later`, `archive`). Supports `--dry-run`.
- `... docs pull --since 2026-02-01` – fetches documents updated since a timestamp for recap/triage workflows; combine with `--output markdown` for conversational summaries.
- `... auth validate` – confirms your token works by hitting the `/api/v2/auth/` endpoint.

## Data guidance
- **Generated entries**: set `--generated` when saving synthetic journal entries or agent summaries. The CLI appends `.generated` to tags (and labels, when provided) so they are searchable in Reader.
- **Source inputs**: prefer `--url` when the content exists online. Use `--content` for local snippets; Reader API v3 does not expose the legacy upload flow, so convert PDFs to shareable URLs before saving.
- **Metadata**: Reader tolerates arbitrary tags/labels, so lean on them for downstream automations (e.g., `.journal`, `.deepread`). Avoid overloading `summary` with custom formats—store structured metadata in labels/tags instead.
- **Dry runs**: `--dry-run` prints the JSON payload without hitting the API. Use this before bulk imports or destructive updates.

## Scripts
- `${CLAUDE_PLUGIN_ROOT}/skills/readwise-reader/scripts/reader_client.py`: CLI covering document create/list/update/pull plus token validation against Reader API v3. Integrates with shared utilities from `${CLAUDE_PLUGIN_ROOT}/readwise_common/`.
- Extend with additional scripts (queue processors, RSS ingestors) by importing the `ReaderClient` and helpers defined here to keep authentication/retry behavior consistent.

## References
- `${CLAUDE_PLUGIN_ROOT}/skills/readwise-reader/references/api.md`: endpoint matrix, payload notes, and example requests/responses segregated by resource.
- Expand with playbooks (e.g., ingestion recipes) as the skill matures.

## Testing & validation
- Use `python -m compileall ${CLAUDE_PLUGIN_ROOT}/skills/readwise-reader ${CLAUDE_PLUGIN_ROOT}/rw_shared` before shipping changes.
- Smoke-test live calls (token required) with `docs create --dry-run`, `docs list --limit 5`, and `docs pull --since <yesterday>` to confirm pagination + tagging rules.
