# Readwise Stub Server

This stub server implements a small subset of the Readwise and Reader APIs so you can run CLI smoke tests locally without hitting production.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
python app.py
```

The server listens on `http://localhost:3000` and expects an `Authorization: Token <value>` header for all endpoints.

## Implemented endpoints

### Reader API

- `GET /api/v2/auth/` – returns `204` when the auth header is present.
- `POST /api/v3/save/` – create a document.
- `GET /api/v3/list/` – list documents (supports `id`, `updatedAfter`, `location`, `category`, `tag`, `limit`, `pageCursor`, `withHtmlContent`, `withRawSourceUrl`).
- `PATCH /api/v3/update/<document_id>/` – update document fields.
- `DELETE /api/v3/delete/<document_id>/` – delete a document.
- `GET /api/v3/tags/` – list document tags.

### Readwise API

- `GET /api/v2/auth/` – returns `204` when the auth header is present.
- `GET /api/v2/highlights/` – list highlights (supports `page`, `page_size`, `book_id`).
- `POST /api/v2/highlights/` – create highlights.
- `PATCH /api/v2/highlights/<highlight_id>/` – update highlights.
- `DELETE /api/v2/highlights/<highlight_id>/` – delete highlights.
- `GET /api/v2/books/` – list books (supports `page`, `page_size`).
- `GET /api/v2/highlights/<highlight_id>/tags` – list highlight tags.
- `GET /api/v2/highlights/<highlight_id>/tags/<tag_id>` – fetch a tag.
- `POST /api/v2/highlights/<highlight_id>/tags/` – create a tag.
- `PATCH /api/v2/highlights/<highlight_id>/tags/<tag_id>` – update a tag.
- `DELETE /api/v2/highlights/<highlight_id>/tags/<tag_id>` – delete a tag.

Fixtures live in `stub_server/fixtures` and are loaded into memory at startup.
