---
name: readwise
description: "Interact with the Readwise Original API for syncing highlights, exporting notes, and managing books/authors. Use whenever tasks require the legacy Readwise endpoints (not the Reader app)."
---

# Readwise Original Skill

Use this skill to automate work with the Readwise "Original" API that powers highlight exports and metadata management.

## Quick start
1. Obtain a personal Readwise token and store it in the `READWISE_TOKEN` secret.
2. For exploratory work, hit the API indirectly through `scripts/readwise_client.py` to benefit from built-in pagination and retries.
3. Keep requests below the documented rate limit (currently 60 req/min). Batch operations and pause between pages when processing large libraries.

## Common workflows
- **Sync highlights to downstream tools**: pull highlights for a date range, transform them, and push elsewhere.
- **Audit metadata**: fetch books/authors to verify completeness or detect duplicates.
- **Bulk updates**: use the `update_highlight` helper to tag, favorite, or modify highlights in place.

## Authentication
Readwise expects the token via `Authorization: Token <value>`. The helper script loads it from `READWISE_TOKEN`. Override via CLI flags when necessary.

## Scripts
- `scripts/readwise_client.py`: lightweight wrapper with pagination, retry, and convenience helpers (`list_highlights`, `list_books`, `update_highlight`).
- Extend this module or add sibling scripts for bespoke pipelines (e.g., CLI sync commands). Keep scripts idempotent and log key decisions.

## References
- `references/api.md`: mirrors endpoints, parameters, and payload schemas that evolve faster than this SKILL.
- Add more references (e.g., sample responses) as flows become concrete.

## Testing & validation
- Use the dry-run flag in the client to print payloads instead of sending them when iterating on workflows.
- Before shipping updates, run `python scripts/readwise_client.py --check` to hit `/auth/test` and confirm credentials.
