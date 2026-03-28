from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path

import pytest
import requests
import typer

from readwise_common.formatting import render_highlights, select_fields
from readwise_common.models import (
    BookListParams,
    Highlight,
    HighlightCreatePayload,
    HighlightListParams,
    HighlightUpdatePayload,
)
from readwise_common.utils import format_inline_tags, hoist_global_options
from skills.readwise.scripts import readwise_client as readwise_module
from skills.readwise.scripts.readwise_client import ReadwiseClient
from skills.readwise.scripts.readwise_client import main as readwise_main


@pytest.fixture
def readwise_client() -> ReadwiseClient:
    token = os.environ["READWISE_TOKEN"]
    base_url = os.environ["READWISE_API_BASE_URL"]
    return ReadwiseClient(token, base_url=base_url)


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = {}

    def json(self) -> object:
        return self._payload


def _raise_http_error(status_code: int | None) -> None:
    response = requests.Response()
    if status_code is not None:
        response.status_code = status_code
    raise requests.HTTPError("Unexpected auth response", response=response)


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

    updated = readwise_client.update_highlight(highlight_id, HighlightUpdatePayload(color="pink", note="updated"))
    assert updated.color == "pink"
    assert updated.note == "updated"

    readwise_client.delete_highlight(highlight_id)
    remaining = list(readwise_client.list_highlights(HighlightListParams(book_id=created.book_id)))
    remaining_ids = {item.id for item in remaining}
    assert highlight_id not in remaining_ids


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


def test_paginate_uses_page_cursor(readwise_client: ReadwiseClient, monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            FakeResponse({"results": [{"id": 1, "text": "first"}], "nextPageCursor": "cursor-2"}),
            FakeResponse({"results": [{"id": 2, "text": "second"}]}),
        ]
    )
    request_calls: list[dict[str, object]] = []

    def fake_request(method: str, path: str, **kwargs: object) -> FakeResponse:
        request_calls.append({"method": method, "path": path, "kwargs": kwargs})
        return next(responses)

    monkeypatch.setattr(readwise_client, "_request", fake_request)

    items = list(readwise_client.paginate("/highlights/", {"tag": "focus"}))

    assert [item["id"] for item in items] == [1, 2]
    assert request_calls[0]["kwargs"] == {"params": {"tag": "focus"}}
    assert request_calls[1]["kwargs"] == {"params": {"tag": "focus", "pageCursor": "cursor-2"}}


def test_paginate_follows_next_url(readwise_client: ReadwiseClient, monkeypatch: pytest.MonkeyPatch) -> None:
    first = FakeResponse({"results": [{"id": 1, "text": "first"}], "next": "http://example.test/next"})
    second = FakeResponse({"results": [{"id": 2, "text": "second"}]})
    request_calls: list[tuple[str, str, dict[str, object]]] = []
    backoff_calls: list[tuple[str, str, dict[str, object]]] = []

    def fake_request(method: str, path: str, **kwargs: object) -> FakeResponse:
        request_calls.append((method, path, kwargs))
        return first

    def fake_backoff(session: requests.Session, method: str, url: str, **kwargs: object) -> FakeResponse:
        backoff_calls.append((method, url, kwargs))
        return second

    monkeypatch.setattr(readwise_client, "_request", fake_request)
    monkeypatch.setattr(readwise_module, "request_with_backoff", fake_backoff)

    items = list(readwise_client.paginate("/highlights/", {}))

    assert [item["id"] for item in items] == [1, 2]
    assert request_calls == [("get", "/highlights/", {"params": {}})]
    assert backoff_calls == [("get", "http://example.test/next", {})]


@pytest.mark.parametrize(
    ("response", "expected_id", "expected_text"),
    [
        (FakeResponse([{"id": 11, "text": "resolved", "modified_highlights": [99]}]), 99, "resolved"),
        (FakeResponse([{"id": 12, "text": "plain"}]), 12, "plain"),
        (FakeResponse({"highlights": [{"id": 13, "text": "nested"}]}), 13, "nested"),
        (FakeResponse({"id": 14, "text": "fallback"}), 14, "fallback"),
    ],
)
def test_create_highlight_handles_api_response_shapes(
    readwise_client: ReadwiseClient,
    monkeypatch: pytest.MonkeyPatch,
    response: FakeResponse,
    expected_id: int,
    expected_text: str,
) -> None:
    payload = HighlightCreatePayload(text="created", location="1", location_type="order")
    monkeypatch.setattr(readwise_client, "_request", lambda method, path, **kwargs: response)

    if isinstance(response.json(), list) and response.json()[0].get("modified_highlights"):
        monkeypatch.setattr(
            readwise_client,
            "get_highlight",
            lambda highlight_id: Highlight(id=highlight_id, text=expected_text),
        )

    created = readwise_client.create_highlight(payload)

    assert created.id == expected_id
    assert created.text == expected_text


