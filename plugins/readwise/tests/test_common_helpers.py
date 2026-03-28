from __future__ import annotations

import json
from collections import namedtuple
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import requests
from pydantic import BaseModel
from requests.structures import CaseInsensitiveDict

import readwise_common.auth as auth_module
import readwise_common.http as http_module
import readwise_common.utils as utils_module
from readwise_common.auth import MissingTokenError, Token, get_reader_token, get_readwise_token, get_token
from readwise_common.formatting import (
    _coerce_mapping,
    _format_tags,
    _render_markdown,
    _render_plain,
    _to_plain,
    print_result,
    render_highlights,
    render_output,
    select_fields,
)
from readwise_common.http import APIRequestError, RateLimitInfo, request_with_backoff
from readwise_common.models import (
    Book,
    DailyReviewHighlight,
    DailyReviewResponse,
    DeleteResult,
    Document,
    DocumentCreatePayload,
    DocumentSaveResponse,
    DocumentUpdatePayload,
    DryRunResult,
    Highlight,
    HighlightCreatePayload,
    HighlightUpdatePayload,
    TokenValidationResult,
)
from readwise_common.utils import (
    build_location_payload,
    build_tags,
    format_inline_tags,
    hoist_global_options,
    load_bulk_payloads,
    parse_iso_datetime,
    parse_tags,
    resolve_highlight_text,
)


class DummyModel(BaseModel):
    value: int
    label: str | None = None


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        json_data: Any = None,
        headers: dict[str, str] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.headers = CaseInsensitiveDict(headers or {})
        self._raise_exc = raise_exc

    def json(self) -> Any:
        return self._json_data

    def raise_for_status(self) -> None:
        if self._raise_exc is not None:
            raise self._raise_exc


class FakeSession:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str, int, dict[str, Any]]] = []

    def request(self, method: str, url: str, timeout: int, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, timeout, kwargs))
        if not self._responses:
            raise AssertionError("No more fake responses configured")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_get_token_uses_override_and_masks_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(auth_module.READWISE_TOKEN_ENV, raising=False)

    token = get_token("override-token")

    assert token == Token(value="override-token", name=auth_module.READWISE_TOKEN_ENV)
    assert repr(token) == "Token(name='READWISE_TOKEN', value='***')"
    assert str(token) == "Token(READWISE_TOKEN=***)"
    assert get_readwise_token("override-token") == token
    assert get_reader_token("override-token") == token


def test_get_token_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auth_module.READWISE_TOKEN_ENV, "env-token")

    token = get_token()

    assert token.value == "env-token"
    assert token.name == auth_module.READWISE_TOKEN_ENV


def test_get_token_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(auth_module.READWISE_TOKEN_ENV, raising=False)

    with pytest.raises(MissingTokenError, match=auth_module.READWISE_TOKEN_ENV):
        get_token()


def test_rate_limit_info_parses_and_ignores_invalid_values() -> None:
    headers = CaseInsensitiveDict(
        {
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Remaining": "12",
            "X-RateLimit-Reset": "bad-value",
        }
    )

    info = RateLimitInfo.from_headers(headers)

    assert info == RateLimitInfo(limit=100, remaining=12, reset=None)


def test_format_rate_limit_notice_uses_available_headers() -> None:
    headers = CaseInsensitiveDict(
        {
            "X-RateLimit-Limit": "50",
            "X-RateLimit-Remaining": "4",
            "X-RateLimit-Reset": "123",
            "Retry-After": "2",
        }
    )

    assert (
        http_module._format_rate_limit_notice(headers)
        == "Rate limit headers: limit=50, remaining=4, reset=123, retry_after=2"
    )
    assert http_module._format_rate_limit_notice(CaseInsensitiveDict()) == ""


def test_request_with_backoff_returns_success_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse(status_code=200, json_data={"ok": True})
    session = FakeSession([response])

    result = request_with_backoff(session, "get", "https://example.com/api", timeout=9, params={"page": 2})

    assert result is response
    assert session.calls == [("GET", "https://example.com/api", 9, {"params": {"page": 2}})]


