"""Utilities for interacting with the Readwise Reader API."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import requests

BASE_URL = "https://readwise.io/api/reader"
DEFAULT_PAGE_SIZE = 100


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Token {token}"}


def get_token(explicit: Optional[str] = None) -> str:
    token = explicit or os.getenv("READWISE_READER_TOKEN")
    if not token:
        raise RuntimeError("Set READWISE_READER_TOKEN or pass --token")
    return token


@dataclass
class ReaderClient:
    session: requests.Session

    @classmethod
    def from_env(cls, token_override: Optional[str] = None) -> "ReaderClient":
        token = get_token(token_override)
        session = requests.Session()
        session.headers.update(_headers(token))
        return cls(session=session)

    def list_documents(self, **filters: Any) -> Iterable[Dict[str, Any]]:
        params = {"page_size": DEFAULT_PAGE_SIZE, **filters}
        next_cursor: Optional[str] = None
        while True:
            current = dict(params)
            if next_cursor:
                current["page_cursor"] = next_cursor
            resp = self.session.get(f"{BASE_URL}/document/list", params=current, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            for doc in payload.get("results", []):
                yield doc
            next_cursor = payload.get("nextPageCursor")
            if not next_cursor:
                break

    def add_url(self, url: str, *, dry_run: bool = False) -> Dict[str, Any]:
        payload = {"url": url}
        if dry_run:
            print(f"DRY RUN: would POST {payload}")
            return payload
        resp = self.session.post(f"{BASE_URL}/document/add", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def health_check(self) -> bool:
        resp = self.session.get(f"{BASE_URL}/auth/test", timeout=15)
        return resp.ok


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Readwise Reader helper")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Verify credentials")
    check.add_argument("--token")

    list_docs = sub.add_parser("list-documents", help="Print unread Reader documents")
    list_docs.add_argument("--token")
    list_docs.add_argument("--category", default="new")
    list_docs.add_argument("--limit", type=int, default=10)

    add = sub.add_parser("add-url", help="Save a URL into Reader")
    add.add_argument("url")
    add.add_argument("--token")
    add.add_argument("--dry-run", action="store_true")

    return parser.parse_args(list(argv) if argv is not None else None)


def main() -> int:
    args = parse_args()

    if args.command == "check":
        client = ReaderClient.from_env(args.token)
        ok = client.health_check()
        print("Auth OK" if ok else "Auth failed", file=sys.stderr)
        return 0 if ok else 1

    if args.command == "list-documents":
        client = ReaderClient.from_env(args.token)
        for idx, doc in enumerate(client.list_documents(category=args.category), start=1):
            print(doc)
            if args.limit and idx >= args.limit:
                break
        return 0

    if args.command == "add-url":
        client = ReaderClient.from_env(args.token)
        result = client.add_url(args.url, dry_run=args.dry_run)
        print(result)
        return 0

    raise ValueError("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
