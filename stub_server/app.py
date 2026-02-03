from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, jsonify, request


BASE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = BASE_DIR / "fixtures"

app = Flask(__name__)


def load_fixture(name: str) -> Any:
    path = FIXTURES_DIR / name
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_auth() -> Optional[Tuple[Dict[str, str], int]]:
    token = request.headers.get("Authorization", "")
    if not token.startswith("Token "):
        return {"detail": "Unauthorized"}, 401
    return None


@dataclass
class Store:
    documents: Dict[str, Dict[str, Any]]
    document_tags: List[Dict[str, str]]
    highlights: Dict[int, Dict[str, Any]]
    books: Dict[int, Dict[str, Any]]
    highlight_tags: Dict[int, List[Dict[str, Any]]]
    highlight_counter: int
    tag_counter: int

    @classmethod
    def from_fixtures(cls) -> "Store":
        documents = {doc["id"]: doc for doc in load_fixture("reader_documents.json")}
        document_tags = load_fixture("reader_tags.json")
        highlights = {highlight["id"]: highlight for highlight in load_fixture("highlights.json")}
        books = {book["id"]: book for book in load_fixture("books.json")}
        highlight_tags = {
            int(highlight_id): tags
            for highlight_id, tags in load_fixture("highlight_tags.json").items()
        }
        highlight_counter = max(highlights.keys(), default=0) + 1
        tag_counter = 100000 + sum(len(tags) for tags in highlight_tags.values())
        return cls(
            documents=documents,
            document_tags=document_tags,
            highlights=highlights,
            books=books,
            highlight_tags=highlight_tags,
            highlight_counter=highlight_counter,
            tag_counter=tag_counter,
        )


STORE = Store.from_fixtures()


@app.route("/api/v2/auth/", methods=["GET"])
def readwise_auth() -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status
    return "", 204


@app.route("/api/v3/save/", methods=["POST"])
def reader_save() -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    payload = request.get_json(force=True, silent=True) or {}
    url = payload.get("url")
    if not url:
        return jsonify({"detail": "url is required"}), 400

    for doc in STORE.documents.values():
        if doc.get("source_url") == url or doc.get("url") == url:
            return jsonify({"id": doc["id"], "url": doc["url"]}), 200

    doc_id = uuid.uuid4().hex
    document = {
        "id": doc_id,
        "url": f"https://read.readwise.io/new/read/{doc_id}",
        "source_url": url,
        "title": payload.get("title") or "Untitled",
        "author": payload.get("author") or "Unknown",
        "source": payload.get("saved_using") or "Stubbed Client",
        "category": payload.get("category") or "article",
        "location": payload.get("location") or "new",
        "tags": {tag: tag.replace("-", " ").title() for tag in payload.get("tags", [])},
        "site_name": "Stubbed Reader",
        "word_count": 120,
        "reading_time": "1 min",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "notes": payload.get("notes", ""),
        "published_date": payload.get("published_date"),
        "summary": payload.get("summary", ""),
        "image_url": payload.get("image_url"),
        "parent_id": None,
        "reading_progress": 0.0,
        "first_opened_at": None,
        "last_opened_at": None,
        "saved_at": now_iso(),
        "last_moved_at": now_iso(),
        "html_content": payload.get("html"),
        "raw_source_url": None,
    }
    STORE.documents[doc_id] = document
    return jsonify({"id": doc_id, "url": document["url"]}), 201


@app.route("/api/v3/list/", methods=["GET"])
def reader_list() -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    docs = list(STORE.documents.values())
    doc_id = request.args.get("id")
    if doc_id:
        docs = [doc for doc in docs if doc.get("id") == doc_id]

    updated_after = request.args.get("updatedAfter")
    if updated_after:
        cutoff = parse_iso_datetime(updated_after)
        if cutoff:
            docs = [doc for doc in docs if parse_iso_datetime(doc.get("updated_at")) and parse_iso_datetime(doc.get("updated_at")) > cutoff]

    location = request.args.get("location")
    if location:
        docs = [doc for doc in docs if doc.get("location") == location]

    category = request.args.get("category")
    if category:
        docs = [doc for doc in docs if doc.get("category") == category]

    tags = request.args.getlist("tag")
    if tags:
        if tags == [""]:
            docs = [doc for doc in docs if not doc.get("tags")]
        else:
            docs = [
                doc
                for doc in docs
                if all(tag in (doc.get("tags") or {}) for tag in tags)
            ]

    limit = int(request.args.get("limit", 100))
    limit = max(1, min(limit, 100))
    page_cursor = request.args.get("pageCursor")
    offset = 0
    if page_cursor:
        try:
            offset = int(page_cursor.split(":", 1)[-1])
        except ValueError:
            offset = 0

    paginated = docs[offset : offset + limit]
    next_cursor = None
    if offset + limit < len(docs):
        next_cursor = f"cursor:{offset + limit}"

    include_html = request.args.get("withHtmlContent", "false").lower() == "true"
    include_raw = request.args.get("withRawSourceUrl", "false").lower() == "true"

    results = []
    for doc in paginated:
        doc_copy = dict(doc)
        if not include_html:
            doc_copy.pop("html_content", None)
        if not include_raw:
            doc_copy.pop("raw_source_url", None)
        results.append(doc_copy)

    return jsonify({"count": len(docs), "nextPageCursor": next_cursor, "results": results})


