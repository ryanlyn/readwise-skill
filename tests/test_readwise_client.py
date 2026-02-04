from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime

import pytest

from readwise_common.formatting import select_fields
from readwise_common.models import (
    BookListParams,
    DailyReviewParams,
    HighlightCreatePayload,
    HighlightListParams,
    HighlightUpdatePayload,
)
from readwise_common.schemas import DISPLAY_FIELDS
from skills.readwise.scripts.readwise_client import ReadwiseClient, main as readwise_main


@pytest.fixture
def readwise_client() -> ReadwiseClient:
    token = os.environ["READWISE_TOKEN"]
    base_url = os.environ["READWISE_API_BASE_URL"]
    return ReadwiseClient(token, base_url=base_url)


def test_list_highlights_filters_by_book(readwise_client: ReadwiseClient) -> None:
    params = HighlightListParams(book_id=1337)
    results = list(readwise_client.list_highlights(params))
    assert results, "Expected highlights for book 1337"
    for highlight in results:
        assert highlight.book_id == 1337


def test_highlight_crud_flow(readwise_client: ReadwiseClient) -> None:
    payload = HighlightCreatePayload(
        text="Integration test highlight",
        note="created via tests",
        location="1",
        location_type="order",
    )
    created = readwise_client.create_highlight(payload)
    highlight_id = created.id
    assert created.text == payload.text
    assert created.color == "yellow"

    updated = readwise_client.update_highlight(
        highlight_id, HighlightUpdatePayload(color="pink", note="updated")
    )
    assert updated.color == "pink"
    assert updated.note == "updated"

    readwise_client.delete_highlight(highlight_id)
    remaining = list(readwise_client.list_highlights(HighlightListParams(book_id=created.book_id)))
    remaining_ids = {item.id for item in remaining}
    assert highlight_id not in remaining_ids


def test_books_list(readwise_client: ReadwiseClient) -> None:
    books = list(readwise_client.list_books(BookListParams()))
    titles = {book.title for book in books}
    assert "Meditations" in titles
    assert "Design Systems and Team Flow" in titles


def test_get_highlight(readwise_client: ReadwiseClient) -> None:
    highlight = readwise_client.get_highlight(13)
    assert highlight.id == 13
    assert highlight.book_id == 1337


def test_highlights_paginate_with_cursor(readwise_client: ReadwiseClient) -> None:
    for idx in range(3):
        readwise_client.create_highlight(
            HighlightCreatePayload(
                text=f"Paginated highlight {idx}",
                note="pagination-test",
                location=str(idx + 1),
                location_type="order",
            )
        )
    highlights = list(readwise_client.list_highlights(HighlightListParams()))
    assert len(highlights) >= 5
    assert len({item.id for item in highlights}) == len(highlights)


