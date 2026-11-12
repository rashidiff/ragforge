from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.pdf_extraction import extract_pages
from app.services.pdf_ingestion import LibraryStore, ValidatedPdf


def make_document(path: Path):
    import pymupdf

    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text(
            (72, 72), "First page. Contract identifier ABC-104. Table: Deadline 15 days."
        )
        page = document.new_page()
        page.insert_text(
            (72, 72), "Deuxieme page. Le contrat contient des clauses et des obligations."
        )
        document.new_page()  # Image-only/empty extraction must not be silently accepted as indexed.
        document.save(path)


def test_page_provenance_and_sparse_warning(tmp_path):
    path = tmp_path / "source.pdf"
    make_document(path)
    result = extract_pages(path)
    assert [page.page for page in result.pages] == [1, 2, 3]
    assert "ABC-104" in result.pages[0].text
    assert "contrat" in result.pages[1].text
    assert result.pages[2].text == ""
    assert result.needs_ocr
    assert "Page 3" in result.warnings[-1]


def test_multilingual_search_normalization_does_not_mutate_source(tmp_path):
    import unicodedata

    from app.services.pdf_extraction import ExtractedPage

    text = "فارسی français English cafe\u0301"
    page = ExtractedPage(12, text, unicodedata.normalize("NFC", text))
    assert page.text == text
    assert "café" in page.search_text
    assert page.page == 12


def test_enabled_local_ocr_replaces_sparse_page_text_and_reports_progress(tmp_path):
    from app.services.ocr import OcrAvailability

    path = tmp_path / "scan.pdf"
    make_document(path)
    progress = []

    class FakeOcr:
        def check_availability(self, languages):
            assert languages == "eng+fra+fas"
            return OcrAvailability(True, "local-tesseract", ("eng", "fra", "fas"))

        def recognize_page(self, page, languages, availability):
            assert availability.available
            return "Scanned Persian passage with enough searchable text."

    result = extract_pages(
        path,
        ocr_enabled=True,
        ocr_languages="eng+fra+fas",
        ocr_engine=FakeOcr(),
        on_ocr_page=lambda page, total: progress.append((page, total)),
    )
    assert result.needs_ocr is False
    assert "Scanned Persian passage" in result.pages[2].text
    assert any("OCR extracted text" in warning for warning in result.pages[2].warnings)
    assert progress == [(3, 3)]


def test_ocr_disabled_or_unavailable_keeps_sparse_scan_warned(tmp_path):
    from app.services.ocr import OcrAvailability

    path = tmp_path / "scan.pdf"
    make_document(path)

    class DisabledProbe:
        def check_availability(self, languages):
            raise AssertionError("OCR must not be probed when disabled")

    disabled = extract_pages(path, ocr_engine=DisabledProbe())
    assert disabled.needs_ocr
    assert disabled.pages[2].text == ""

    class MissingLanguage:
        def check_availability(self, languages):
            return OcrAvailability(
                False,
                "tesseract",
                ("eng", "fas"),
                ("fas",),
                "Local OCR language packs are missing: fas.",
            )

        def recognize_page(self, *args):
            raise AssertionError("OCR must be skipped when a configured language is missing")

    unavailable = extract_pages(path, ocr_enabled=True, ocr_engine=MissingLanguage())
    assert unavailable.needs_ocr
    assert any("language packs are missing: fas" in warning for warning in unavailable.warnings)
    assert unavailable.pages[2].text == ""


def test_tesseract_availability_checks_executable_and_requested_language_packs(monkeypatch):
    import subprocess

    from app.services.ocr import LocalTesseract

    monkeypatch.setattr("app.services.ocr.shutil.which", lambda name: "C:/tools/tesseract.exe")
    monkeypatch.setattr(
        "app.services.ocr.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout="List of available languages (2):\neng\nfra\n", stderr=""
        ),
    )
    result = LocalTesseract().check_availability("eng+fra+fas")
    assert result.available is False
    assert result.executable == "C:/tools/tesseract.exe"
    assert result.missing_languages == ("fas",)
    assert "fas" in result.warning


def test_tesseract_missing_executable_is_a_clear_nonfatal_warning(monkeypatch):
    from app.services.ocr import LocalTesseract

    monkeypatch.setattr("app.services.ocr.shutil.which", lambda name: None)
    result = LocalTesseract().check_availability("eng")
    assert result.available is False
    assert result.executable is None
    assert "not found on PATH" in result.warning


def test_preview_uses_managed_id_and_rejects_deleted_document(tmp_path):
    from hashlib import sha256
    from uuid import uuid4

    directory = tmp_path / "library/pdfs"
    directory.mkdir(parents=True)
    temporary = directory / "original.upload"
    make_document(temporary)
    content = temporary.read_bytes()
    identifier = str(uuid4())
    store = LibraryStore(tmp_path)
    store.accept(
        ValidatedPdf(
            temporary, identifier, "source.pdf", sha256(content).hexdigest(), len(content), 3
        )
    )
    config = Settings(_env_file=None, data_dir=tmp_path)
    with TestClient(create_app(config), base_url="http://127.0.0.1:8000") as client:
        response = client.get(f"/api/library/{identifier}/pdf")
        assert response.status_code == 200
        assert response.content == content
        assert response.headers["content-type"] == "application/pdf"
        store.update_status(identifier, "deleting")
        assert client.get(f"/api/library/{identifier}/pdf").status_code == 404
        assert client.get("/api/library/%2E%2E/pdf").status_code in {404, 422}