def test_request_with_backoff_retries_throttled_responses(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    first = FakeResponse(
        status_code=429,
        headers={
            "Retry-After": "2",
            "X-RateLimit-Limit": "5",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "99",
        },
    )
    second = FakeResponse(status_code=200, json_data={"ok": True})
    session = FakeSession([first, second])
    sleeps: list[float] = []

    monkeypatch.setattr(http_module.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(http_module.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = request_with_backoff(session, "post", "https://example.com/api")

    assert result is second
    assert sleeps == [2.0]
    assert "Throttled (HTTP 429)" in capsys.readouterr().err


def test_request_with_backoff_uses_backoff_when_retry_after_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    first = FakeResponse(status_code=503, headers={"Retry-After": "soon"})
    second = FakeResponse(status_code=200, json_data={"ok": True})
    session = FakeSession([first, second])
    sleeps: list[float] = []

    monkeypatch.setattr(http_module.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(http_module.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = request_with_backoff(session, "get", "https://example.com/api")

    assert result is second
    assert sleeps == [pytest.approx(http_module.BACKOFF_BASE**1)]


def test_request_with_backoff_raises_after_request_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession([requests.ConnectionError("boom")])
    sleeps: list[float] = []

    monkeypatch.setattr(http_module.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(http_module.time, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(APIRequestError, match="boom"):
        request_with_backoff(session, "get", "https://example.com/api", max_attempts=1)

    assert sleeps == []


def test_request_with_backoff_sleeps_between_request_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession([requests.ConnectionError("boom"), requests.ConnectionError("boom-again")])
    sleeps: list[float] = []

    monkeypatch.setattr(http_module.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(http_module.time, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(APIRequestError, match="boom-again"):
        request_with_backoff(session, "get", "https://example.com/api", max_attempts=2)

    assert sleeps == [pytest.approx(http_module.BACKOFF_BASE**1)]


def test_request_with_backoff_raises_after_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    error = requests.HTTPError("bad response")
    response = FakeResponse(status_code=400, raise_exc=error)
    session = FakeSession([response])

    with pytest.raises(APIRequestError, match="bad response"):
        request_with_backoff(session, "get", "https://example.com/api", max_attempts=1)


def test_request_with_backoff_raises_when_retries_are_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(status_code=429)
    session = FakeSession([response])
    sleeps: list[float] = []

    monkeypatch.setattr(http_module.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(http_module.time, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(APIRequestError, match="Request failed after retries"):
        request_with_backoff(session, "get", "https://example.com/api", max_attempts=1)

    assert sleeps == [pytest.approx(http_module.BACKOFF_BASE**1)]


def test_to_plain_and_render_output_cover_model_and_plain_paths() -> None:
    model = DummyModel(value=7, label="seven")

    assert _to_plain(model) == {"value": 7, "label": "seven"}
    assert _to_plain([model]) == [{"value": 7, "label": "seven"}]
    assert render_output(model, "json") == json.dumps({"value": 7, "label": "seven"}, ensure_ascii=False, indent=2)
    assert render_output([b"one", b"two"], "plain") == "one\ntwo"
    assert render_output({"value": 1}, "markdown") == "- **value**: 1"


def test_coerce_mapping_covers_all_fallbacks() -> None:
    pair_type = namedtuple("Pair", ["value", "label"])
    pair = pair_type(1, "tuple")

    assert _coerce_mapping(DummyModel(value=1, label="model")) == {"value": 1, "label": "model"}
    assert _coerce_mapping({"value": 2}) == {"value": 2}
    assert _coerce_mapping(pair) == {"value": 1, "label": "tuple"}
    assert _coerce_mapping(SimpleNamespace(value=3, label="namespace")) == {"value": 3, "label": "namespace"}
    assert _coerce_mapping(9) == {"value": 9}


def test_format_tags_handles_dict_list_other_and_empty() -> None:
    assert _format_tags({}) == ""
    assert _format_tags({"alpha": 1, "beta": 2}) == "alpha, beta"
    assert _format_tags([{"name": "gamma"}, "delta"]) == "gamma, delta"
    assert _format_tags("epsilon") == "epsilon"


def test_render_highlights_handles_mixed_entries() -> None:
    rendered = render_highlights(
        [
            {"text": "First quote", "note": "Important", "tags": {"alpha": 1, "beta": 2}},
            {"text": "Second quote", "tags": [{"name": "gamma"}, "delta"]},
            "raw entry",
        ]
    )

    assert "> First quote" in rendered
    assert "Note: Important" in rendered
    assert "Tags: alpha, beta" in rendered
    assert "Tags: gamma, delta" in rendered
    assert "raw entry" in rendered
    assert render_highlights("already rendered") == "already rendered"
    assert render_highlights([]) == ""


def test_render_markdown_and_plain_cover_iterable_paths() -> None:
    assert _render_markdown({"keep": 1, "drop": "", "skip": None}) == "- **keep**: 1"
    assert _render_markdown([1, {"value": 2}, SimpleNamespace(value=3)]) == "- value=1\n- value=2\n- value=3"
    assert _render_markdown(5) == "5"
    assert _render_plain("text") == "text"
    assert _render_plain({"value": 1}) == json.dumps({"value": 1}, ensure_ascii=False)


def test_select_fields_filters_dicts_and_leaves_other_items() -> None:
    data = [{"id": 1, "title": "keep", "extra": "drop"}, "raw"]

    assert select_fields(data, ["id", "title"]) == [{"id": 1, "title": "keep"}, "raw"]
    assert select_fields({"id": 1, "title": "keep", "extra": "drop"}, ["id", "title"]) == {"id": 1, "title": "keep"}
    assert select_fields("unchanged", ["id"]) == "unchanged"


def test_print_result_honors_fields_renderer_raw_and_dry_run_modes(capsys: pytest.CaptureFixture[str]) -> None:
    model = DummyModel(value=7, label="seven")
    seen: list[Any] = []

    print_result(
        [model],
        fields=["value"],
        raw=False,
        dry_run=False,
        renderer=lambda value: seen.append(value) or "rendered",
    )
    assert seen == [[{"value": 7}]]
    assert capsys.readouterr().out.strip() == "rendered"

    print_result(model, fields=None, raw=True, dry_run=False)
    assert json.loads(capsys.readouterr().out) == {"value": 7, "label": "seven"}

    print_result({"value": 1, "extra": ""}, fields=["value"], raw=False, dry_run=True, renderer=lambda value: "ignored")
    assert capsys.readouterr().out.strip() == "- **value**: 1"


def test_parse_tags_build_tags_and_format_inline_tags() -> None:
    assert parse_tags(None) == []
    assert parse_tags(" alpha, beta ,alpha,, gamma ") == ["alpha", "beta", "gamma"]
    assert hoist_global_options(["highlight", "create", "--raw", "--dry-run"]) == [
        "--raw",
        "--dry-run",
        "highlight",
        "create",
    ]
    assert build_tags(["focus"], False) == ["focus"]
    assert build_tags(["focus"], True) == ["focus", ".generated"]
    assert build_tags(["focus", ".generated"], True) == ["focus", ".generated"]
    assert format_inline_tags(["focus"], None) == ".focus"
    assert format_inline_tags(["focus", ".generated"], "Note") == ".focus .generated\nNote"
    assert format_inline_tags([], "Note") == "Note"
    assert format_inline_tags([], None) == ""


def test_resolve_highlight_text_prefers_direct_text_and_file(tmp_path: Path) -> None:
    text_file = tmp_path / "highlight.txt"
    text_file.write_text("  file text  ", encoding="utf-8")

    assert resolve_highlight_text("direct text", str(text_file)) == "direct text"
    assert resolve_highlight_text(None, str(text_file)) == "file text"


def test_resolve_highlight_text_reads_stdin_and_raises_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeStdin:
        def __init__(self, data: str, tty: bool) -> None:
            self._data = data
            self._tty = tty

        def isatty(self) -> bool:
            return self._tty

        def read(self) -> str:
            return self._data

    monkeypatch.setattr(utils_module.sys, "stdin", FakeStdin("  stdin text  ", False))
    assert resolve_highlight_text(None, None) == "stdin text"

    monkeypatch.setattr(utils_module.sys, "stdin", FakeStdin("", False))
    with pytest.raises(ValueError, match="Provide --text, --text-file, or pipe content via stdin"):
        resolve_highlight_text(None, None)


def test_build_location_payload_covers_generated_and_validation_paths() -> None:
    assert build_location_payload(None, None, True) == {"location_type": "none"}
    assert build_location_payload("12", None, False) == {"location": "12", "location_type": "order"}
    assert build_location_payload("12", "page", False) == {"location": "12", "location_type": "page"}

    with pytest.raises(ValueError, match="--location-type requires --location"):
        build_location_payload(None, "page", False)


def test_load_bulk_payloads_and_parse_iso_datetime(tmp_path: Path) -> None:
    bulk_file = tmp_path / "payloads.ndjson"
    bulk_file.write_text('{"text": "one"}\n\n  {"text": "two"}  \n', encoding="utf-8")

    assert list(load_bulk_payloads(str(bulk_file))) == [{"text": "one"}, {"text": "two"}]
    assert parse_iso_datetime("2024-01-15") == "2024-01-15T00:00:00Z"
    assert parse_iso_datetime("2024-01-15T10:30:00") == "2024-01-15T10:30:00Z"
    assert parse_iso_datetime("2024-01-15T10:30:00Z") == "2024-01-15T10:30:00Z"
    assert parse_iso_datetime("2024-01-15T10:30:00+11:00") == "2024-01-14T23:30:00Z"

    with pytest.raises(ValueError, match="Date value cannot be empty"):
        parse_iso_datetime("   ")
    with pytest.raises(ValueError, match="Invalid date/time: not-a-date"):
        parse_iso_datetime("not-a-date")


def test_parse_iso_datetime_uses_date_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDateTime:
        min = datetime.min

        @staticmethod
        def fromisoformat(value: str) -> datetime:
            raise ValueError(value)

        @staticmethod
        def combine(parsed_date, parsed_time, tzinfo=None) -> datetime:
            return datetime.combine(parsed_date, parsed_time, tzinfo=tzinfo)

    monkeypatch.setattr(utils_module, "datetime", FakeDateTime)

    assert parse_iso_datetime("2024-01-15") == "2024-01-15T00:00:00Z"


def test_model_basics_and_extra_fields_are_allowed() -> None:
    highlight = Highlight.model_validate(
        {
            "id": 1,
            "text": "Quote",
            "book_id": 99,
            "extra_field": "kept",
        }
    )
    review = DailyReviewResponse.model_validate(
        {
            "review_id": 10,
            "review_completed": True,
            "highlights": [{"text": "Review quote", "note": "yes"}],
        }
    )
    document = Document.model_validate(
        {
            "id": "doc-1",
            "title": "Doc",
            "tags": {"topic": "study"},
            "extra": 1,
        }
    )

    assert highlight.model_extra == {"extra_field": "kept"}
    assert review.highlights[0] == DailyReviewHighlight(text="Review quote", note="yes")
    assert document.model_extra == {"extra": 1}

    assert HighlightCreatePayload(text="x").tags == []
    assert DocumentCreatePayload().tags == []
    assert DocumentCreatePayload().labels == []
    assert DocumentSaveResponse(id="abc", url="https://example.com").id == "abc"
    assert DocumentUpdatePayload(location="later").model_dump(exclude_none=True) == {"location": "later"}
    assert HighlightUpdatePayload(color="pink").model_dump(exclude_none=True) == {"color": "pink"}
    assert DryRunResult().dry_run is True
    assert DeleteResult(deleted=True).deleted is True
    assert Book(id=1, title="Book").title == "Book"
    assert TokenValidationResult(valid=True, message="ok").message == "ok"
