"""Page-aware local extraction. Sparse scans are warned, never called indexed."""
from dataclasses import dataclass
from pathlib import Path
import unicodedata

from .pdf_ingestion import PdfIntakeError
from .ocr import LocalTesseract, OcrProcessingError


@dataclass(frozen=True)
class ExtractedPage:
    page: int
    text: str
    search_text: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Extraction:
    pages: tuple[ExtractedPage, ...]
    warnings: tuple[str, ...]
    needs_ocr: bool


def extract_pages(path: Path, sparse_character_threshold: int = 30, *, ocr_enabled: bool = False,
                  ocr_languages: str = "eng+fra+fas", ocr_engine=None,
                  on_ocr_page=None) -> Extraction:
    import pymupdf

    if sparse_character_threshold < 1:
        raise ValueError("Sparse extraction threshold must be positive")
    pages = []
    warnings = []
    recognizer = ocr_engine or (LocalTesseract() if ocr_enabled else None)
    availability = None
    try:
        with pymupdf.open(path) as document:
            if document.needs_pass or document.is_encrypted:
                raise PdfIntakeError("encrypted_pdf", "Encrypted PDFs cannot be extracted")
            if not document.is_pdf or document.page_count == 0:
                raise PdfIntakeError("unreadable_pdf", "PDF has no readable pages")
            for number, page in enumerate(document, start=1):
                blocks = page.get_text("blocks", sort=True)
                # Block coordinates give a reasonable page reading order and preserve table text
                # without inventing unsupported table structure. Ignore image-only blocks.
                text = "\n\n".join(block[4] for block in blocks if len(block) >= 7 and block[6] == 0)
                page_warnings = []
                sparse = len("".join(text.split())) < sparse_character_threshold
                if sparse and ocr_enabled:
                    if availability is None:
                        availability = recognizer.check_availability(ocr_languages)
                        if availability.warning:
                            warnings.append(availability.warning)
                    if on_ocr_page is not None:
                        on_ocr_page(number, document.page_count)
                    if availability.available:
                        try:
                            recognized = recognizer.recognize_page(page, ocr_languages, availability)
                        except OcrProcessingError:
                            recognized = ""
                            page_warnings.append(f"Local OCR could not process page {number}.")
                        if len("".join(recognized.split())) >= sparse_character_threshold:
                            text = recognized
                            sparse = False
                            page_warnings.append(f"Local OCR extracted text from page {number}.")
                        elif not page_warnings:
                            page_warnings.append(f"Local OCR did not extract enough text from page {number}.")
                if sparse:
                    warning = f"Page {number} has little or no extractable text. Local OCR may be needed."
                    page_warnings.append(warning)
                    warnings.append(warning)
                warnings.extend(page_warnings)
                pages.append(ExtractedPage(number, text, unicodedata.normalize("NFC", text),
                                           tuple(page_warnings)))
    except PdfIntakeError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise PdfIntakeError("extraction_failed", "PDF text could not be read. Try a readable unencrypted copy.") from exc
    return Extraction(tuple(pages), tuple(warnings), any(
        len("".join(page.text.split())) < sparse_character_threshold for page in pages))
