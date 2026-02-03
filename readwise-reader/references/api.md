# Readwise Reader API Notes

## Base URL
`https://readwise.io/api/reader`

## Resources
- `GET /document/list` — filter by `category` (`new`, `later`, `archive`), `doc_type`, `updated_after`.
- `POST /document/add` — ingest via URL or uploaded file.
- `POST /document/upload` — multipart PDF/EPUB upload; returns `source_url` used in `/document/add`.
- `PATCH /document/<id>` — update metadata (`labels`, `state`).
- `GET /annotations` — returns highlights created inside Reader apps.

## Pagination
Reader uses `nextPageCursor` and `document_ids`. The helper client normalizes to Python generators.

## Rate limiting
20 requests/minute. Respect headers `X-User-Limit-Remaining` and `Retry-After` when present.

## TODO
- Capture sample webhook payloads once available.
- Map document schema to downstream targets (e.g., Notion, Obsidian).
