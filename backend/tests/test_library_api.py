import re
from typing import ClassVar

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeTokenizer:
    def __call__(self, text, **options):
        return {"offset_mapping": [match.span() for match in re.finditer(r"\S+", text)]}


class FakeEmbeddings:
    tokenizer = FakeTokenizer()
    identity: ClassVar[dict] = {
        "model": "fixture",
        "revision": None,
        "resolved_revision": "fixture",
        "normalized": True,
    }
    version = "fixture"
    max_document_tokens = 500

    def documents(self, texts):
        return np.array([[1.0, 0.0] for text in texts], dtype="float32")

    def query(self, text):
        return np.array([1.0, 0.0], dtype="float32")

    def count_tokens(self, text):
        return len(text.split())


def fixture_pdf(blank=False):
    import pymupdf

    with pymupdf.open() as document:
        page = document.new_page()
        if not blank:
            page.insert_text(
                (72, 72), "Contract ABC-104 has a delivery deadline of fifteen business days."
            )
        return document.tobytes()


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, embedding_model="fixture"))
    with TestClient(app, base_url="http://127.0.0.1:8000") as connection:
        app.state.runtime.index.embeddings = FakeEmbeddings()
        yield connection


def finish(client):
    client.app.state.runtime.index._executor.submit(lambda: None).result(timeout=15)


def test_upload_jobs_preview_deduplication_and_deletion(client):
    content = fixture_pdf()
    response = client.post(
        "/api/library/upload", files={"file": ("contract.pdf", content, "application/pdf")}
    )
    assert response.status_code == 202
    identifier = response.json()["document"]["document_id"]
    finish(client)
    status = client.get("/api/index/status").json()
    assert status["ready"]
    assert status["jobs"][0]["stage"] == "ready"
    assert client.get(f"/api/library/{identifier}/pdf").content == content
    duplicate = client.post(
        "/api/library/upload", files={"file": ("copy.pdf", content, "application/pdf")}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_pdf"
    assert client.post(f"/api/library/{identifier}/reindex").status_code == 202
    finish(client)
    assert client.delete(f"/api/library/{identifier}").status_code == 202
    assert client.get(f"/api/library/{identifier}/pdf").status_code == 404
    finish(client)
    assert client.get("/api/library").json()["documents"] == []


def test_scan_warning_and_failure_are_not_indexed_success(client):
    response = client.post(
        "/api/library/upload",
        files={"file": ("scan.pdf", fixture_pdf(blank=True), "application/pdf")},
    )
    assert response.status_code == 202
    finish(client)
    document = client.get("/api/library").json()["documents"][0]
    assert document["status"] == "failed"
    assert document["warnings"] and "OCR" in document["error"]
    assert client.get("/api/index/status").json()["jobs"][0]["stage"] == "failed"


def test_unknown_jobs_and_invalid_upload_have_safe_errors(client):
    from uuid import uuid4

    assert client.get(f"/api/index/status?job_id={uuid4()}").status_code == 404
    invalid = client.post(
        "/api/library/upload", files={"file": ("not.pdf", b"not pdf", "application/pdf")}
    )
    assert invalid.status_code == 415
    assert "Traceback" not in invalid.text


def test_source_excerpt_endpoint_is_scoped_to_document_and_page(client, monkeypatch):
    from uuid import uuid4

    document_id, chunk_id = str(uuid4()), str(uuid4())
    monkeypatch.setattr(
        client.app.state.runtime.index,
        "get_source_excerpt",
        lambda identifier: {
            "chunk_id": identifier,
            "document_id": document_id,
            "filename": "guide.pdf",
            "page_start": 7,
            "page_end": 7,
            "text": "Source text",
            "index_version": "v1",
            "available": True,
        },
    )
    response = client.get(f"/api/library/{document_id}/sources/{chunk_id}")
    assert response.status_code == 200
    assert response.json()["url"] == f"/api/library/{document_id}/pdf#page=7"
    assert response.json()["text"] == "Source text"
    assert client.get(f"/api/library/{uuid4()}/sources/{chunk_id}").status_code == 404


def test_real_indexed_chunk_opens_source_without_exposing_internal_metadata(client):
    response = client.post('/api/library/upload', files={
        'file': ('contract.pdf', fixture_pdf(), 'application/pdf')})
    assert response.status_code == 202
    document_id = response.json()['document']['document_id']
    finish(client)
    sources = client.app.state.runtime.index.search_library('ABC-104 delivery deadline')
    assert sources
    chunk_id = sources[0]['chunk_id']
    internal = client.app.state.runtime.index.get_source_excerpt(chunk_id)
    assert 'sha256' in internal
    response = client.get(f'/api/library/{document_id}/sources/{chunk_id}')
    assert response.status_code == 200
    source = response.json()
    assert set(source) == {
        'chunk_id', 'document_id', 'filename', 'page_start', 'page_end',
        'url', 'text', 'index_version', 'available',
    }
    assert source['available'] is True
    assert 'ABC-104' in source['text']
    assert source['url'] == f'/api/library/{document_id}/pdf#page=1'
    assert client.get(f'/api/library/{document_id}/pdf').status_code == 200
