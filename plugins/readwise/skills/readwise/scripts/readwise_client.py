"""Comprehensive CLI for interacting with the Readwise Original API."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from typing import Annotated, Any

import requests
import typer

from readwise_common import (
    Book,
    BookListParams,
    DailyReviewResponse,
    DeleteResult,
    DryRunResult,
    Highlight,
    HighlightCreatePayload,
    HighlightListParams,
    HighlightUpdatePayload,
    TokenValidationResult,
    build_location_payload,
    build_tags,
    format_inline_tags,
    get_readwise_token,
    parse_iso_datetime,
    parse_tags,
    print_result,
    render_highlights,
    request_with_backoff,
    resolve_highlight_text,
)
from readwise_common.http import APIRequestError
from readwise_common.utils import hoist_global_options, load_bulk_payloads

HIGHLIGHT_FIELDS = ["id", "text", "note", "tags"]
BOOK_FIELDS = ["id", "title", "author", "category", "source", "num_highlights"]

DEFAULT_BASE_URL = "https://readwise.io/api/v2"
AUTH_URL = "https://readwise.io/api/v2/auth/"
USER_AGENT = "readwise-skill-cli/0.1"


class ReadwiseClient:
    def __init__(self, token: str, *, base_url: str | None = None, auth_url: str | None = None, dry_run: bool = False):
        self.base_url = (base_url or os.getenv("READWISE_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.auth_url = auth_url or os.getenv("READWISE_AUTH_URL") or AUTH_URL
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Token {token}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        return request_with_backoff(self.session, method, url, **kwargs)

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
        cursor: str | None = None
        next_url: str | None = None
        base_params = dict(params or {})
        while True:
            scoped = dict(base_params)
            if cursor:
                scoped["pageCursor"] = cursor
                cursor = None
            if next_url:
                response = request_with_backoff(self.session, "get", next_url)
                next_url = None
            else:
                response = self._request("get", path, params=scoped)
            payload = response.json()
            yield from payload.get("results", [])
            cursor = payload.get("nextPageCursor")
            next_url = payload.get("next")
            if not cursor and not next_url:
                break

    def create_highlight(self, payload: HighlightCreatePayload) -> Highlight | DryRunResult:
        data = payload.model_dump(exclude_none=True)
        if self.dry_run:
            return DryRunResult(request_payload=data)
        response = self._request("post", "/highlights/", json={"highlights": [data]})
        resp_data = response.json()
        if isinstance(resp_data, list) and len(resp_data) == 1:
            book = resp_data[0]
            highlight_ids = book.get("modified_highlights", [])
            if highlight_ids:
                return self.get_highlight(highlight_ids[0])
            return Highlight.model_validate(book)
        highlights = resp_data.get("highlights")
        if isinstance(highlights, list) and len(highlights) == 1:
            return Highlight.model_validate(highlights[0])
        return Highlight.model_validate(resp_data)

    def list_highlights(self, params: HighlightListParams) -> Iterable[Highlight]:
        query: dict[str, Any] = {}
        if params.book_id is not None:
            query["book_id"] = params.book_id
        if params.tag is not None:
            query["tag"] = params.tag
        if params.updated_after is not None:
            query["updatedAfter"] = params.updated_after
        if params.updated_before is not None:
            query["updatedBefore"] = params.updated_before
        if params.category is not None:
            query["category"] = params.category
        for item in self.paginate("/highlights/", query):
            yield Highlight.model_validate(item)

    def get_highlight(self, highlight_id: int) -> Highlight:
        response = self._request("get", f"/highlights/{highlight_id}/")
        return Highlight.model_validate(response.json())

    def update_highlight(self, highlight_id: int, payload: HighlightUpdatePayload) -> Highlight | DryRunResult:
        data = payload.model_dump(exclude_none=True)
        if self.dry_run:
            return DryRunResult(highlight_id=highlight_id, request_payload=data)
        response = self._request("patch", f"/highlights/{highlight_id}/", json=data)
        return Highlight.model_validate(response.json())

    def delete_highlight(self, highlight_id: int) -> DeleteResult | DryRunResult:
        if self.dry_run:
            return DryRunResult(highlight_id=highlight_id, action="delete")
        self._request("delete", f"/highlights/{highlight_id}/")
        return DeleteResult(deleted=True, highlight_id=highlight_id)

    def daily_review(self) -> DailyReviewResponse:
        response = self._request("get", "/review/")
        return DailyReviewResponse.model_validate(response.json())

    def list_books(self, params: BookListParams) -> Iterable[Book]:
        for item in self.paginate("/books/"):
            yield Book.model_validate(item)

    def tag_highlight(self, highlight_id: int, tag_name: str) -> dict[str, Any]:
        if self.dry_run:
            return {"dry_run": True, "highlight_id": highlight_id, "tag": tag_name}
        response = self._request("post", f"/highlights/{highlight_id}/tags/", json={"name": tag_name})
        return response.json()

    def get_book(self, book_id: int) -> Book:
        response = self._request("get", f"/books/{book_id}/")
        return Book.model_validate(response.json())

    def validate_token(self) -> None:
        response = request_with_backoff(self.session, "get", self.auth_url)
        if response.status_code != 204:
            error = requests.HTTPError("Unexpected auth response", response=response)
            raise error


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------


def _build_highlight_payload(
    *,
    text: str | None,
    text_file: str | None,
    title: str | None,
    author: str | None,
    source_url: str | None,
    image_url: str | None = None,
    book_id: int | None,
    category: str | None,
    note: str | None,
    tags_raw: str | None,
    location: str | None,
    location_type: str | None,
    generated: bool,
    require_text: bool,
    inline_tags: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    should_load_text = bool(text or text_file or not sys.stdin.isatty())
    if should_load_text:
        try:
            payload["text"] = resolve_highlight_text(text, text_file)
        except ValueError:
            if require_text:
                raise
    field_values = [
        ("title", title),
        ("author", author),
        ("source_url", source_url),
        ("image_url", image_url),
        ("note", note),
        ("book_id", book_id),
        ("category", category),
    ]
    for field, value in field_values:
        if value:
            payload[field] = value

    tag_list = build_tags(parse_tags(tags_raw), generated)
    if tag_list:
        if inline_tags:
            payload["note"] = format_inline_tags(tag_list, payload.get("note"))
        else:
            payload["_tags"] = tag_list

    payload.update(build_location_payload(location, location_type, generated))
    return payload


def _normalize_bulk_payload(entry: dict[str, Any], default_generated: bool) -> dict[str, Any]:
    payload = dict(entry)
    text = payload.get("text")
    if not text:
        raise ValueError("Bulk highlight payloads require 'text'")
    tags = payload.pop("tags", None) or []
    if isinstance(tags, str):
        tags = parse_tags(tags)
    generated = payload.pop("generated", default_generated)
    resolved_tags = build_tags(tags, generated)
    if resolved_tags:
        payload["note"] = format_inline_tags(resolved_tags, payload.get("note"))
    payload.update(build_location_payload(payload.get("location"), payload.get("location_type"), generated))
    return payload


def _normalize_datetime_arg(label: str, value: str) -> str:
    try:
        return parse_iso_datetime(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date or datetime") from exc


def _resolve_book_id(client: ReadwiseClient, payload: dict[str, Any]) -> None:
    """Replace book_id with book metadata so the API's dedup matches correctly."""
    book_id = payload.pop("book_id", None)
    if book_id and not payload.get("title"):
        book = client.get_book(book_id)
        payload["title"] = book.title
        field_map = [
            ("author", "author"),
            ("source_url", "source_url"),
            ("category", "category"),
            ("source_type", "source"),
        ]
        for field, book_attr in field_map:
            value = getattr(book, book_attr, None)
            if value:
                payload.setdefault(field, value)


