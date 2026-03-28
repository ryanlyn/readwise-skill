from __future__ import annotations

import importlib.util
import json
import os
import runpy
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import typer


def _load_reader_module():
    module_name = "readwise_reader.scripts.reader_client"
    module_path = Path(__file__).resolve().parents[1] / "skills" / "readwise-reader" / "scripts" / "reader_client.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load reader_client module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


from readwise_common.models import (  # noqa: E402
    DocumentCreatePayload,
    DocumentListParams,
    DocumentUpdatePayload,
)

_reader_module = _load_reader_module()
ReaderClient = _reader_module.ReaderClient
reader_main = _reader_module.main
reader_script = Path(__file__).resolve().parents[1] / "skills" / "readwise-reader" / "scripts" / "reader_client.py"


@pytest.fixture
def reader_client() -> ReaderClient:
    token = os.environ["READWISE_TOKEN"]
    base_url = os.environ["READWISE_READER_API_BASE_URL"]
    return ReaderClient(token, base_url=base_url)


class _DummyContext:
    def __init__(self, client: ReaderClient, *, raw: bool = False, dry_run: bool = False) -> None:
        self.obj = {"client": client, "raw": raw, "dry_run": dry_run}


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload


def test_list_documents_by_location(reader_client: ReaderClient) -> None:
    docs = list(reader_client.list_documents(DocumentListParams(location="new")))
    assert docs, "Expected at least one document in 'new' location"
    assert all(doc.location == "new" for doc in docs)


def test_reader_client_list_documents_supports_content_and_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ReaderClient("stub-token", base_url="http://example.test")
    calls: list[tuple[str, str, dict[str, object]]] = []
    responses = [
        _FakeResponse(
            {
                "results": [
                    {
                        "id": "doc-1",
                        "title": "First",
                        "source_url": "https://example.com/first",
                    }
                ],
                "nextPageCursor": "cursor:1",
            }
        ),
        _FakeResponse(
            {
                "results": [
                    {
                        "id": "doc-2",
                        "title": "Second",
                        "source_url": "https://example.com/second",
                    }
                ],
                "nextPageCursor": None,
            }
        ),
    ]

    def fake_request(method: str, path: str, **kwargs: object) -> _FakeResponse:
        calls.append((method, path, dict(kwargs)))
        return responses.pop(0)

    monkeypatch.setattr(client, "_request", fake_request)

    docs = list(
        client.list_documents(
            DocumentListParams(
                document_id="doc-1",
                category="article",
                tag="first-tag",
                location="new",
                updated_after="2024-01-01T00:00:00Z",
            ),
            with_content=True,
        )
    )

    assert [doc.id for doc in docs] == ["doc-1", "doc-2"]
    first_call = calls[0]
    assert first_call[0] == "get"
    assert first_call[1] == "/list/"
    params = first_call[2]["params"]
    assert params["withRawSourceUrl"] == "true"
    assert params["withHtmlContent"] == "true"
    assert params["id"] == "doc-1"
    assert params["category"] == "article"
    assert params["tag"] == "first-tag"
    assert params["location"] == "new"
    assert params["updatedAfter"] == "2024-01-01T00:00:00Z"
    assert calls[1][2]["params"]["pageCursor"] == "cursor:1"


def test_reader_client_dry_run_methods_return_payloads() -> None:
    client = ReaderClient("stub-token", base_url="http://example.test", dry_run=True)

    created = client.create_document(DocumentCreatePayload(url="https://example.com/create", title="Create"))
    updated = client.update_document(
        "doc-1",
        DocumentUpdatePayload(title="Updated", labels=["priority"], location="later"),
    )
    deleted = client.delete_document("doc-1")

    assert created.request_payload == {
        "url": "https://example.com/create",
        "title": "Create",
        "tags": [],
        "labels": [],
    }
    assert updated.document_id == "doc-1"
    assert updated.request_payload == {"title": "Updated", "labels": ["priority"], "location": "later"}
    assert deleted.dry_run is True
    assert deleted.document_id == "doc-1"
    assert deleted.action == "delete"


