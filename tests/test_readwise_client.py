from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Iterable, List

import pytest

from readwise.scripts.readwise_client import ReadwiseClient


@pytest.fixture
def readwise_client() -> ReadwiseClient:
    token = os.environ["READWISE_TOKEN"]
    base_url = os.environ["READWISE_API_BASE_URL"]
    return ReadwiseClient(token, base_url=base_url)


def _collect(iterable: Iterable[Dict]) -> List[Dict]:
    return list(iterable)


def test_list_highlights_filters_by_book(readwise_client: ReadwiseClient) -> None:
    results = _collect(readwise_client.list_highlights({"book_id": 1337}))
    assert results, "Expected highlights for book 1337"
    for highlight in results:
        assert highlight["book_id"] == 1337


def test_highlight_crud_flow(readwise_client: ReadwiseClient) -> None:
    payload = {
        "text": "Integration test highlight",
        "note": "created via tests",
        "location": 1,
        "location_type": "order",
        "tags": ["integration-test"],
    }
    created = readwise_client.create_highlight(payload)
    highlight_id = created["id"]
    assert created["text"] == payload["text"]
    assert created["color"] == "yellow"

    updated = readwise_client.update_highlight(highlight_id, {"color": "pink", "note": "updated"})
    assert updated["color"] == "pink"
    assert updated["note"] == "updated"

    readwise_client.delete_highlight(highlight_id)
    remaining = _collect(readwise_client.list_highlights({"book_id": created["book_id"]}))
    remaining_ids = {item["id"] for item in remaining}
    assert highlight_id not in remaining_ids


def test_books_list(readwise_client: ReadwiseClient) -> None:
    books = _collect(readwise_client.list_books({}))
    titles = {book["title"] for book in books}
    assert "Meditations" in titles
    assert "Design Systems and Team Flow" in titles


def test_get_highlight(readwise_client: ReadwiseClient) -> None:
    highlight = readwise_client.get_highlight(13)
    assert highlight["id"] == 13
    assert highlight["book_id"] == 1337


def test_highlights_paginate_with_cursor(readwise_client: ReadwiseClient) -> None:
    for idx in range(3):
        readwise_client.create_highlight(
            {
                "text": f"Paginated highlight {idx}",
                "note": "pagination-test",
                "location": idx + 1,
                "location_type": "order",
            }
        )
    highlights = _collect(readwise_client.list_highlights({"page_size": 2}))
    assert len(highlights) >= 5
    assert len({item["id"] for item in highlights}) == len(highlights)


def test_daily_review_filters_by_date(readwise_client: ReadwiseClient) -> None:
    response = readwise_client.daily_review({"updatedAfter": "2020-12-31T00:00:00+00:00", "limit": 10})
    results = response["results"]
    assert results

    def _parse(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    cutoff = datetime.fromisoformat("2020-12-31T00:00:00+00:00")
    assert all(_parse(item["highlighted_at"]) > cutoff for item in results)


def test_get_book_detail(readwise_client: ReadwiseClient) -> None:
    book = readwise_client.get_book(1337)
    assert book["title"] == "Meditations"
    assert book["author"] == "Marcus Aurelius"


def test_books_paginate_with_cursor(readwise_client: ReadwiseClient) -> None:
    books = _collect(readwise_client.list_books({"page_size": 1}))
    assert len(books) >= 2
    assert {book["title"] for book in books} >= {"Meditations", "Design Systems and Team Flow"}
