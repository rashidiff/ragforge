"""Tokenizer-bounded, page-contained chunks with deterministic source identities."""

import re
from bisect import bisect_right
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from .pdf_extraction import ExtractedPage


class OffsetTokenizer(Protocol):
    def __call__(
        self, text: str, *, add_special_tokens: bool, return_offsets_mapping: bool
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    filename: str
    page_start: int
    page_end: int
    text: str
    sha256: str
    position: int
    embedding_model_version: str

    def record(self) -> dict:
        return asdict(self)


class Chunker:
    def __init__(
        self, tokenizer: OffsetTokenizer, target_tokens: int = 500, overlap_tokens: int = 80
    ):
        if target_tokens < 1 or overlap_tokens < 0 or overlap_tokens >= target_tokens:
            raise ValueError("Chunk target must exceed a nonnegative overlap")
        self.tokenizer = tokenizer
        self.target = target_tokens
        self.overlap = overlap_tokens

    def chunks(
        self,
        document_id: str,
        filename: str,
        pages: tuple[ExtractedPage, ...],
        embedding_model_version: str,
    ) -> list[Chunk]:
        result = []
        for page in pages:
            if not page.text.strip():
                continue
            encoded = self.tokenizer(
                page.text, add_special_tokens=False, return_offsets_mapping=True
            )
            offsets = [
                (int(start), int(end)) for start, end in encoded["offset_mapping"] if end > start
            ]
            if not offsets:
                continue
            if any(start < 0 or end > len(page.text) or end < start for start, end in offsets):
                raise ValueError("Tokenizer offsets must refer to the original page text")
            if any(offsets[index][0] < offsets[index - 1][0] for index in range(1, len(offsets))):
                raise ValueError("Tokenizer offsets must be in source order")
            ends = [end for _, end in offsets]
            boundaries = [
                match.end() for match in re.finditer(r"\n\s*\n|\n(?=\s*#{1,6}\s)", page.text)
            ]
            start_token = 0
            while start_token < len(offsets):
                end_token = min(start_token + self.target, len(offsets))
                if end_token < len(offsets):
                    earliest = offsets[start_token + max(0, int(self.target * 0.6) - 1)][1]
                    latest = offsets[end_token - 1][1]
                    candidates = [
                        boundary for boundary in boundaries if earliest <= boundary <= latest
                    ]
                    if candidates:
                        candidate_end = bisect_right(ends, candidates[-1])
                        if candidate_end > start_token + self.overlap:
                            end_token = candidate_end
                char_start, char_end = offsets[start_token][0], offsets[end_token - 1][1]
                text = page.text[char_start:char_end]
                digest = sha256(text.encode("utf-8")).hexdigest()
                identity = f"{document_id}:{page.page}:{char_start}:{char_end}:{digest}:{embedding_model_version}"
                result.append(
                    Chunk(
                        str(uuid5(NAMESPACE_URL, identity)),
                        document_id,
                        filename,
                        page.page,
                        page.page,
                        text,
                        digest,
                        len(result),
                        embedding_model_version,
                    )
                )
                if end_token == len(offsets):
                    break
                start_token = max(start_token + 1, end_token - self.overlap)
        return result
