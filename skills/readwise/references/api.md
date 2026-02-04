# Readwise Original API Notes

## Base URL
`https://readwise.io/api/v2`

## Key endpoints
- `GET /highlights/` — supports `page_size`, `updated_after`, `book_id`, `category`.
- `GET /books/` — provides metadata for deduping or enrichment.
- `POST /highlights/` — create custom highlights; pass `text`, `title`, `location_url`, `source_url`.
- `PATCH /highlights/<id>/` — update tags, note, or favorite.

## Pagination
Use `nextPageCursor` tokens from responses; the helper client exposes `paginate()` to iterate safely.

## Rate limiting
Readwise enforces 60 requests/minute across endpoints. Back off for HTTP 429 with exponential delay.

## Sample response
```json
{
  "count": 2,
  "nextPageCursor": null,
  "results": [
    {
      "id": 123,
      "text": "Example highlight",
      "note": "",
      "location_url": "kindle://book/...",
      "source_url": "https://article",
      "book_id": 456,
      "updated": "2024-01-01T12:00:00Z"
    }
  ]
}
```

## TODO
- Add schema snippets for `/authors/`, `/reviewers/` if needed.
- Document custom export formats when finalized.
