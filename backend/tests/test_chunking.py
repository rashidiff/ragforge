import re

import pytest

from app.services.chunking import Chunker
from app.services.pdf_extraction import ExtractedPage


class WordTokenizer:
    """Deterministic fixture tokenizer, not the production model tokenizer."""
    def __call__(self, text, **options):
        return {"offset_mapping": [match.span() for match in re.finditer(r"\S+", text)]}


def test_chunks_never_cross_pages_and_keep_source_ranges():
    pages = (ExtractedPage(7, " ".join(f"p7-{n}" for n in range(12)), ""),
             ExtractedPage(8, "فارسی English français", ""))
    chunks = Chunker(WordTokenizer(), target_tokens=5, overlap_tokens=2).chunks(
        "document", "source.pdf", pages, "model@revision")
    assert all(chunk.page_start == chunk.page_end for chunk in chunks)
    assert [chunk.position for chunk in chunks] == list(range(len(chunks)))
    first = chunks[0].text.split()
    second = chunks[1].text.split()
    assert first[-2:] == second[:2]
    assert all(len(chunk.text.split()) <= 5 for chunk in chunks)
    assert chunks[-1].page_start == 8
    assert chunks[-1].text == pages[-1].text
    assert chunks[-1].embedding_model_version == "model@revision"


def test_boundaries_prefer_paragraphs_without_dropping_tail():
    text = "one two three four\n\nfive six seven eight nine ten"
    chunks = Chunker(WordTokenizer(), target_tokens=6, overlap_tokens=1).chunks(
        "id", "source.pdf", (ExtractedPage(1, text, text),), "v1")
    assert chunks[0].text == "one two three four"
    assert chunks[-1].text.endswith("ten")


def test_chunk_ids_stable_but_change_with_source_or_embedding_version():
    page = ExtractedPage(4, "enduring content", "enduring content")
    chunker = Chunker(WordTokenizer(), 5, 1)
    first = chunker.chunks("id", "source.pdf", (page,), "v1")
    assert first == chunker.chunks("id", "source.pdf", (page,), "v1")
    assert first[0].chunk_id != chunker.chunks("id", "source.pdf", (page,), "v2")[0].chunk_id
    assert first[0].record()["page_end"] == 4


@pytest.mark.parametrize("target,overlap", [(0, 0), (5, 5), (5, -1)])
def test_invalid_chunk_budgets_rejected(target, overlap):
    with pytest.raises(ValueError):
        Chunker(WordTokenizer(), target, overlap)