def test_daily_review_returns_highlights(readwise_client: ReadwiseClient) -> None:
    response = readwise_client.daily_review()
    assert response.review_id is not None
    assert response.highlights
    assert all(h.text is not None for h in response.highlights)


def test_get_book_detail(readwise_client: ReadwiseClient) -> None:
    book = readwise_client.get_book(1337)
    assert book.title == "Meditations"
    assert book.author == "Marcus Aurelius"


def test_books_list_and_pagination(readwise_client: ReadwiseClient) -> None:
    books = list(readwise_client.list_books(BookListParams()))
    assert len(books) >= 2
    titles = {book.title for book in books}
    assert "Meditations" in titles
    assert "Design Systems and Team Flow" in titles


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


def test_dry_run_create_outputs_payload_once(capsys: pytest.CaptureFixture[str]) -> None:
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
    readwise_main(
        [
            "--raw",
            "highlight",
            "create",
            "--text",
            "Generated highlight",
            "--title",
            "Gen Test",
            "--generated",
        ]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list) and len(data) == 1
    tag_names = {t["name"] for t in data[0]["tags"]}
    assert "generated" in tag_names


def test_highlight_create_tags_and_note(readwise_client: ReadwiseClient) -> None:
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
    readwise_main(
        [
            "--raw",
            "highlight",
            "create",
            "--text",
            "CLI tagged",
            "--title",
            "CLI Tag Book",
            "--tags",
            "alpha,beta",
        ]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list) and len(data) == 1
    tag_names = {t["name"] for t in data[0]["tags"]}
    assert "alpha" in tag_names
    assert "beta" in tag_names


