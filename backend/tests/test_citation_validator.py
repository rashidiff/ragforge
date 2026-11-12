from uuid import uuid4

import pytest

from app.llm.base import ProviderError, SourceExcerpt
from app.services.citation_validator import CitationValidator


def test_validates_only_request_sources_and_builds_exact_page_urls():
    document_id = str(uuid4())
    source = SourceExcerpt("chunk-1", document_id, "Guide.pdf", 7, 7,
                           "The deadline is 15 days.", "generation-1")
    class Index:
        def get_source_excerpt(self, chunk_id):
            return {"chunk_id": chunk_id, "document_id": document_id, "filename": "Guide.pdf",
                "page_start": 7, "page_end": 7, "text": source.text,
                "index_version": "generation-1", "available": True}
    citations = CitationValidator(Index()).validate(
        "The document sets a deadline. [[source:chunk-1]]", (source,))
    assert citations == [{"chunk_id": "chunk-1", "document_id": document_id,
        "filename": "Guide.pdf", "page_start": 7, "page_end": 7,
        "url": f"/api/library/{document_id}/pdf#page=7"}]


def test_rejects_fabricated_and_now_unavailable_source_ids():
    document_id = str(uuid4())
    source = SourceExcerpt("valid", document_id, "Guide.pdf", 1, 1, "Evidence", "v1")
    class Index:
        def get_source_excerpt(self, chunk_id):
            raise KeyError(chunk_id)
    validator = CitationValidator(Index())
    with pytest.raises(ProviderError, match="not retrieved"):
        validator.validate("Claim [[source:fabricated]]", (source,))
    with pytest.raises(ProviderError, match="no longer available"):
        validator.validate("Claim [[source:valid]]", (source,))


def test_rejects_a_source_whose_live_provenance_changed():
    document_id = str(uuid4())
    source = SourceExcerpt("valid", document_id, "Guide.pdf", 1, 1, "Old evidence", "v1")
    class Index:
        def get_source_excerpt(self, chunk_id):
            return {"available": True, "document_id": document_id, "filename": "Guide.pdf",
                    "page_start": 1, "page_end": 1, "text": "Changed evidence"}
    with pytest.raises(ProviderError, match="changed or is no longer available"):
        CitationValidator(Index()).validate("Claim [[source:valid]]", (source,))
