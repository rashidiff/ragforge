"""Validate provider source markers against request evidence and current Library state."""

import re
from uuid import UUID

from app.domain.schemas import Citation
from app.llm.base import ProviderError, SourceExcerpt
from app.services.index_manager import IndexUnavailableError

_MARKER = re.compile(r"\[\[source:([^\]\s]+)\]\]")


class CitationValidator:
    def __init__(self, index_manager):
        self.index = index_manager

    def validate(self, answer: str, request_sources: tuple[SourceExcerpt, ...]) -> list[dict]:
        requested = {source.chunk_id: source for source in request_sources}
        result = []
        seen = set()
        for match in _MARKER.finditer(answer):
            chunk_id = match.group(1)
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            original = requested.get(chunk_id)
            if original is None:
                raise ProviderError(
                    "invalid_citation", "The response cited a source that was not retrieved"
                )
            try:
                current = self.index.get_source_excerpt(chunk_id)
            except (KeyError, IndexUnavailableError) as exc:
                raise ProviderError(
                    "source_unavailable", "A cited PDF is no longer available"
                ) from exc
            if (
                current.get("available") is not True
                or current.get("document_id") != original.document_id
                or current.get("filename") != original.filename
                or current.get("page_start") != original.page_start
                or current.get("page_end") != original.page_end
                or current.get("text") != original.text
            ):
                raise ProviderError(
                    "source_unavailable", "A cited PDF changed or is no longer available"
                )
            citation = Citation(
                chunk_id=chunk_id,
                document_id=UUID(original.document_id),
                filename=original.filename,
                page_start=original.page_start,
                page_end=original.page_end,
                url=f"/api/library/{original.document_id}/pdf#page={original.page_start}",
            )
            result.append(citation.model_dump(mode="json"))
        return result
