"""Helper utilities for interacting with the Readwise Original API."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import requests

BASE_URL = "https://readwise.io/api/v2"
DEFAULT_PAGE_SIZE = 100


def _build_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Token {token}", "Content-Type": "application/json"}


def get_token(explicit: Optional[str] = None) -> str:
    token = explicit or os.getenv("READWISE_TOKEN")
    if not token:
        raise RuntimeError("Set READWISE_TOKEN or pass --token")
    return token


@dataclass
class ReadwiseClient:
    token: str
    session: requests.Session

    @classmethod
    def from_env(cls, token_override: Optional[str] = None) -> "ReadwiseClient":
        token = get_token(token_override)
        session = requests.Session()
        session.headers.update(_build_headers(token))
        return cls(token=token, session=session)

    def paginate(self, path: str, params: Optional[Dict[str, Any]] = None) -> Iterable[Dict[str, Any]]:
        params = {"page_size": DEFAULT_PAGE_SIZE, **(params or {})}
        next_cursor: Optional[str] = None
        while True:
            local_params = dict(params)
            if next_cursor:
                local_params["page_cursor"] = next_cursor
            resp = self.session.get(f"{BASE_URL}{path}", params=local_params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            for item in payload.get("results", []):
                yield item
            next_cursor = payload.get("nextPageCursor")
            if not next_cursor:
                break

    def list_highlights(self, **filters: Any) -> Iterable[Dict[str, Any]]:
        return self.paginate("/highlights/", filters)

    def list_books(self, **filters: Any) -> Iterable[Dict[str, Any]]:
        return self.paginate("/books/", filters)

    def update_highlight(self, highlight_id: int, **fields: Any) -> Dict[str, Any]:
        resp = self.session.patch(f"{BASE_URL}/highlights/{highlight_id}/", json=fields, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def health_check(self) -> bool:
        resp = self.session.get(f"{BASE_URL}/auth/test", timeout=15)
        return resp.ok


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Utility wrapper around the Readwise API")
    parser.add_argument("command", choices=["check", "list-highlights", "list-books"], help="Action to perform")
    parser.add_argument("--token", dest="token", help="Override token instead of READWISE_TOKEN")
    parser.add_argument("--updated-after", dest="updated_after", help="ISO timestamp filter for list commands")
    parser.add_argument("--limit", type=int, default=10, help="Max rows to print (0 means unlimited)")
    return parser.parse_args(list(argv) if argv is not None else None)


def main() -> int:
    args = parse_args()
    client = ReadwiseClient.from_env(args.token)

    if args.command == "check":
        ok = client.health_check()
        print("Auth OK" if ok else "Auth failed", file=sys.stderr)
        return 0 if ok else 1

    iterator: Iterable[Dict[str, Any]]
    if args.command == "list-highlights":
        iterator = client.list_highlights(updated_after=args.updated_after)
    elif args.command == "list-books":
        iterator = client.list_books(updated_after=args.updated_after)
    else:
        raise ValueError("Unknown command")

    for idx, item in enumerate(iterator, start=1):
        print(item)
        if args.limit and idx >= args.limit:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