def test_reader_document_crud_flow(reader_client: ReaderClient) -> None:
    unique_url = f"https://example.com/articles/{uuid4().hex}"
    created = reader_client.create_document(DocumentCreatePayload(url=unique_url, title="Stub Doc", tags=["focus"]))
    doc_id = created.id
    assert doc_id

    reader_client.update_document(doc_id, DocumentUpdatePayload(location="archive", tags=["integration-test"]))
    fetched = list(reader_client.list_documents(DocumentListParams(document_id=doc_id)))
    assert fetched, "Document should be retrievable after update"
    document = fetched[0]
    assert document.location == "archive"
    assert "integration-test" in (document.tags or {})

    reader_client.delete_document(doc_id)
    assert list(reader_client.list_documents(DocumentListParams(document_id=doc_id))) == []


def test_reader_list_paginates(reader_client: ReaderClient) -> None:
    created_ids = []
    for _ in range(3):
        unique_url = f"https://example.com/docs/{uuid4().hex}"
        created = reader_client.create_document(DocumentCreatePayload(url=unique_url, title="Paginated Doc"))
        created_ids.append(created.id)

    docs = list(reader_client.list_documents(DocumentListParams()))
    assert set(created_ids).issubset({doc.id for doc in docs})


def test_reader_list_filters_by_tag(reader_client: ReaderClient) -> None:
    docs = list(reader_client.list_documents(DocumentListParams(tag="first-tag")))
    assert docs
    assert all("first-tag" in (doc.tags or {}) for doc in docs)


def test_reader_update_labels_and_state(reader_client: ReaderClient) -> None:
    unique_url = f"https://example.com/update/{uuid4().hex}"
    created = reader_client.create_document(DocumentCreatePayload(url=unique_url, title="Label Doc"))
    doc_id = created.id

    reader_client.update_document(doc_id, DocumentUpdatePayload(location="later", labels=["priority"]))
    fetched = list(reader_client.list_documents(DocumentListParams(document_id=doc_id)))
    assert fetched
    doc = fetched[0]
    assert doc.location == "later"
    labels = getattr(doc, "labels", None) or []
    assert "priority" in labels


def test_reader_validate_token(reader_client: ReaderClient) -> None:
    reader_client.validate_token()


@pytest.mark.parametrize(
    "status_code, expected_message",
    [
        (401, "Token is invalid. Generate one at https://readwise.io/access_token"),
        (403, "Token is unauthorized. Generate one at https://readwise.io/access_token"),
        (500, "Token validation failed with status 500."),
    ],
)
def test_reader_auth_validate_http_error_branches(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status_code: int,
    expected_message: str,
) -> None:
    monkeypatch.setattr(
        _reader_module,
        "request_with_backoff",
        lambda *args, **kwargs: _FakeResponse({}, status_code=status_code),
    )

    assert reader_main(["auth", "validate"]) == 0
    captured = capsys.readouterr()
    assert expected_message in captured.out


def test_reader_auth_validate_api_request_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(*args, **kwargs):
        raise _reader_module.APIRequestError("boom")

    monkeypatch.setattr(_reader_module, "request_with_backoff", boom)

    assert reader_main(["auth", "validate"]) == 0
    captured = capsys.readouterr()
    assert "Token validation failed: boom" in captured.out


def test_reader_dry_run_create_outputs_once(capsys: pytest.CaptureFixture[str]) -> None:
    reader_main(["--dry-run", "docs", "create", "--url", "https://example.com/dry", "--title", "Dry"])
    captured = capsys.readouterr()
    lines = [line for line in captured.out.strip().splitlines() if line.strip()]
    url_count = sum(1 for line in lines if "example.com/dry" in line)
    assert url_count == 1, f"Expected payload printed once, got {url_count} occurrences"


def test_reader_pull_accepts_date_only(reader_client: ReaderClient, capsys: pytest.CaptureFixture[str]) -> None:
    unique_url = f"https://example.com/pull/{uuid4().hex}"
    reader_client.create_document(DocumentCreatePayload(url=unique_url, title="Pull Test"))
    reader_main(["docs", "pull", "--since", "2020-01-01", "--limit", "5"])
    captured = capsys.readouterr()
    assert "Pull Test" in captured.out


