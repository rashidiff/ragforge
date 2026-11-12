from hashlib import sha256

import numpy as np
import pytest

from app.services.chunking import Chunk
from app.services.retrieval import HybridSnapshot, reciprocal_rank_fusion


def chunk(identifier, document, text, page=1):
    return Chunk(
        identifier,
        document,
        f"{document}.pdf",
        page,
        page,
        text,
        sha256(text.encode()).hexdigest(),
        0,
        "encoder",
    )


def snapshot():
    chunks = [
        chunk("a", "one", "Contract ABC-104 deadline"),
        chunk("b", "two", "Le délai est indiqué dans le contrat"),
        chunk("c", "three", "مهلت قرارداد فارسی"),
    ]
    return HybridSnapshot.build(
        "version",
        {"model": "fixture"},
        chunks,
        np.array([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]], dtype="float32"),
    )


def test_hybrid_persistence_mapping_and_unicode(tmp_path):
    original = snapshot()
    original.save(tmp_path)
    reopened = HybridSnapshot.load(tmp_path)
    sources = reopened.search(
        "ABC-104",
        np.array([1.0, 0.0]),
        {"one", "two", "three"},
        count_tokens=lambda text: len(text.split()),
    )
    assert sources[0]["chunk_id"] == "a"
    assert reopened.lexical.search("قرارداد", 2)[0][0] == "c"
    assert reopened.lexical.search("unrelated-identifier", 2) == []
    assert reopened.vector.chunk_ids == ("a", "b", "c")


def test_deleted_document_filter_and_budget_apply_to_both_indexes():
    result = snapshot().search(
        "ABC-104",
        np.array([1.0, 0.0]),
        {"two"},
        count_tokens=lambda text: len(text.split()),
        token_budget=100,
    )
    assert result and all(item["document_id"] == "two" for item in result)
    assert snapshot().search("query", np.array([1.0, 0.0]), set()) == []
    assert snapshot().search("query", np.array([1.0, 0.0]), {"one"}, token_budget=1) == []


def test_corrupt_generation_rejected_before_faiss_load(tmp_path):
    snapshot().save(tmp_path)
    (tmp_path / "faiss.index").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        HybridSnapshot.load(tmp_path)


def test_rrf_uses_ranks_not_universal_score_confidence():
    result = reciprocal_rank_fusion([("a", 1000), ("b", -10)], [("b", 0.99)])
    assert result[0][0] == "b"
    assert 0 < result[0][1] < 1
