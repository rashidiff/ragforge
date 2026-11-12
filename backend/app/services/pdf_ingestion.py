"""Bounded multipart PDF validation and durable local original/manifest storage."""

import asyncio
import hashlib
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from .state_store import JsonState, StateCorruptionError


class PdfIntakeError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422, document_id: str | None = None):
        super().__init__(message)
        self.code, self.status, self.document_id = code, status, document_id


def safe_filename(name: str | None) -> str:
    if not name or any(character in name for character in ("/", "\\", "\x00")):
        raise PdfIntakeError("invalid_filename", "Use a PDF filename without path components")
    if name in {".", ".."} or re.search(r"[\x00-\x1f\x7f]", name):
        raise PdfIntakeError("invalid_filename", "Filename contains unsafe characters")
    if len(name) > 240 or not name.lower().endswith(".pdf"):
        raise PdfIntakeError("unsupported_pdf", "Only .pdf files are accepted", 415)
    return name


def managed_pdf_path(root: Path, document_id: str) -> Path:
    identifier = str(UUID(document_id))
    directory = root.resolve()
    candidate = (directory / f"{identifier}.pdf").resolve()
    if not candidate.is_relative_to(directory):
        raise PdfIntakeError("invalid_path", "PDF path escapes managed storage")
    return candidate


def inspect_pdf(path: Path) -> int:
    import pymupdf

    try:
        with pymupdf.open(path) as document:
            if not document.is_pdf or document.needs_pass or document.is_encrypted:
                raise PdfIntakeError(
                    "encrypted_pdf", "Encrypted PDFs are not supported. Export an unencrypted copy."
                )
            if document.page_count < 1:
                raise PdfIntakeError("empty_pdf", "The PDF has no readable pages")
            # Parsing every page catches broken page trees without extracting or indexing.
            for page in document:
                _ = page.rect
            return document.page_count
    except PdfIntakeError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise PdfIntakeError("unreadable_pdf", "The PDF is malformed or unreadable") from exc


@dataclass(frozen=True)
class ValidatedPdf:
    temporary_path: Path
    document_id: str
    original_name: str
    sha256: str
    size_bytes: int
    page_count: int

    def discard(self) -> None:
        self.temporary_path.unlink(missing_ok=True)


async def validate_upload(upload: UploadFile, pdf_directory: Path, max_bytes: int) -> ValidatedPdf:
    """Read multipart chunks with an exact byte ceiling; never trust the MIME label."""
    if max_bytes <= 0:
        raise ValueError("Maximum upload size must be positive")
    name = safe_filename(upload.filename)
    if upload.content_type not in {None, "application/pdf", "application/octet-stream"}:
        raise PdfIntakeError("unsupported_pdf", "Upload must contain a PDF", 415)
    pdf_directory.mkdir(parents=True, exist_ok=True)
    document_id = str(uuid4())
    path = managed_pdf_path(pdf_directory, document_id).with_suffix(".upload")
    digest = hashlib.sha256()
    size = 0
    header = b""
    try:
        with path.open("xb") as stream:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise PdfIntakeError(
                        "upload_too_large", "PDF exceeds the configured file-size limit", 413
                    )
                if len(header) < 5:
                    header = (header + chunk)[:5]
                digest.update(chunk)
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        if header != b"%PDF-":
            raise PdfIntakeError("invalid_pdf_signature", "File content is not a PDF", 415)
        pages = await asyncio.to_thread(inspect_pdf, path)
        return ValidatedPdf(path, document_id, name, digest.hexdigest(), size, pages)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


class LibraryStore:
    def __init__(self, data_dir: Path):
        self.directory = data_dir / "library/pdfs"
        self.manifest = JsonState(
            data_dir / "library/manifest.json", {"schema_version": 1, "documents": {}}
        )

    @staticmethod
    def _documents(state: dict) -> dict:
        documents = state.get("documents")
        if not isinstance(documents, dict):
            raise StateCorruptionError("Library manifest is corrupt; restore a backup")
        return documents

    def list(self) -> list[dict]:
        from copy import deepcopy

        return deepcopy(list(self._documents(self.manifest.read()).values()))

    def accept(self, pdf: ValidatedPdf) -> dict:
        """Persist original before publishing metadata, under the manifest mutation lock."""
        with self.manifest.lock:
            for document in self.list():
                if document["sha256"] == pdf.sha256 and document["status"] != "deleted":
                    pdf.discard()
                    raise PdfIntakeError(
                        "duplicate_pdf",
                        "This PDF is already in the Library",
                        409,
                        document_id=document["document_id"],
                    )
            destination = managed_pdf_path(self.directory, pdf.document_id)
            metadata = dict(
                document_id=pdf.document_id,
                original_name=pdf.original_name,
                title=pdf.original_name,
                sha256=pdf.sha256,
                size_bytes=pdf.size_bytes,
                page_count=pdf.page_count,
                imported_at=datetime.now(UTC).isoformat(),
                status="extracting",
                warnings=[],
                index_version=None,
                error=None,
            )
            try:
                # The validated original is already fsynced; publish on the same filesystem.
                os.replace(pdf.temporary_path, destination)
                if os.name == "posix":
                    descriptor = os.open(
                        destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                    )
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                self.manifest.update(
                    lambda state: self._documents(state).__setitem__(pdf.document_id, metadata)
                )
            except BaseException:
                # An unreferenced original is retained on disk for recovery, never exposed as ready.
                pdf.discard()
                raise
            return metadata

    def update_status(
        self,
        document_id: str,
        status: str,
        *,
        warnings=None,
        error=None,
        index_version: str | None = None,
    ) -> dict:
        if status not in {
            "extracting",
            "ocr",
            "chunking",
            "embedding",
            "indexing",
            "failed",
            "deleting",
            "deleted",
        }:
            raise ValueError("Only a validated index publisher may mark documents ready")

        def mutate(state):
            document = self._documents(state).get(document_id)
            if document is None:
                raise KeyError("Document not found")
            document.update(status=status, error=error, index_version=index_version)
            if warnings is not None:
                document["warnings"] = list(warnings)
            return dict(document)

        return self.manifest.update(mutate)
