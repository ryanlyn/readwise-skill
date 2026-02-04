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
    DailyReviewParams,
    DailyReviewResponse,
    DeleteResult,
    DryRunResult,
    Highlight,
    HighlightCreatePayload,
    HighlightListParams,
    HighlightUpdatePayload,
    build_location_payload,
    build_tags,
    get_readwise_token,
    parse_iso_datetime,
    parse_tags,
    print_result,
    request_with_backoff,
    resolve_highlight_text,
)
from readwise_common.utils import load_bulk_payloads

DEFAULT_BASE_URL = "https://readwise.io/api/v2"
USER_AGENT = "readwise-skill-cli/0.1"


class ReadwiseClient:
    def __init__(self, token: str, *, base_url: str | None = None, dry_run: bool = False):
        self.base_url = (base_url or os.getenv("READWISE_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
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
            for item in payload.get("results", []):
                yield item
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

    def daily_review(self, params: DailyReviewParams) -> DailyReviewResponse:
        query: dict[str, Any] = {}
        if params.updated_after is not None:
            query["updatedAfter"] = params.updated_after
        if params.updated_before is not None:
            query["updatedBefore"] = params.updated_before
        query["limit"] = params.limit
        response = self._request("get", "/export/", params=query)
        return DailyReviewResponse.model_validate(response.json())

    def list_books(self, params: BookListParams) -> Iterable[Book]:
        for item in self.paginate("/books/"):
            yield Book.model_validate(item)

    def get_book(self, book_id: int) -> Book:
        response = self._request("get", f"/books/{book_id}/")
        return Book.model_validate(response.json())


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
    book_id: int | None,
    category: str | None,
    note: str | None,
    tags_raw: str | None,
    location: str | None,
    location_type: str | None,
    generated: bool,
    require_text: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    should_load_text = bool(text or text_file or not sys.stdin.isatty())
    if should_load_text:
        try:
            payload["text"] = resolve_highlight_text(text, text_file)
        except ValueError:
            if require_text:
                raise
    for field, value in [("title", title), ("author", author), ("source_url", source_url), ("note", note)]:
        if value:
            payload[field] = value
    if book_id:
        payload["book_id"] = book_id
    if category:
        payload["category"] = category

    tag_list = build_tags(parse_tags(tags_raw), generated)
    if tag_list:
        payload["tags"] = tag_list

    payload.update(build_location_payload(location, location_type, generated))
    return payload


def _normalize_bulk_payload(entry: dict[str, Any], default_generated: bool) -> dict[str, Any]:
    payload = dict(entry)
    text = payload.get("text")
    if not text:
        raise ValueError("Bulk highlight payloads require 'text'")
    tags = payload.get("tags") or []
    if isinstance(tags, str):
        tags = parse_tags(tags)
    generated = payload.pop("generated", default_generated)
    payload["tags"] = build_tags(tags, generated)
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
        for field, book_attr in [("author", "author"), ("source_url", "source_url"), ("category", "category"), ("source_type", "source")]:
            value = getattr(book, book_attr, None)
            if value:
                payload.setdefault(field, value)


# ---------------------------------------------------------------------------
# Typer CLI
# ---------------------------------------------------------------------------

app = typer.Typer(help="Interact with the Readwise Original API")
highlight_app = typer.Typer(help="Operate on a single highlight")
highlights_app = typer.Typer(help="List or review highlights")

app.add_typer(highlight_app, name="highlight")
app.add_typer(highlights_app, name="highlights")


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
    text: Annotated[str | None, typer.Option(help="Highlight text. Falls back to --text-file or stdin.")] = None,
    text_file: Annotated[str | None, typer.Option("--text-file", help="Path to file containing highlight text")] = None,
    title: Annotated[str | None, typer.Option(help="Optional title to associate")] = None,
    author: Annotated[str | None, typer.Option(help="Author name")] = None,
    source_url: Annotated[str | None, typer.Option("--source-url", help="Source URL")] = None,
    book_id: Annotated[int | None, typer.Option("--book-id", help="Existing Readwise book ID")] = None,
    category: Annotated[str | None, typer.Option(help="Highlight category")] = None,
    note: Annotated[str | None, typer.Option(help="Personal note to attach")] = None,
    tags: Annotated[str | None, typer.Option(help="Comma-separated tags")] = None,
    location: Annotated[str | None, typer.Option()] = None,
    location_type: Annotated[str | None, typer.Option("--location-type", help="Location type")] = None,
    generated: Annotated[bool, typer.Option("--generated", help="Tag highlight as synthetic")] = False,
    bulk_file: Annotated[str | None, typer.Option("--bulk-file", help="NDJSON payloads for batch create")] = None,
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    payloads: list[dict[str, Any]] = []
    if bulk_file:
        for entry in load_bulk_payloads(bulk_file):
            payloads.append(_normalize_bulk_payload(entry, generated))
    else:
        payload = _build_highlight_payload(
            text=text, text_file=text_file, title=title, author=author,
            source_url=source_url, book_id=book_id, category=category, note=note,
            tags_raw=tags, location=location, location_type=location_type,
            generated=generated, require_text=True,
        )
        if "text" not in payload:
            raise typer.BadParameter("Highlight text is required")
        payloads.append(payload)

    for p in payloads:
        _resolve_book_id(client, p)

    results = [client.create_highlight(HighlightCreatePayload.model_validate(p)) for p in payloads]
    print_result(results, entity="highlight", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@highlight_app.command("show")
def highlight_show(
    ctx: typer.Context,
    highlight_id: Annotated[int, typer.Argument()],
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    result = client.get_highlight(highlight_id)
    print_result(result, entity="highlight", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@highlight_app.command("update")
def highlight_update(
    ctx: typer.Context,
    highlight_id: Annotated[int, typer.Argument()],
    text: Annotated[str | None, typer.Option(help="Highlight text")] = None,
    text_file: Annotated[str | None, typer.Option("--text-file")] = None,
    title: Annotated[str | None, typer.Option()] = None,
    author: Annotated[str | None, typer.Option()] = None,
    source_url: Annotated[str | None, typer.Option("--source-url")] = None,
    book_id: Annotated[int | None, typer.Option("--book-id")] = None,
    category: Annotated[str | None, typer.Option()] = None,
    note: Annotated[str | None, typer.Option()] = None,
    tags: Annotated[str | None, typer.Option(help="Comma-separated tags")] = None,
    location: Annotated[str | None, typer.Option()] = None,
    location_type: Annotated[str | None, typer.Option("--location-type")] = None,
    generated: Annotated[bool, typer.Option("--generated")] = False,
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    payload = _build_highlight_payload(
        text=text, text_file=text_file, title=title, author=author,
        source_url=source_url, book_id=book_id, category=category, note=note,
        tags_raw=tags, location=location, location_type=location_type,
        generated=generated, require_text=False,
    )
    if not payload:
        raise typer.BadParameter("No fields to update")
    result = client.update_highlight(highlight_id, HighlightUpdatePayload.model_validate(payload))
    print_result(result, entity="highlight", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@highlight_app.command("delete")
def highlight_delete(
    ctx: typer.Context,
    highlight_id: Annotated[int, typer.Argument()],
    yes: Annotated[bool, typer.Option("--yes", help="Do not prompt for confirmation")] = False,
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    if not yes:
        confirmation = input(f"Delete highlight {highlight_id}? [y/N] ")
        if confirmation.strip().lower() not in {"y", "yes"}:
            print("Aborted", file=sys.stderr)
            print_result({"deleted": False}, entity="highlight", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])
            return
    result = client.delete_highlight(highlight_id)
    print_result(result, entity="highlight", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@highlights_app.command("list")
def highlights_list(
    ctx: typer.Context,
    book_id: Annotated[int | None, typer.Option("--book-id")] = None,
    tag: Annotated[str | None, typer.Option()] = None,
    updated_after: Annotated[str | None, typer.Option("--updated-after")] = None,
    updated_before: Annotated[str | None, typer.Option("--updated-before")] = None,
    limit: Annotated[int, typer.Option()] = 50,
    category: Annotated[str | None, typer.Option()] = None,
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
    print_result(results, entity="highlight", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@highlights_app.command("review")
def highlights_review(
    ctx: typer.Context,
    since: Annotated[str | None, typer.Option(help="ISO timestamp or YYYY-MM-DD")] = None,
    until: Annotated[str | None, typer.Option(help="ISO timestamp or YYYY-MM-DD")] = None,
    limit: Annotated[int, typer.Option()] = 50,
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    params = DailyReviewParams(
        updated_after=_normalize_datetime_arg("--since", since) if since else None,
        updated_before=_normalize_datetime_arg("--until", until) if until else None,
        limit=limit,
    )
    result = client.daily_review(params)
    print_result(result, entity="highlight", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@app.command("books")
def books_list(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option()] = 50,
    author: Annotated[str | None, typer.Option()] = None,
    title: Annotated[str | None, typer.Option(help="Filter by title (case-insensitive substring match)")] = None,
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
    print_result(results, entity="book", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@app.command("book")
def book_show(
    ctx: typer.Context,
    book_id: Annotated[int, typer.Argument()],
) -> None:
    client: ReadwiseClient = ctx.obj["client"]
    result = client.get_book(book_id)
    print_result(result, entity="book", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


def main(argv: Iterable[str] | None = None) -> int:
    """Entry point preserving the existing main(argv) interface for tests."""
    try:
        app(list(argv) if argv is not None else None, standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