def test_daily_review_filters_by_date(readwise_client: ReadwiseClient) -> None:
    params = DailyReviewParams(updated_after="2020-12-31T00:00:00+00:00", limit=10)
    response = readwise_client.daily_review(params)
    results = response.results
    assert results

    def _parse(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    cutoff = datetime.fromisoformat("2020-12-31T00:00:00+00:00")
    assert all(_parse(item.highlighted_at) > cutoff for item in results)


def test_get_book_detail(readwise_client: ReadwiseClient) -> None:
    book = readwise_client.get_book(1337)
    assert book.title == "Meditations"
    assert book.author == "Marcus Aurelius"


def test_books_paginate_with_cursor(readwise_client: ReadwiseClient) -> None:
    books = list(readwise_client.list_books(BookListParams()))
    assert len(books) >= 2
    assert {book.title for book in books} >= {"Meditations", "Design Systems and Team Flow"}


def test_books_author_filter(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main(["books", "--author", "Marcus Aurelius"])
    captured = capsys.readouterr()
    assert "Meditations" in captured.out
    assert "Design Systems" not in captured.out


def test_books_title_filter(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main(["books", "--title", "meditations"])
    captured = capsys.readouterr()
    assert "Meditations" in captured.out
    assert "Design Systems" not in captured.out


def test_book_show(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main(["book", "1337"])
    captured = capsys.readouterr()
    assert "Meditations" in captured.out
    assert "Marcus Aurelius" in captured.out


def test_book_id_resolves_to_title_author(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main(["--dry-run", "highlight", "create", "--text", "resolved", "--book-id", "1337"])
    captured = capsys.readouterr()
    assert "Meditations" in captured.out
    assert "Marcus Aurelius" in captured.out
    assert "book_id" not in captured.out


def test_dry_run_outputs_once(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main(["--dry-run", "highlight", "create", "--text", "dry run test", "--title", "DryBook"])
    captured = capsys.readouterr()
    lines = [line for line in captured.out.strip().splitlines() if line.strip()]
    text_count = sum(1 for line in lines if "dry run test" in line)
    assert text_count == 1, f"Expected payload printed once, got {text_count} occurrences"
    assert "dry_run" in captured.out
    assert "request_payload" in captured.out


def test_dry_run_delete_no_side_effects(readwise_client: ReadwiseClient, capsys: pytest.CaptureFixture[str]) -> None:
    created = readwise_client.create_highlight(
        HighlightCreatePayload(text="to be kept", location="1", location_type="order")
    )
    highlight_id = created.id
    readwise_main(["--dry-run", "highlight", "delete", str(highlight_id), "--yes"])
    assert readwise_client.get_highlight(highlight_id).id == highlight_id


def test_highlight_create_with_tags(readwise_client: ReadwiseClient) -> None:
    from readwise_common.utils import format_inline_tags
    note_with_tags = format_inline_tags(["focus", "review"])
    payload = HighlightCreatePayload(
        text="Tagged highlight",
        note=note_with_tags,
        location="1",
        location_type="order",
    )
    created = readwise_client.create_highlight(payload)
    tag_names = {t["name"] for t in created.tags}
    assert "focus" in tag_names
    assert "review" in tag_names


def test_highlight_create_generated_tags(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main([
        "--raw", "highlight", "create",
        "--text", "Generated highlight",
        "--title", "Gen Test",
        "--generated",
    ])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list) and len(data) == 1
    tag_names = {t["name"] for t in data[0]["tags"]}
    assert "generated" in tag_names


def test_highlight_create_tags_and_note(readwise_client: ReadwiseClient) -> None:
    from readwise_common.utils import format_inline_tags
    note_with_tags = format_inline_tags(["focus", ".generated"], "My personal note")
    payload = HighlightCreatePayload(
        text="Highlight with note and tags",
        note=note_with_tags,
        location="1",
        location_type="order",
    )
    created = readwise_client.create_highlight(payload)
    assert created.note == "My personal note"
    tag_names = {t["name"] for t in created.tags}
    assert "focus" in tag_names
    assert "generated" in tag_names


def test_highlight_create_with_tags_via_cli(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main([
        "--raw", "highlight", "create",
        "--text", "CLI tagged",
        "--title", "CLI Tag Book",
        "--tags", "alpha,beta",
    ])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list) and len(data) == 1
    tag_names = {t["name"] for t in data[0]["tags"]}
    assert "alpha" in tag_names
    assert "beta" in tag_names


def test_dry_run_create_with_tags(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main([
        "--dry-run", "highlight", "create",
        "--text", "Dry run tagged",
        "--title", "DryTagBook",
        "--tags", "alpha,beta",
    ])
    captured = capsys.readouterr()
    assert "dry_run" in captured.out
    assert ".alpha" in captured.out
    assert ".beta" in captured.out


def test_highlight_update_with_tags(readwise_client: ReadwiseClient) -> None:
    created = readwise_client.create_highlight(
        HighlightCreatePayload(text="To be tagged later", location="1", location_type="order")
    )
    highlight_id = created.id
    readwise_client.tag_highlight(highlight_id, "retrospective")
    detail = readwise_client.get_highlight(highlight_id)
    tag_names = {t["name"] for t in detail.tags}
    assert "retrospective" in tag_names


class TestFormatInlineTags:
    def test_basic(self) -> None:
        from readwise_common.utils import format_inline_tags
        assert format_inline_tags(["focus", "review"]) == ".focus .review"

    def test_with_note(self) -> None:
        from readwise_common.utils import format_inline_tags
        result = format_inline_tags(["focus"], "My note")
        assert result == ".focus\nMy note"

    def test_preserves_dot_prefix(self) -> None:
        from readwise_common.utils import format_inline_tags
        assert format_inline_tags([".generated", "focus"]) == ".generated .focus"

    def test_empty(self) -> None:
        from readwise_common.utils import format_inline_tags
        assert format_inline_tags([]) == ""
        assert format_inline_tags([], "note") == "note"


class TestSelectFields:
    def test_dict(self) -> None:
        data = {"id": 1, "text": "hello", "extra": "gone"}
        assert select_fields(data, ["id", "text"]) == {"id": 1, "text": "hello"}

    def test_list_of_dicts(self) -> None:
        data = [{"id": 1, "a": "x"}, {"id": 2, "a": "y"}]
        assert select_fields(data, ["id"]) == [{"id": 1}, {"id": 2}]

    def test_passthrough_non_dict(self) -> None:
        assert select_fields("plain string", ["id"]) == "plain string"
        assert select_fields(42, ["id"]) == 42

    def test_missing_fields_ignored(self) -> None:
        data = {"id": 1}
        assert select_fields(data, ["id", "text", "note"]) == {"id": 1}


def test_default_output_is_trimmed_markdown(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main(["books", "--title", "meditations"])
    captured = capsys.readouterr()
    assert "Meditations" in captured.out
    assert "num_highlights" in captured.out
    assert "cover_image_url" not in captured.out


def test_raw_flag_outputs_full_json(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main(["--raw", "books", "--title", "meditations"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert len(data) >= 1
    book = data[0]
    assert book["title"] == "Meditations"
    assert "cover_image_url" in book


def test_dry_run_skips_field_filtering(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main(["--dry-run", "highlight", "create", "--text", "test", "--title", "DryBook"])
    captured = capsys.readouterr()
    assert "dry_run" in captured.out
    assert "request_payload" in captured.out