def test_reader_list_accepts_date_only(reader_client: ReaderClient, capsys: pytest.CaptureFixture[str]) -> None:
    unique_url = f"https://example.com/listdate/{uuid4().hex}"
    reader_client.create_document(DocumentCreatePayload(url=unique_url, title="ListDate Test"))
    reader_main(["docs", "list", "--location", "new", "--updated-after", "2020-01-01", "--limit", "5"])
    captured = capsys.readouterr()
    assert "ListDate Test" in captured.out


def test_reader_default_output_is_trimmed(reader_client: ReaderClient, capsys: pytest.CaptureFixture[str]) -> None:
    unique_url = f"https://example.com/trimmed/{uuid4().hex}"
    reader_client.create_document(DocumentCreatePayload(url=unique_url, title="Trimmed Doc"))
    reader_main(["docs", "list", "--location", "new", "--limit", "5"])
    captured = capsys.readouterr()
    assert "Trimmed Doc" in captured.out
    assert "created_at" not in captured.out  # created_at is not in DOCUMENT_FIELDS


def test_reader_raw_flag_outputs_full_json(reader_client: ReaderClient, capsys: pytest.CaptureFixture[str]) -> None:
    unique_url = f"https://example.com/rawtest/{uuid4().hex}"
    reader_client.create_document(DocumentCreatePayload(url=unique_url, title="Raw Doc"))
    reader_main(["--raw", "docs", "list", "--location", "new", "--limit", "5"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert any(doc["title"] == "Raw Doc" for doc in data)


def test_reader_list_with_content_includes_html_content(
    reader_client: ReaderClient, capsys: pytest.CaptureFixture[str]
) -> None:
    reader_main(["--raw", "docs", "list", "--location", "new", "--with-content", "--limit", "1"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert data and "html_content" in data[0]


def test_reader_docs_create_rejects_file_and_missing_url() -> None:
    ctx = _DummyContext(ReaderClient("stub-token", base_url="http://example.test"))

    with pytest.raises(typer.BadParameter, match="uploads are not supported"):
        _reader_module.docs_create(ctx, file="unsupported.txt")

    with pytest.raises(typer.BadParameter, match="Provide --url or --content"):
        _reader_module.docs_create(ctx)


def test_reader_docs_update_requires_fields() -> None:
    ctx = _DummyContext(ReaderClient("stub-token", base_url="http://example.test"))

    with pytest.raises(typer.BadParameter, match="No fields to update"):
        _reader_module.docs_update(ctx, document_id="doc-1")


def test_reader_main_returns_system_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_system_exit(*args, **kwargs) -> None:
        raise SystemExit(7)

    monkeypatch.setattr(_reader_module, "app", raise_system_exit)

    assert reader_main(["docs", "list"]) == 7


def test_reader_script_executes_as_main() -> None:
    original_argv = sys.argv[:]
    sys.argv = [str(reader_script), "--help"]
    try:
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_path(str(reader_script), run_name="__main__")
    finally:
        sys.argv = original_argv

    assert exc_info.value.code == 0


READER_COMMAND_MATRIX = [
    ["docs", "create", "--url", "https://example.com/matrix", "--title", "Matrix Doc"],
    ["docs", "list", "--location", "new", "--limit", "1"],
    ["docs", "update", "01gkqtdz9xabcd5gt96khreyb", "--title", "Updated Matrix Doc"],
    ["docs", "pull", "--limit", "1"],
    ["auth", "validate"],
]


@pytest.mark.parametrize("argv", READER_COMMAND_MATRIX)
def test_all_reader_commands_accept_trailing_raw(argv: list[str]) -> None:
    assert reader_main([*argv, "--raw"]) == 0


@pytest.mark.parametrize("argv", READER_COMMAND_MATRIX)
def test_all_reader_commands_accept_trailing_dry_run(argv: list[str]) -> None:
    assert reader_main([*argv, "--dry-run"]) == 0
