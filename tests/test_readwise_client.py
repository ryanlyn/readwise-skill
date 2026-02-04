from __future__ import annotations

import os
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
