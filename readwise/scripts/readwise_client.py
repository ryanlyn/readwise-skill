"""Comprehensive CLI for interacting with the Readwise Original API."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Iterable, List, Optional

import requests

from rw_shared import (
    build_location_payload,
    build_tags,
    get_readwise_token,
    parse_iso_datetime,
    parse_tags,
    render_output,
    request_with_backoff,
    resolve_highlight_text,
)
from rw_shared.utils import load_bulk_payloads

BASE_URL = "https://readwise.io/api/v2"
USER_AGENT = "readwise-skill-cli/0.1"


class ReadwiseClient:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Token {token}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{BASE_URL}{path}"
        return request_with_backoff(self.session, method, url, **kwargs)

    def paginate(self, path: str, params: Optional[Dict[str, Any]] = None) -> Iterable[Dict[str, Any]]:
        cursor: Optional[str] = None
        params = dict(params or {})
        while True:
            scoped = dict(params)
            if cursor:
                scoped["pageCursor"] = cursor
            response = self._request("get", path, params=scoped)
            payload = response.json()
            for item in payload.get("results", []):
                yield item
            cursor = payload.get("nextPageCursor")
            if not cursor:
                break

    def create_highlight(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._request("post", "/highlights/", json=payload)
        return response.json()

    def list_highlights(self, params: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        return self.paginate("/highlights/", params)

    def get_highlight(self, highlight_id: int) -> Dict[str, Any]:
        response = self._request("get", f"/highlights/{highlight_id}/")
        return response.json()

    def update_highlight(self, highlight_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._request("patch", f"/highlights/{highlight_id}/", json=payload)
        return response.json()

    def delete_highlight(self, highlight_id: int) -> None:
        self._request("delete", f"/highlights/{highlight_id}/")

    def daily_review(self, params: Dict[str, Any]) -> Dict[str, Any]:
        response = self._request("get", "/export/", params=params)
        return response.json()

    def list_books(self, params: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        return self.paginate("/books/", params)

    def get_book(self, book_id: int) -> Dict[str, Any]:
        response = self._request("get", f"/books/{book_id}/")
        return response.json()


def _add_common_create_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--text", help="Highlight text. Falls back to --text-file or stdin.")
    parser.add_argument("--text-file", help="Path to file containing highlight text")
    parser.add_argument("--title", help="Optional title to associate")
    parser.add_argument("--author", help="Author name")
    parser.add_argument("--source-url", dest="source_url", help="Source URL")
    parser.add_argument("--book-id", type=int, help="Existing Readwise book ID")
    parser.add_argument("--category", choices=["articles", "books", "tweets", "podcasts", "supplementals"], help="Highlight category")
    parser.add_argument("--note", help="Personal note to attach")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--location")
    parser.add_argument("--location-type", dest="location_type", help="Location type (page, order, none, etc.)")
    parser.add_argument("--generated", action="store_true", help="Tag highlight as synthetic by appending .generated")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interact with the Readwise Original API")
    parser.add_argument("--token", help="Override READWISE_TOKEN env var")
    parser.add_argument("--output", choices=["json", "markdown", "plain"], default="json")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without calling the API")
    subparsers = parser.add_subparsers(dest="command", required=True)

    highlight = subparsers.add_parser("highlight", help="Operate on a single highlight")
    highlight_sub = highlight.add_subparsers(dest="highlight_command", required=True)

    create = highlight_sub.add_parser("create", help="Create a highlight")
    _add_common_create_args(create)
    create.add_argument("--bulk-file", help="NDJSON payloads for batch create")

    show = highlight_sub.add_parser("show", help="Fetch a highlight by id")
    show.add_argument("highlight_id", type=int)

    update = highlight_sub.add_parser("update", help="Patch highlight fields")
    update.add_argument("highlight_id", type=int)
    _add_common_create_args(update)

    delete = highlight_sub.add_parser("delete", help="Delete a highlight")
    delete.add_argument("highlight_id", type=int)
    delete.add_argument("--yes", action="store_true", help="Do not prompt for confirmation")

    highlights = subparsers.add_parser("highlights", help="List or review highlights")
    highlights_sub = highlights.add_subparsers(dest="highlights_command", required=True)

    listing = highlights_sub.add_parser("list", help="List highlights with filters")
    listing.add_argument("--book-id", type=int)
    listing.add_argument("--tag")
    listing.add_argument("--updated-after")
    listing.add_argument("--updated-before")
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--category", choices=["articles", "books", "tweets", "podcasts", "supplementals"])

    review = highlights_sub.add_parser("review", help="Daily review export")
    review.add_argument("--since", help="ISO timestamp or YYYY-MM-DD")
    review.add_argument("--until", help="ISO timestamp or YYYY-MM-DD")
    review.add_argument("--limit", type=int, default=50)

    books = subparsers.add_parser("books", help="List books")
    books.add_argument("--limit", type=int, default=50)
    books.add_argument("--author")

    book = subparsers.add_parser("book", help="Fetch a single book")
    book.add_argument("book_id", type=int)

    return parser


def _build_highlight_payload(
    args: argparse.Namespace,
    *,
    require_text: bool,
    override_generated: Optional[bool] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    generated = args.generated if override_generated is None else override_generated
    should_load_text = bool(getattr(args, "text", None) or getattr(args, "text_file", None) or not sys.stdin.isatty())
    if should_load_text:
        try:
            payload["text"] = resolve_highlight_text(getattr(args, "text", None), getattr(args, "text_file", None))
        except ValueError:
            if require_text:
                raise
    for field in ("title", "author", "source_url", "note"):
        value = getattr(args, field, None)
        if value:
            payload[field if field != "source_url" else "source_url"] = value
    if getattr(args, "book_id", None):
        payload["book_id"] = args.book_id
    if getattr(args, "category", None):
        payload["category"] = args.category

    tags = build_tags(parse_tags(getattr(args, "tags", None)), generated)
    if tags:
        payload["tags"] = tags

    payload.update(build_location_payload(getattr(args, "location", None), getattr(args, "location_type", None), generated))
    return payload


def _normalize_bulk_payload(entry: Dict[str, Any], default_generated: bool) -> Dict[str, Any]:
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


def handle_highlight_create(client: ReadwiseClient, args: argparse.Namespace) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    if args.bulk_file:
        for entry in load_bulk_payloads(args.bulk_file):
            payloads.append(_normalize_bulk_payload(entry, args.generated))
    else:
        payload = _build_highlight_payload(args, require_text=True)
        if "text" not in payload:
            raise ValueError("Highlight text is required")
        payloads.append(payload)

    if args.dry_run:
        for payload in payloads:
            print(json.dumps(payload, indent=2))
        return payloads

    results = [client.create_highlight(payload) for payload in payloads]
    return results


def handle_highlight_show(client: ReadwiseClient, args: argparse.Namespace) -> Dict[str, Any]:
    return client.get_highlight(args.highlight_id)


def handle_highlight_update(client: ReadwiseClient, args: argparse.Namespace) -> Dict[str, Any]:
    payload = _build_highlight_payload(args, require_text=False)
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return payload
    if not payload:
        raise ValueError("No fields to update")
    return client.update_highlight(args.highlight_id, payload)


def handle_highlight_delete(client: ReadwiseClient, args: argparse.Namespace) -> Dict[str, Any]:
    if not args.yes:
        confirmation = input(f"Delete highlight {args.highlight_id}? [y/N] ")
        if confirmation.strip().lower() not in {"y", "yes"}:
            print("Aborted", file=sys.stderr)
            return {"deleted": False}
    if args.dry_run:
        print(json.dumps({"deleted_id": args.highlight_id}, indent=2))
        return {"deleted": False}
    client.delete_highlight(args.highlight_id)
    return {"deleted": True, "highlight_id": args.highlight_id}


def handle_highlights_list(client: ReadwiseClient, args: argparse.Namespace) -> List[Dict[str, Any]]:
    params = {}
    if args.book_id:
        params["book_id"] = args.book_id
    if args.tag:
        params["tag"] = args.tag
    if args.updated_after:
        params["updatedAfter"] = _normalize_datetime_arg("--updated-after", args.updated_after)
    if args.updated_before:
        params["updatedBefore"] = _normalize_datetime_arg("--updated-before", args.updated_before)
    if args.category:
        params["category"] = args.category
    results = []
    for idx, highlight in enumerate(client.list_highlights(params), start=1):
        results.append(highlight)
        if args.limit and idx >= args.limit:
            break
    return results


def handle_highlights_review(client: ReadwiseClient, args: argparse.Namespace) -> Dict[str, Any]:
    params = {}
    if args.since:
        params["updatedAfter"] = _normalize_datetime_arg("--since", args.since)
    if args.until:
        params["updatedBefore"] = _normalize_datetime_arg("--until", args.until)
    params["limit"] = args.limit
    return client.daily_review(params)


def handle_books_list(client: ReadwiseClient, args: argparse.Namespace) -> List[Dict[str, Any]]:
    params = {}
    if args.author:
        params["author"] = args.author
    results = []
    for idx, book in enumerate(client.list_books(params), start=1):
        results.append(book)
        if args.limit and idx >= args.limit:
            break
    return results


def handle_book_show(client: ReadwiseClient, args: argparse.Namespace) -> Dict[str, Any]:
    return client.get_book(args.book_id)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    token = get_readwise_token(args.token).value
    client = ReadwiseClient(token)

    if args.command == "highlight":
        if args.highlight_command == "create":
            result = handle_highlight_create(client, args)
        elif args.highlight_command == "show":
            result = handle_highlight_show(client, args)
        elif args.highlight_command == "update":
            result = handle_highlight_update(client, args)
        elif args.highlight_command == "delete":
            result = handle_highlight_delete(client, args)
        else:
            parser.error("Unknown highlight subcommand")
    elif args.command == "highlights":
        if args.highlights_command == "list":
            result = handle_highlights_list(client, args)
        elif args.highlights_command == "review":
            result = handle_highlights_review(client, args)
        else:
            parser.error("Unknown highlights subcommand")
    elif args.command == "books":
        result = handle_books_list(client, args)
    elif args.command == "book":
        result = handle_book_show(client, args)
    else:
        parser.error("Unknown command")

    print(render_output(result, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
