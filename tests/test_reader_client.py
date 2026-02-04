from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest


def _load_reader_client_class():
    module_name = "readwise_reader.scripts.reader_client"
    module_path = Path(__file__).resolve().parents[1] / "readwise-reader" / "scripts" / "reader_client.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load reader_client module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ReaderClient


ReaderClient = _load_reader_client_class()


@pytest.fixture
def reader_client() -> ReaderClient:
    token = os.environ["READWISE_READER_TOKEN"]
    base_url = os.environ["READWISE_READER_API_BASE_URL"]
    return ReaderClient(token, base_url=base_url)


def test_list_documents_by_location(reader_client: ReaderClient) -> None:
    docs = list(reader_client.list_documents({"location": "new"}))
    assert docs, "Expected at least one document in 'new' location"
    assert all(doc["location"] == "new" for doc in docs)


def test_reader_document_crud_flow(reader_client: ReaderClient) -> None:
    unique_url = f"https://example.com/articles/{uuid4().hex}"
    created = reader_client.create_document({"url": unique_url, "title": "Stub Doc", "tags": ["focus"]})
    doc_id = created["id"]
    assert doc_id

    reader_client.update_document(doc_id, {"location": "archive", "tags": ["integration-test"]})
    fetched = list(reader_client.list_documents({"id": doc_id}))
    assert fetched, "Document should be retrievable after update"
    document = fetched[0]
    assert document["location"] == "archive"
    assert "integration-test" in (document.get("tags") or {})

    reader_client.delete_document(doc_id)
    assert list(reader_client.list_documents({"id": doc_id})) == []