@app.route("/api/v3/update/<doc_id>/", methods=["PATCH"])
def reader_update(doc_id: str) -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    document = STORE.documents.get(doc_id)
    if not document:
        return jsonify({"detail": "Document not found"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    for field in [
        "title",
        "author",
        "summary",
        "published_date",
        "image_url",
        "location",
        "category",
        "notes",
    ]:
        if field in payload:
            document[field] = payload[field]

    if "tags" in payload:
        document["tags"] = {tag: tag.replace("-", " ").title() for tag in payload["tags"]}

    if "seen" in payload:
        if payload["seen"]:
            document["first_opened_at"] = document.get("first_opened_at") or now_iso()
            document["last_opened_at"] = now_iso()
        else:
            document["first_opened_at"] = None
            document["last_opened_at"] = None

    document["updated_at"] = now_iso()
    return jsonify({"id": doc_id, "url": document["url"]})


@app.route("/api/v3/delete/<doc_id>/", methods=["DELETE"])
def reader_delete(doc_id: str) -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    if doc_id in STORE.documents:
        STORE.documents.pop(doc_id)
        return "", 204
    return jsonify({"detail": "Document not found"}), 404


@app.route("/api/v3/tags/", methods=["GET"])
def reader_tags() -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    page_cursor = request.args.get("pageCursor")
    offset = 0
    if page_cursor:
        try:
            offset = int(page_cursor.split(":", 1)[-1])
        except ValueError:
            offset = 0

    limit = 100
    tags = STORE.document_tags
    results = tags[offset : offset + limit]
    next_cursor = None
    if offset + limit < len(tags):
        next_cursor = f"cursor:{offset + limit}"

    return jsonify({"count": len(tags), "nextPageCursor": next_cursor, "results": results})


def paginate(items: List[Any], page: int, page_size: int) -> Tuple[List[Any], Optional[str]]:
    start = (page - 1) * page_size
    end = start + page_size
    next_page = None
    if end < len(items):
        next_page = f"?page={page + 1}&page_size={page_size}"
    return items[start:end], next_page


@app.route("/api/v2/highlights/", methods=["GET"])
def highlights_list() -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    highlights = list(STORE.highlights.values())
    book_id = request.args.get("book_id")
    if book_id:
        highlights = [h for h in highlights if str(h.get("book_id")) == book_id]

    page_size = int(request.args.get("page_size", 100))
    page = int(request.args.get("page", 1))
    page_size = max(1, min(page_size, 1000))
    page = max(page, 1)
    page_results, next_page = paginate(highlights, page, page_size)

    next_url = None
    if next_page:
        next_url = f"http://localhost:3000/api/v2/highlights/{next_page}"

    return jsonify(
        {
            "count": len(highlights),
            "next": next_url,
            "previous": None if page == 1 else f"http://localhost:3000/api/v2/highlights/?page={page - 1}&page_size={page_size}",
            "results": page_results,
        }
    )


@app.route("/api/v2/highlights/", methods=["POST"])
def highlights_create() -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    payload = request.get_json(force=True, silent=True) or {}
    highlights_payload = payload.get("highlights") or []
    created = []
    for highlight in highlights_payload:
        highlight_id = STORE.highlight_counter
        STORE.highlight_counter += 1
        book_id = highlight.get("book_id") or next(iter(STORE.books.keys()), 1)
        created_highlight = {
            "id": highlight_id,
            "text": highlight.get("text", ""),
            "note": highlight.get("note", ""),
            "location": highlight.get("location") or 1,
            "location_type": highlight.get("location_type") or "order",
            "highlighted_at": highlight.get("highlighted_at") or now_iso(),
            "created_at": now_iso(),
            "url": highlight.get("highlight_url"),
            "color": highlight.get("color") or "yellow",
            "updated": now_iso(),
            "book_id": int(book_id),
            "external_id": highlight.get("external_id"),
            "tags": [],
            "end_location": highlight.get("end_location"),
            "readwise_url": f"https://readwise.io/open/{highlight_id}",
        }
        STORE.highlights[highlight_id] = created_highlight
        created.append(created_highlight)

    return jsonify({"highlights": created}), 200


@app.route("/api/v2/highlights/<int:highlight_id>/", methods=["PATCH"])
def highlights_update(highlight_id: int) -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    highlight = STORE.highlights.get(highlight_id)
    if not highlight:
        return jsonify({"detail": "Highlight not found"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    for field in ["text", "note", "location", "url", "color"]:
        if field in payload:
            highlight[field] = payload[field]
    highlight["updated"] = now_iso()

    return jsonify(highlight)


@app.route("/api/v2/highlights/<int:highlight_id>/", methods=["DELETE"])
def highlights_delete(highlight_id: int) -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    if highlight_id in STORE.highlights:
        STORE.highlights.pop(highlight_id)
        STORE.highlight_tags.pop(highlight_id, None)
        return "", 204
    return jsonify({"detail": "Highlight not found"}), 404


@app.route("/api/v2/books/", methods=["GET"])
def books_list() -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    books = list(STORE.books.values())
    page_size = int(request.args.get("page_size", 100))
    page = int(request.args.get("page", 1))
    page_size = max(1, min(page_size, 1000))
    page = max(page, 1)
    page_results, next_page = paginate(books, page, page_size)

    next_url = None
    if next_page:
        next_url = f"http://localhost:3000/api/v2/books/{next_page}"

    return jsonify(
        {
            "count": len(books),
            "next": next_url,
            "previous": None if page == 1 else f"http://localhost:3000/api/v2/books/?page={page - 1}&page_size={page_size}",
            "results": page_results,
        }
    )


@app.route("/api/v2/highlights/<int:highlight_id>/tags", methods=["GET"])
def highlight_tags_list(highlight_id: int) -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    tags = STORE.highlight_tags.get(highlight_id, [])
    page_size = int(request.args.get("page_size", 100))
    page = int(request.args.get("page", 1))
    page_results, next_page = paginate(tags, page, page_size)

    next_url = None
    if next_page:
        next_url = f"http://localhost:3000/api/v2/highlights/{highlight_id}/tags{next_page}"

    return jsonify(
        {
            "count": len(tags),
            "next": next_url,
            "previous": None if page == 1 else f"http://localhost:3000/api/v2/highlights/{highlight_id}/tags?page={page - 1}&page_size={page_size}",
            "results": page_results,
        }
    )


@app.route("/api/v2/highlights/<int:highlight_id>/tags/<int:tag_id>", methods=["GET"])
def highlight_tag_detail(highlight_id: int, tag_id: int) -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    tags = STORE.highlight_tags.get(highlight_id, [])
    for tag in tags:
        if tag.get("id") == tag_id:
            return jsonify(tag)
    return jsonify({"detail": "Tag not found"}), 404


@app.route("/api/v2/highlights/<int:highlight_id>/tags/", methods=["POST"])
def highlight_tag_create(highlight_id: int) -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    payload = request.get_json(force=True, silent=True) or {}
    name = payload.get("name")
    if not name:
        return jsonify({"detail": "name is required"}), 400

    STORE.tag_counter += 1
    tag = {"id": STORE.tag_counter, "name": name}
    STORE.highlight_tags.setdefault(highlight_id, []).append(tag)
    return jsonify(tag)


@app.route("/api/v2/highlights/<int:highlight_id>/tags/<int:tag_id>", methods=["PATCH"])
def highlight_tag_update(highlight_id: int, tag_id: int) -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    payload = request.get_json(force=True, silent=True) or {}
    name = payload.get("name")
    if not name:
        return jsonify({"detail": "name is required"}), 400

    tags = STORE.highlight_tags.get(highlight_id, [])
    for tag in tags:
        if tag.get("id") == tag_id:
            tag["name"] = name
            return jsonify(tag)
    return jsonify({"detail": "Tag not found"}), 404


@app.route("/api/v2/highlights/<int:highlight_id>/tags/<int:tag_id>", methods=["DELETE"])
def highlight_tag_delete(highlight_id: int, tag_id: int) -> Any:
    auth_error = require_auth()
    if auth_error:
        payload, status = auth_error
        return jsonify(payload), status

    tags = STORE.highlight_tags.get(highlight_id, [])
    updated = [tag for tag in tags if tag.get("id") != tag_id]
    if len(updated) != len(tags):
        STORE.highlight_tags[highlight_id] = updated
        return "", 204
    return jsonify({"detail": "Tag not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)