def test_dry_run_create_with_tags(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main(
        [
            "--dry-run",
            "highlight",
            "create",
            "--text",
            "Dry run tagged",
            "--title",
            "DryTagBook",
            "--tags",
            "alpha,beta",
        ]
    )
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


class TestHoistGlobalOptions:
    def test_flags_already_before_subcommand(self) -> None:
        assert hoist_global_options(["--raw", "books"]) == ["--raw", "books"]

    def test_flags_moved_from_end(self) -> None:
        assert hoist_global_options(["books", "--raw"]) == ["--raw", "books"]

    def test_multiple_flags_moved(self) -> None:
        result = hoist_global_options(["highlight", "create", "--text", "x", "--raw", "--dry-run"])
        assert result == ["--raw", "--dry-run", "highlight", "create", "--text", "x"]

    def test_no_flags(self) -> None:
        assert hoist_global_options(["books", "--title", "foo"]) == ["books", "--title", "foo"]

    def test_empty(self) -> None:
        assert hoist_global_options([]) == []


class TestFormatInlineTags:
    def test_basic(self) -> None:
        assert format_inline_tags(["focus", "review"]) == ".focus .review"

    def test_with_note(self) -> None:
        result = format_inline_tags(["focus"], "My note")
        assert result == ".focus\nMy note"

    def test_preserves_dot_prefix(self) -> None:
        assert format_inline_tags([".generated", "focus"]) == ".generated .focus"

    def test_empty(self) -> None:
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


class TestRenderHighlights:
    def test_blockquoted_text(self) -> None:
        highlights = [{"text": "Some quote", "note": "", "tags": []}]
        result = render_highlights(highlights)
        assert result == "> Some quote"

    def test_note_shown_when_present(self) -> None:
        highlights = [{"text": "Quote", "note": "My thought"}]
        result = render_highlights(highlights)
        assert "> Quote" in result
        assert "Note: My thought" in result

    def test_tags_shown_when_present(self) -> None:
        highlights = [{"text": "Quote", "tags": [{"name": "focus"}, {"name": "deep"}]}]
        result = render_highlights(highlights)
        assert "Tags: focus, deep" in result

    def test_empty_note_and_tags_omitted(self) -> None:
        highlights = [{"text": "Clean", "note": "", "tags": []}]
        result = render_highlights(highlights)
        assert "Note" not in result
        assert "Tags" not in result

    def test_multiple_highlights_separated(self) -> None:
        highlights = [{"text": "First"}, {"text": "Second"}]
        result = render_highlights(highlights)
        assert "> First\n\n> Second" == result


def test_highlights_list_uses_blockquote_format(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main(["highlights", "list", "--book-id", "1337", "--limit", "2"])
    captured = capsys.readouterr()
    assert captured.out.startswith(">")
    assert "id=" not in captured.out


def test_readwise_validate_token(readwise_client: ReadwiseClient) -> None:
    readwise_client.validate_token()


def test_validate_token_raises_for_non_204(readwise_client: ReadwiseClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        readwise_module,
        "request_with_backoff",
        lambda session, method, url, **kwargs: FakeResponse({}, status_code=401),
    )

    with pytest.raises(requests.HTTPError) as excinfo:
        readwise_client.validate_token()

    assert excinfo.value.response is not None
    assert excinfo.value.response.status_code == 401


def test_list_highlights_builds_query_with_all_filters(
    readwise_client: ReadwiseClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_paginate(path: str, params: dict[str, object] | None = None):
        captured["path"] = path
        captured["params"] = params
        yield {"id": 1, "text": "filtered"}

    monkeypatch.setattr(readwise_client, "paginate", fake_paginate)

    params = HighlightListParams(
        book_id=1337,
        tag="focus",
        updated_after="2024-01-15T10:30:00Z",
        updated_before="2024-02-01T10:30:00Z",
        category="books",
    )
    results = list(readwise_client.list_highlights(params))

    assert [item.id for item in results] == [1]
    assert captured["path"] == "/highlights/"
    assert captured["params"] == {
        "book_id": 1337,
        "tag": "focus",
        "updatedAfter": "2024-01-15T10:30:00Z",
        "updatedBefore": "2024-02-01T10:30:00Z",
        "category": "books",
    }


def test_dry_run_methods_skip_network(readwise_client: ReadwiseClient) -> None:
    dry_client = ReadwiseClient(
        os.environ["READWISE_TOKEN"],
        base_url=os.environ["READWISE_API_BASE_URL"],
        dry_run=True,
    )

    updated = dry_client.update_highlight(13, HighlightUpdatePayload(color="pink"))
    deleted = dry_client.delete_highlight(13)
    tagged = dry_client.tag_highlight(13, "retrospective")

    assert updated.dry_run is True
    assert updated.highlight_id == 13
    assert updated.request_payload == {"color": "pink"}
    assert deleted.dry_run is True
    assert deleted.action == "delete"
    assert deleted.highlight_id == 13
    assert tagged == {"dry_run": True, "highlight_id": 13, "tag": "retrospective"}


def test_build_highlight_payload_preserves_inline_tag_mode() -> None:
    payload = readwise_module._build_highlight_payload(
        text="payload text",
        text_file=None,
        title="Title",
        author="Author",
        source_url="https://example.com",
        image_url="https://example.com/image.png",
        book_id=1337,
        category="books",
        note="Personal note",
        tags_raw="alpha,beta",
        location="12",
        location_type="page",
        generated=True,
        require_text=True,
        inline_tags=False,
    )

    assert payload["text"] == "payload text"
    assert payload["title"] == "Title"
    assert payload["author"] == "Author"
    assert payload["source_url"] == "https://example.com"
    assert payload["image_url"] == "https://example.com/image.png"
    assert payload["book_id"] == 1337
    assert payload["category"] == "books"
    assert payload["note"] == "Personal note"
    assert payload["_tags"] == ["alpha", "beta", ".generated"]
    assert payload["location"] == "12"
    assert payload["location_type"] == "page"


def test_build_highlight_payload_raises_when_text_resolution_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_resolve_highlight_text(text: str | None, text_file: str | None) -> str:
        raise ValueError("no text")

    monkeypatch.setattr(readwise_module, "resolve_highlight_text", fake_resolve_highlight_text)

    with pytest.raises(ValueError, match="no text"):
        readwise_module._build_highlight_payload(
            text=None,
            text_file=None,
            title=None,
            author=None,
            source_url=None,
            image_url=None,
            book_id=None,
            category=None,
            note=None,
            tags_raw=None,
            location=None,
            location_type=None,
            generated=False,
            require_text=True,
        )


def test_normalize_bulk_payload_requires_text() -> None:
    with pytest.raises(ValueError, match="Bulk highlight payloads require 'text'"):
        readwise_module._normalize_bulk_payload({}, False)


def test_normalize_bulk_payload_applies_tags_and_location() -> None:
    payload = readwise_module._normalize_bulk_payload(
        {
            "text": "Bulk text",
            "note": "My note",
            "tags": "alpha, beta",
            "generated": True,
            "location": "5",
            "location_type": "order",
        },
        default_generated=False,
    )

    assert payload["text"] == "Bulk text"
    assert payload["note"] == ".alpha .beta .generated\nMy note"
    assert payload["location"] == "5"
    assert payload["location_type"] == "order"
    assert "tags" not in payload


def test_normalize_datetime_arg_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="--updated-after must be an ISO date or datetime"):
        readwise_module._normalize_datetime_arg("--updated-after", "not-a-date")


def test_highlight_create_rejects_missing_text_when_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(readwise_module.sys, "stdin", type("FakeStdin", (), {"isatty": lambda self: True})())

    with pytest.raises(typer.BadParameter, match="Highlight text is required"):
        readwise_main(["highlight", "create", "--title", "No Text"])


def test_highlight_update_rejects_empty_payload_when_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(readwise_module.sys, "stdin", type("FakeStdin", (), {"isatty": lambda self: True})())

    with pytest.raises(typer.BadParameter, match="No fields to update"):
        readwise_main(["highlight", "update", "13"])


def test_highlight_update_tags_only_fetches_updated_item(capsys: pytest.CaptureFixture[str]) -> None:
    class FakeStdin:
        def isatty(self) -> bool:
            return True

    original_stdin = readwise_module.sys.stdin
    readwise_module.sys.stdin = FakeStdin()
    try:
        readwise_main(["--raw", "highlight", "update", "13", "--tags", "alpha,beta"])
        captured = capsys.readouterr()
    finally:
        readwise_module.sys.stdin = original_stdin

    data = json.loads(captured.out)
    tag_names = {tag["name"] for tag in data["tags"]}
    assert "alpha" in tag_names
    assert "beta" in tag_names


def test_highlight_delete_can_be_aborted(
    readwise_client: ReadwiseClient, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    readwise_main(["highlight", "delete", "13"])
    captured = capsys.readouterr()

    assert "Aborted" in captured.err
    assert readwise_client.get_highlight(13).id == 13


def test_highlight_create_reads_bulk_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bulk_file = tmp_path / "highlights.ndjson"
    bulk_file.write_text(
        json.dumps(
            {
                "text": "Bulk created highlight",
                "tags": "alpha,beta",
                "location": "9",
                "location_type": "order",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    readwise_main(["--raw", "highlight", "create", "--bulk-file", str(bulk_file)])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["text"] == "Bulk created highlight"
    assert data[0]["tags"][0]["name"] == "alpha"


@pytest.mark.parametrize(
    ("status_code", "expected_message"),
    [
        (401, "Token is invalid. Generate one at https://readwise.io/access_token"),
        (403, "Token is unauthorized. Generate one at https://readwise.io/access_token"),
        (500, "Token validation failed with status 500."),
    ],
)
def test_auth_validate_handles_http_errors(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_validate(self: ReadwiseClient) -> None:
        _raise_http_error(status_code)

    monkeypatch.setattr(readwise_module.ReadwiseClient, "validate_token", fake_validate)

    readwise_main(["auth", "validate", "--raw"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert data["valid"] is False
    assert data["status"] == status_code
    assert data["message"] == expected_message


def test_auth_validate_handles_api_request_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_validate(self: ReadwiseClient) -> None:
        raise readwise_module.APIRequestError("connection reset")

    monkeypatch.setattr(readwise_module.ReadwiseClient, "validate_token", fake_validate)

    readwise_main(["auth", "validate", "--raw"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert data["valid"] is False
    assert data["message"] == "Token validation failed: connection reset"


def test_main_returns_one_for_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_app(args: list[str], standalone_mode: bool = False) -> None:
        raise SystemExit("boom")

    monkeypatch.setattr(readwise_module, "app", fake_app)

    assert readwise_module.main([]) == 1


def test_module_entrypoint_runs_main_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(typer.main.Typer, "__call__", lambda self, *args, **kwargs: 0)
    module_path = Path(readwise_module.__file__).resolve()
    original_argv = sys.argv[:]
    sys.argv = [str(module_path)]
    try:
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_path(str(module_path), run_name="__main__")
    finally:
        sys.argv = original_argv

    assert excinfo.value.code == 0


READWISE_COMMAND_MATRIX = [
    ["books", "--limit", "1"],
    ["book", "1337"],
    ["highlights", "list", "--limit", "1"],
    ["highlights", "review"],
    ["highlight", "show", "13"],
    ["highlight", "create", "--text", "matrix create", "--title", "Matrix Book"],
    ["highlight", "update", "13", "--text", "matrix update"],
    ["highlight", "delete", "13", "--yes"],
    ["auth", "validate"],
]


@pytest.mark.parametrize("argv", READWISE_COMMAND_MATRIX)
def test_all_readwise_commands_accept_trailing_raw(argv: list[str]) -> None:
    assert readwise_main([*argv, "--raw"]) == 0


@pytest.mark.parametrize("argv", READWISE_COMMAND_MATRIX)
def test_all_readwise_commands_accept_trailing_dry_run(argv: list[str]) -> None:
    assert readwise_main([*argv, "--dry-run"]) == 0


def test_falsy_fields_omitted_in_markdown(capsys: pytest.CaptureFixture[str]) -> None:
    readwise_main(["book", "1337"])
    captured = capsys.readouterr()
    assert "Meditations" in captured.out
    assert "document_note" not in captured.out
