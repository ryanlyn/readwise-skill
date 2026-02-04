# Readwise Reader API Notes

## Base URL
`https://readwise.io/api/v3`

## Resources
- `POST /save/` — create a document from a URL or HTML payload (see `reader_api` docs).
- `GET /list/` — filter by `category`, `doc_type`, `updated_after`.
- `PATCH /update/<document_id>/` — update metadata (`labels`, `state`).
- `DELETE /delete/<document_id>/` — remove a document.
- `GET /tags/` — list tags.

## Pagination
Reader uses `nextPageCursor` and `document_ids`. The helper client normalizes to Python generators.

## Rate limiting
20 requests/minute. Respect headers `X-User-Limit-Remaining` and `Retry-After` when present.

## TODO
- Capture sample webhook payloads once available.
- Map document schema to downstream targets (e.g., Notion, Obsidian).
