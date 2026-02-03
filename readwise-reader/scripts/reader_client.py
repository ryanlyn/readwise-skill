"""CLI for interacting with the Readwise Reader API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

from rw_shared import (
    build_tags,
    get_reader_token,
    parse_tags,
    render_output,
    request_with_backoff,
    resolve_highlight_text,
)
from rw_shared.http import APIRequestError

BASE_URL = "https://readwise.io/api/reader"
AUTH_URL = "https://readwise.io/api/v2/auth/"
USER_AGENT = "readwise-reader-skill/0.1"


def _load_document_body(args: argparse.Namespace) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if args.url:
        payload["url"] = args.url
    if args.content:
        payload["html"] = args.content
    if args.file:
        payload["file_path"] = args.file
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
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Token {token}",
                "User-Agent": USER_AGENT,
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{BASE_URL}{path}"
        return request_with_backoff(self.session, method, url, **kwargs)

    def create_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if "file_path" in payload:
            file_path = Path(payload.pop("file_path"))
            file_bytes = file_path.read_bytes()
            upload_resp = self._request("post", "/document/upload", files={"file": (file_path.name, file_bytes)})
            upload_json = upload_resp.json()
            payload["source_url"] = upload_json["source_url"]
        response = self._request("post", "/document/add", json=payload)
        return response.json()

    def list_documents(self, params: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        cursor: Optional[str] = None
        params = dict(params)
        while True:
            scoped = dict(params)
            if cursor:
                scoped["pageCursor"] = cursor
            response = self._request("get", "/document/list", params=scoped)
            payload = response.json()
            for doc in payload.get("results", []):
                yield doc
            cursor = payload.get("nextPageCursor")
            if not cursor:
                break

    def update_document(self, document_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._request("patch", f"/document/{document_id}", json=payload)
        return response.json()

    def validate_token(self) -> None:
        response = request_with_backoff(self.session, "get", AUTH_URL)
        if response.status_code != 204:
            error = requests.HTTPError("Unexpected auth response", response=response)
            raise error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interact with Readwise Reader API")
    parser.add_argument("--token", help="Override READWISE_READER_TOKEN")
    parser.add_argument("--output", choices=["json", "markdown", "plain"], default="json")
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
    if (
        not payload.get("url")
        and not payload.get("html")
        and not payload.get("source_url")
        and not payload.get("file_path")
    ):
        raise ValueError("Provide --url, --content, or --file")
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return payload
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
        params["updatedAfter"] = args.updated_after
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
    if args.state:
        payload["document_status"] = args.state
    if not payload:
        raise ValueError("No fields to update")
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return payload
    return client.update_document(args.document_id, payload)


def handle_pull(client: ReaderClient, args: argparse.Namespace) -> List[Dict[str, Any]]:
    params = {}
    if args.location:
        params["location"] = args.location
    if args.since:
        params["updatedAfter"] = args.since
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
    client = ReaderClient(token)

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
        if args.auth_command == "validate":
            result = handle_validate(client)
        else:
            parser.error("Unknown auth subcommand")
    else:
        parser.error("Unknown command")

    print(render_output(result, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
