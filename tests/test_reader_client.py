from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest


def _load_reader_module():
    module_name = "readwise_reader.scripts.reader_client"
    module_path = Path(__file__).resolve().parents[1] / "skills" / "readwise-reader" / "scripts" / "reader_client.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load reader_client module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_reader_module = _load_reader_module()
ReaderClient = _reader_module.ReaderClient
reader_main = _reader_module.main

from readwise_common.models import (
    DocumentCreatePayload,
    DocumentListParams,
    DocumentUpdatePayload,
)


@pytest.fixture
def reader_client() -> ReaderClient:
    token = os.environ["READWISE_TOKEN"]
    base_url = os.environ["READWISE_READER_API_BASE_URL"]
    return ReaderClient(token, base_url=base_url)


def test_list_documents_by_location(reader_client: ReaderClient) -> None:
    docs = list(reader_client.list_documents(DocumentListParams(location="new")))
    assert docs, "Expected at least one document in 'new' location"
    assert all(doc.location == "new" for doc in docs)


def test_reader_document_crud_flow(reader_client: ReaderClient) -> None:
    unique_url = f"https://example.com/articles/{uuid4().hex}"
    created = reader_client.create_document(
        DocumentCreatePayload(url=unique_url, title="Stub Doc", tags=["focus"])
    )
    doc_id = created.id
    assert doc_id

    reader_client.update_document(
        doc_id, DocumentUpdatePayload(location="archive", tags=["integration-test"])
    )
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
        created = reader_client.create_document(
            DocumentCreatePayload(url=unique_url, title="Paginated Doc")
        )
        created_ids.append(created.id)

    docs = list(reader_client.list_documents(DocumentListParams()))
    assert set(created_ids).issubset({doc.id for doc in docs})


def test_reader_list_filters_by_tag(reader_client: ReaderClient) -> None:
    docs = list(reader_client.list_documents(DocumentListParams(tag="first-tag")))
    assert docs
    assert all("first-tag" in (doc.tags or {}) for doc in docs)


def test_reader_update_labels_and_state(reader_client: ReaderClient) -> None:
    unique_url = f"https://example.com/update/{uuid4().hex}"
    created = reader_client.create_document(
        DocumentCreatePayload(url=unique_url, title="Label Doc")
    )
    doc_id = created.id

    reader_client.update_document(
        doc_id, DocumentUpdatePayload(location="later", labels=["priority"])
    )
    fetched = list(reader_client.list_documents(DocumentListParams(document_id=doc_id)))
    assert fetched
    doc = fetched[0]
    assert doc.location == "later"
    labels = getattr(doc, "labels", None) or []
    assert "priority" in labels


def test_reader_validate_token(reader_client: ReaderClient) -> None:
    reader_client.validate_token()


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
    reader_main(["docs", "list", "--updated-after", "2020-01-01", "--limit", "5"])
    captured = capsys.readouterr()
    assert "ListDate Test" in captured.out


def test_reader_default_output_is_trimmed(reader_client: ReaderClient, capsys: pytest.CaptureFixture[str]) -> None:
    unique_url = f"https://example.com/trimmed/{uuid4().hex}"
    reader_client.create_document(DocumentCreatePayload(url=unique_url, title="Trimmed Doc"))
    reader_main(["docs", "list", "--limit", "5"])
    captured = capsys.readouterr()
    assert "Trimmed Doc" in captured.out
    assert "source_url" not in captured.out


def test_reader_raw_flag_outputs_full_json(reader_client: ReaderClient, capsys: pytest.CaptureFixture[str]) -> None:
    unique_url = f"https://example.com/rawtest/{uuid4().hex}"
    reader_client.create_document(DocumentCreatePayload(url=unique_url, title="Raw Doc"))
    reader_main(["--raw", "docs", "list", "--limit", "5"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert any(doc["title"] == "Raw Doc" for doc in data)