# ---------------------------------------------------------------------------
# Typer CLI
# ---------------------------------------------------------------------------

app = typer.Typer(help="Interact with the Readwise Original API")
highlight_app = typer.Typer(help="Operate on a single highlight")
highlights_app = typer.Typer(help="List or review highlights")
auth_app = typer.Typer(help="Authentication helpers")

app.add_typer(highlight_app, name="highlight")
app.add_typer(highlights_app, name="highlights")
app.add_typer(auth_app, name="auth")


@app.callback()
def app_callback(
    ctx: typer.Context,
    token: Annotated[str | None, typer.Option(help="Override READWISE_TOKEN env var")] = None,
    raw: Annotated[bool, typer.Option("--raw", help="Output full JSON (all fields)")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print payloads without calling the API")] = False,
) -> None:
    resolved = get_readwise_token(token)
    ctx.ensure_object(dict)
    ctx.obj["client"] = ReadwiseClient(resolved.value, dry_run=dry_run)
    ctx.obj["raw"] = raw
    ctx.obj["dry_run"] = dry_run


@highlight_app.command("create")
def highlight_create(
    ctx: typer.Context,
    text: Annotated[str | None, typer.Option(help="Highlight text (or use --text-file or stdin)")] = None,
    text_file: Annotated[str | None, typer.Option("--text-file", help="Path to file containing highlight text")] = None,
    title: Annotated[str | None, typer.Option(help="Source title (e.g. book/article name)")] = None,
    author: Annotated[str | None, typer.Option(help="Author name")] = None,
    source_url: Annotated[str | None, typer.Option("--source-url", help="URL of the source")] = None,
    image_url: Annotated[
        str | None, typer.Option("--image-url", help="Cover image URL (recommended for books/podcasts)")
    ] = None,
    book_id: Annotated[int | None, typer.Option("--book-id", help="Attach to existing Readwise book ID")] = None,
    category: Annotated[str | None, typer.Option(help="books|articles|tweets|podcasts")] = None,
    note: Annotated[str | None, typer.Option(help="Personal note to attach")] = None,
    tags: Annotated[str | None, typer.Option(help="Comma-separated tags (e.g. 'insight,research')")] = None,
    location: Annotated[str | None, typer.Option(help="Location in source (page number, timestamp, etc.)")] = None,
    location_type: Annotated[str | None, typer.Option("--location-type", help="page|time_offset|order")] = None,
    generated: Annotated[
        bool, typer.Option("--generated", help="Mark as agent-generated (adds .generated tag)")
    ] = False,
    bulk_file: Annotated[str | None, typer.Option("--bulk-file", help="NDJSON file for batch create")] = None,
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    payloads: list[dict[str, Any]] = []
    if bulk_file:
        for entry in load_bulk_payloads(bulk_file):
            payloads.append(_normalize_bulk_payload(entry, generated))
    else:
        payload = _build_highlight_payload(
            text=text,
            text_file=text_file,
            title=title,
            author=author,
            source_url=source_url,
            image_url=image_url,
            book_id=book_id,
            category=category,
            note=note,
            tags_raw=tags,
            location=location,
            location_type=location_type,
            generated=generated,
            require_text=True,
        )
        if "text" not in payload:
            raise typer.BadParameter("Highlight text is required")
        payloads.append(payload)

    for p in payloads:
        _resolve_book_id(client, p)

    results = [client.create_highlight(HighlightCreatePayload.model_validate(p)) for p in payloads]
    print_result(results, fields=HIGHLIGHT_FIELDS, raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@highlight_app.command("show")
def highlight_show(
    ctx: typer.Context,
    highlight_id: Annotated[int, typer.Argument(help="Highlight ID to fetch")],
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    result = client.get_highlight(highlight_id)
    print_result(result, fields=HIGHLIGHT_FIELDS, raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@highlight_app.command("update")
def highlight_update(
    ctx: typer.Context,
    highlight_id: Annotated[int, typer.Argument(help="Highlight ID to update")],
    text: Annotated[str | None, typer.Option(help="New highlight text")] = None,
    text_file: Annotated[str | None, typer.Option("--text-file", help="Path to file containing new text")] = None,
    title: Annotated[str | None, typer.Option(help="New source title")] = None,
    author: Annotated[str | None, typer.Option(help="New author name")] = None,
    source_url: Annotated[str | None, typer.Option("--source-url", help="New source URL")] = None,
    book_id: Annotated[int | None, typer.Option("--book-id", help="Move to different book ID")] = None,
    category: Annotated[str | None, typer.Option(help="books|articles|tweets|podcasts")] = None,
    note: Annotated[str | None, typer.Option(help="New personal note")] = None,
    tags: Annotated[str | None, typer.Option(help="Comma-separated tags to add")] = None,
    location: Annotated[str | None, typer.Option(help="New location in source")] = None,
    location_type: Annotated[str | None, typer.Option("--location-type", help="page|time_offset|order")] = None,
    generated: Annotated[bool, typer.Option("--generated", help="Mark as agent-generated")] = False,
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    payload = _build_highlight_payload(
        text=text,
        text_file=text_file,
        title=title,
        author=author,
        source_url=source_url,
        book_id=book_id,
        category=category,
        note=note,
        tags_raw=tags,
        location=location,
        location_type=location_type,
        generated=generated,
        require_text=False,
        inline_tags=False,
    )
    tag_names = payload.pop("_tags", [])
    if not payload and not tag_names:
        raise typer.BadParameter("No fields to update")
    result = None
    if payload:
        result = client.update_highlight(highlight_id, HighlightUpdatePayload.model_validate(payload))
    for tag_name in tag_names:
        client.tag_highlight(highlight_id, tag_name)
    if result is None:
        result = client.get_highlight(highlight_id)
    print_result(result, fields=HIGHLIGHT_FIELDS, raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@highlight_app.command("delete")
def highlight_delete(
    ctx: typer.Context,
    highlight_id: Annotated[int, typer.Argument(help="Highlight ID to delete")],
    yes: Annotated[bool, typer.Option("--yes", help="Skip confirmation prompt")] = False,
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    if not yes:
        confirmation = input(f"Delete highlight {highlight_id}? [y/N] ")
        if confirmation.strip().lower() not in {"y", "yes"}:
            print("Aborted", file=sys.stderr)
            print_result({"deleted": False}, fields=HIGHLIGHT_FIELDS, raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])
            return
    result = client.delete_highlight(highlight_id)
    print_result(result, fields=HIGHLIGHT_FIELDS, raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@highlights_app.command("list")
def highlights_list(
    ctx: typer.Context,
    book_id: Annotated[int | None, typer.Option("--book-id", help="Filter by Readwise book ID")] = None,
    tag: Annotated[str | None, typer.Option(help="Filter by tag name")] = None,
    updated_after: Annotated[str | None, typer.Option("--updated-after", help="ISO datetime (e.g. 2024-01-15)")] = None,
    updated_before: Annotated[
        str | None, typer.Option("--updated-before", help="ISO datetime (e.g. 2024-01-15)")
    ] = None,
    limit: Annotated[int, typer.Option(help="Max highlights to return")] = 50,
    category: Annotated[str | None, typer.Option(help="books|articles|tweets|podcasts")] = None,
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    params = HighlightListParams(
        book_id=book_id,
        tag=tag,
        updated_after=_normalize_datetime_arg("--updated-after", updated_after) if updated_after else None,
        updated_before=_normalize_datetime_arg("--updated-before", updated_before) if updated_before else None,
        category=category,
    )
    results = []
    for idx, highlight in enumerate(client.list_highlights(params), start=1):
        results.append(highlight)
        if limit and idx >= limit:
            break
    print_result(
        results,
        fields=HIGHLIGHT_FIELDS,
        raw=ctx.obj["raw"],
        dry_run=ctx.obj["dry_run"],
        renderer=render_highlights,
    )


@highlights_app.command("review")
def highlights_review(ctx: typer.Context) -> None:
    """Fetch today's daily review highlights from Readwise."""
    client: ReadwiseClient = ctx.obj["client"]
    result = client.daily_review()
    highlights = [h for h in result.highlights if h.text is not None]
    print_result(
        highlights, fields=HIGHLIGHT_FIELDS, raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"], renderer=render_highlights
    )


@app.command("books")
def books_list(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option(help="Max books to return")] = 50,
    author: Annotated[str | None, typer.Option(help="Filter by author (case-insensitive substring)")] = None,
    title: Annotated[str | None, typer.Option(help="Filter by title (case-insensitive substring)")] = None,
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    params = BookListParams(author=author, title=title)
    author_filter = (params.author or "").lower()
    title_filter = (params.title or "").lower()
    results = []
    for book in client.list_books(params):
        if author_filter and author_filter not in (book.author or "").lower():
            continue
        if title_filter and title_filter not in (book.title or "").lower():
            continue
        results.append(book)
        if limit and len(results) >= limit:
            break
    print_result(results, fields=BOOK_FIELDS, raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@app.command("book")
def book_show(
    ctx: typer.Context,
    book_id: Annotated[int, typer.Argument()],
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    result = client.get_book(book_id)
    print_result(result, fields=BOOK_FIELDS, raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@auth_app.command("validate")
def auth_validate(ctx: typer.Context) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    try:
        client.validate_token()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code == 401:
            message = "Token is invalid. Generate one at https://readwise.io/access_token"
        elif status_code == 403:
            message = "Token is unauthorized. Generate one at https://readwise.io/access_token"
        else:
            status = status_code if status_code is not None else "unknown"
            message = f"Token validation failed with status {status}."
        result = TokenValidationResult(valid=False, status=status_code, message=message)
        print_result(result, fields=None, raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])
        return
    except APIRequestError as exc:
        result = TokenValidationResult(valid=False, message=f"Token validation failed: {exc}")
        print_result(result, fields=None, raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])
        return
    result = TokenValidationResult(valid=True, message="Token is valid for Readwise API.")
    print_result(result, fields=None, raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


def main(argv: Iterable[str] | None = None) -> int:
    """Entry point preserving the existing main(argv) interface for tests."""
    try:
        args = hoist_global_options(list(argv) if argv is not None else sys.argv[1:])
        app(args, standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
