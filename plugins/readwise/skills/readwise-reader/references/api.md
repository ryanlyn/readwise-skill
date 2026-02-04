# Readwise Reader API Notes

## Base URL
`https://readwise.io/api/v3`

## Resources
- `POST /save/` — ingest via URL or HTML snippet.
- `GET /list/` — filter by `category`, `location`, `tag`, `updatedAfter`, `id`.
- `PATCH /update/<id>/` — update title/summary/category/location/tags/notes.
- `DELETE /delete/<id>/` — hard-delete/archive document.
- `GET /tags/` — list available document tags.

## Pagination
Reader uses `nextPageCursor` and `document_ids`. The helper client normalizes to Python generators.

## Rate limiting
20 requests/minute. Respect headers `X-User-Limit-Remaining` and `Retry-After` when present.

## TODO
- Capture sample webhook payloads once available.
- Map document schema to downstream targets (e.g., Notion, Obsidian).
