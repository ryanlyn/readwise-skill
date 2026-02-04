"""CLI for interacting with the Readwise Reader API."""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict, Iterable, List, Optional

import requests

from readwise_common import (
    DISPLAY_FIELDS,
    build_tags,
    get_reader_token,
    parse_iso_datetime,
    parse_tags,
    render_output,
    request_with_backoff,
    select_fields,
)
from readwise_common.http import APIRequestError

DEFAULT_BASE_URL = "https://readwise.io/api/v3"
AUTH_URL = "https://readwise.io/api/v2/auth/"
USER_AGENT = "readwise-reader-skill/0.1"


def _load_document_body(args: argparse.Namespace) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if args.url:
        payload["url"] = args.url
    if args.content:
        payload["html"] = args.content
    if args.file:
        raise ValueError("--file uploads are not supported by Reader API v3")
    for field in ("title", "summary"):
        value = getattr(args, field, None)
        if value:
            payload[field] = value
    tags = build_tags(parse_tags(getattr(args, "tags", None)), args.generated)
    if tags:
        payload["tags"] = tags
    if args.category:
        payload["category"] = args.category
    if args.labels:
        payload["labels"] = parse_tags(args.labels)
    return payload


class ReaderClient:
    def __init__(self, token: str, *, base_url: Optional[str] = None, auth_url: Optional[str] = None, dry_run: bool = False):
        resolved = base_url or os.getenv("READWISE_READER_API_BASE_URL") or DEFAULT_BASE_URL
        self.base_url = resolved.rstrip("/")
        resolved_auth = auth_url or os.getenv("READWISE_READER_AUTH_URL") or AUTH_URL
        self.auth_url = resolved_auth
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Token {token}",
                "User-Agent": USER_AGENT,
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        return request_with_backoff(self.session, method, url, **kwargs)

    def create_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(payload)
        if "file_path" in payload:
            raise ValueError("File uploads are not supported by the Reader API v3 endpoints.")
        if self.dry_run:
            return {"dry_run": True, "request_payload": payload}
        response = self._request("post", "/save/", json=payload)
        return response.json()

    def list_documents(self, params: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        cursor: Optional[str] = None
        params = dict(params)
        while True:
            scoped = dict(params)
            if cursor:
                scoped["pageCursor"] = cursor
            response = self._request("get", "/list/", params=scoped)
            payload = response.json()
            for doc in payload.get("results", []):
                yield doc
            cursor = payload.get("nextPageCursor")
            if not cursor:
                break

    def update_document(self, document_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.dry_run:
            return {"dry_run": True, "document_id": document_id, "request_payload": payload}
        response = self._request("patch", f"/update/{document_id}/", json=payload)
        return response.json()

    def delete_document(self, document_id: str) -> Dict[str, Any]:
        if self.dry_run:
            return {"dry_run": True, "document_id": document_id, "action": "delete"}
        self._request("delete", f"/delete/{document_id}/")
        return {"deleted": True, "document_id": document_id}

    def validate_token(self) -> None:
        response = request_with_backoff(self.session, "get", self.auth_url)
        if response.status_code != 204:
            error = requests.HTTPError("Unexpected auth response", response=response)
            raise error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interact with Readwise Reader API")
    parser.add_argument("--token", help="Override READWISE_TOKEN")
    parser.add_argument("--raw", action="store_true", help="Output full JSON (all fields)")
    parser.add_argument("--dry-run", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    docs = subparsers.add_parser("docs", help="Document operations")
    docs_sub = docs.add_subparsers(dest="docs_command", required=True)

    create = docs_sub.add_parser("create", help="Create a document")
    create.add_argument("--url")
    create.add_argument("--content")
    create.add_argument("--file")
    create.add_argument("--title")
    create.add_argument("--summary")
    create.add_argument("--category")
    create.add_argument("--tags", help="Comma-separated tags")
    create.add_argument("--labels", help="Comma-separated labels")
    create.add_argument("--generated", action="store_true")

    listing = docs_sub.add_parser("list", help="List documents")
    listing.add_argument("--id", dest="document_id")
    listing.add_argument("--category")
    listing.add_argument("--tag")
    listing.add_argument("--location")
    listing.add_argument("--updated-after")
    listing.add_argument("--limit", type=int, default=50)

    update = docs_sub.add_parser("update", help="Update metadata/state")
    update.add_argument("document_id")
    update.add_argument("--title")
    update.add_argument("--summary")
    update.add_argument("--category")
    update.add_argument("--labels")
    update.add_argument("--tags")
    update.add_argument("--state", choices=["new", "later", "archive"])

    pull = docs_sub.add_parser("pull", help="Export documents since timestamp")
    pull.add_argument("--location")
    pull.add_argument("--since")
    pull.add_argument("--limit", type=int, default=50)

    auth = subparsers.add_parser("auth", help="Authentication helpers")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)
    auth_sub.add_parser("validate", help="Validate the configured Reader token")

    return parser


def handle_create(client: ReaderClient, args: argparse.Namespace) -> Dict[str, Any]:
    payload = _load_document_body(args)
    if not payload.get("url") and not payload.get("html") and not payload.get("source_url"):
        raise ValueError("Provide --url or --content")
    return client.create_document(payload)


def handle_list(client: ReaderClient, args: argparse.Namespace) -> List[Dict[str, Any]]:
    params = {}
    if args.document_id:
        params["id"] = args.document_id
    if args.category:
        params["category"] = args.category
    if args.tag:
        params["tag"] = args.tag
    if args.location:
        params["location"] = args.location
    if args.updated_after:
        params["updatedAfter"] = parse_iso_datetime(args.updated_after)
    docs = []
    for idx, doc in enumerate(client.list_documents(params), start=1):
        docs.append(doc)
        if args.limit and idx >= args.limit:
            break
    return docs


def handle_update(client: ReaderClient, args: argparse.Namespace) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for field in ("title", "summary", "category"):
        value = getattr(args, field, None)
        if value:
            payload[field] = value
    if args.labels:
        payload["labels"] = parse_tags(args.labels)
    if args.tags:
        payload["tags"] = parse_tags(args.tags)
    if args.state:
        payload["location"] = args.state
    if not payload:
        raise ValueError("No fields to update")
    return client.update_document(args.document_id, payload)


def handle_pull(client: ReaderClient, args: argparse.Namespace) -> List[Dict[str, Any]]:
    params = {}
    if args.location:
        params["location"] = args.location
    if args.since:
        params["updatedAfter"] = parse_iso_datetime(args.since)
    docs = []
    for idx, doc in enumerate(client.list_documents(params), start=1):
        docs.append(doc)
        if args.limit and idx >= args.limit:
            break
    return docs


def handle_validate(client: ReaderClient) -> Dict[str, Any]:
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
        return {"valid": False, "status": status_code, "message": message}
    except APIRequestError as exc:
        return {"valid": False, "message": f"Token validation failed: {exc}"}
    return {"valid": True, "message": "Token is valid for Readwise Reader API."}


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    token = get_reader_token(args.token).value
    client = ReaderClient(token, dry_run=args.dry_run)

    entity = "document"
    if args.command == "docs":
        if args.docs_command == "create":
            result = handle_create(client, args)
        elif args.docs_command == "list":
            result = handle_list(client, args)
        elif args.docs_command == "update":
            result = handle_update(client, args)
        elif args.docs_command == "pull":
            result = handle_pull(client, args)
        else:
            parser.error("Unknown docs subcommand")
    elif args.command == "auth":
        entity = ""
        if args.auth_command == "validate":
            result = handle_validate(client)
        else:
            parser.error("Unknown auth subcommand")
    else:
        parser.error("Unknown command")

    if args.raw:
        print(render_output(result, "json"))
    else:
        if not args.dry_run:
            fields = DISPLAY_FIELDS.get(entity)
            if fields:
                result = select_fields(result, fields)
        print(render_output(result, "markdown"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
