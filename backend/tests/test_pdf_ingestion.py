import asyncio
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services.pdf_ingestion import LibraryStore, PdfIntakeError, validate_upload


def pdf_bytes():
    import pymupdf

    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Local source")
        return document.tobytes()


def validate(tmp_path, content, name="source.pdf", limit=50 * 1024 * 1024):
    upload = UploadFile(
        filename=name, file=BytesIO(content), headers=Headers({"content-type": "application/pdf"})
    )
    return asyncio.run(validate_upload(upload, tmp_path / "library/pdfs", limit))


@pytest.mark.parametrize(
    "name", ["../escape.pdf", "folder\\escape.pdf", "source.txt", "bad\x00.pdf"]
)
def test_unsafe_names_rejected(tmp_path, name):
    with pytest.raises(PdfIntakeError):
        validate(tmp_path, b"%PDF-fake", name=name)


def test_byte_limit_and_content_signature(tmp_path):
    with pytest.raises(PdfIntakeError) as failure:
        validate(tmp_path, b"%PDF-" + b"x" * 50, limit=20)
    assert failure.value.status == 413
    with pytest.raises(PdfIntakeError) as failure:
        validate(tmp_path, b"not pdf")
    assert failure.value.status == 415
    assert not list((tmp_path / "library/pdfs").glob("*.upload"))


def test_normal_pdf_persistence_and_hash_deduplication(tmp_path):
    content = pdf_bytes()
    store = LibraryStore(tmp_path)
    first = store.accept(validate(tmp_path, content, name="فرانسوی.pdf"))
    assert first["page_count"] == 1
    assert first["status"] != "ready"
    assert (tmp_path / "library/pdfs" / f"{first['document_id']}.pdf").read_bytes() == content
    with pytest.raises(PdfIntakeError) as duplicate:
        store.accept(validate(tmp_path, content, name="another.pdf"))
    assert duplicate.value.document_id == first["document_id"]
    assert len(LibraryStore(tmp_path).list()) == 1
    assert len(list((tmp_path / "library/pdfs").glob("*.pdf"))) == 1


def test_malformed_and_encrypted_pdfs(tmp_path):
    import pymupdf

    with pytest.raises(PdfIntakeError):
        validate(tmp_path, b"%PDF-malformed")
    with pymupdf.open() as document:
        document.new_page()
        encrypted = document.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="reader"
        )
    with pytest.raises(PdfIntakeError, match="Encrypted"):
        validate(tmp_path, encrypted)


def test_manifest_failure_does_not_publish_ready_document(tmp_path):
    store = LibraryStore(tmp_path)
    accepted = validate(tmp_path, pdf_bytes())
    with (
        patch.object(store.manifest, "update", side_effect=OSError("full disk")),
        pytest.raises(OSError),
    ):
        store.accept(accepted)
    assert store.list() == []
