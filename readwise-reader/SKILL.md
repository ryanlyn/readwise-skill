---
name: readwise-reader
description: "Automate the Readwise Reader API for ingesting documents, syncing annotations, and orchestrating triage inside the Reader app. Use when tasks involve the Reader beta endpoints (articles, RSS, documents, read states)."
---

# Readwise Reader Skill

Use this skill to script workflows against the Readwise Reader product (a superset of the Original API focused on saved articles, feeds, and PDF ingestion).

## Quick start
1. Generate a Reader token from https://readwise.io/reader_api and store it in `READWISE_READER_TOKEN`.
2. Interact with the API through `scripts/reader_client.py` for pagination, filtering, and attachment uploads.
3. Respect Reader's tighter rate limits (20 req/min) and exponential backoff guidance.

## Common workflows
- **Daily triage**: fetch unread documents, prioritize, and mark processed items as archived.
- **Cross-device sync**: export annotations/highlights from Reader to other services.
- **Automated ingestion**: upload PDFs, Markdown snippets, or RSS finds directly into Reader collections.

## Authentication
Pass `Authorization: Token <value>` just like the Original API. The helper script reads from `READWISE_READER_TOKEN` and exposes `--token` to override.

## Scripts
- `scripts/reader_client.py`: wraps endpoints for documents, annotations, feeds, and file uploads with built-in backoff and type validation.
- Add specialized scripts (e.g., queue processors) when workflows become repeatable.

## References
- `references/api.md`: endpoint matrix, payload notes, and example requests/responses segregated by resource.
- Expand with playbooks (e.g., ingestion recipes) as the skill matures.

## Testing & validation
- Run `python scripts/reader_client.py --check` to verify credentials via `/auth/test`.
- Use the built-in dry-run switch while refining bulk actions to avoid accidental deletions.
