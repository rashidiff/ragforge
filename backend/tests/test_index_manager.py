import re
from hashlib import sha256
from typing import ClassVar
from unittest.mock import patch
from uuid import uuid4

import numpy as np
import pytest

from app.config import Settings
from app.services.activity_logger import ActivityLogger
from app.services.index_manager import IndexConflictError, IndexManager, IndexUnavailableError
from app.services.pdf_extraction import ExtractedPage, Extraction
from app.services.pdf_ingestion import ValidatedPdf


class Tokenizer:
    def __call__(self, text, **options):
        return {"offset_mapping": [match.span() for match in re.finditer(r"\S+", text)]}


class Embeddings:
    tokenizer = Tokenizer()
    identity: ClassVar[dict] = {
        "model": "fixture",
        "revision": None,
        "resolved_revision": "fixed",
        "normalized": True,
        "encoding": "test",
    }
    version = "fixture-v1"
    max_document_tokens = 500

    def documents(self, texts):
        return np.array([[1.0, 0.0] for text in texts], dtype="float32")

    def query(self, text):
        return np.array([1.0, 0.0], dtype="float32")

    def count_tokens(self, text):
        return len(text.split())


def make_manager(tmp_path):
    config = Settings(_env_file=None, data_dir=tmp_path, embedding_model="fixture")
    config.initialize_directories()
    return IndexManager(config, ActivityLogger(tmp_path / "system.log.jsonl"), Embeddings())


def upload(manager, text="Source deadline 15 days"):
    identifier = str(uuid4())
    path = manager.library.directory / f"{identifier}.upload"
    path.write_bytes(text.encode())
    return ValidatedPdf(
        path, identifier, "fixture.pdf", sha256(text.encode()).hexdigest(), len(text.encode()), 1
    )


def finish(manager):
    manager._executor.submit(lambda: None).result(timeout=10)


@pytest.fixture
def extraction(monkeypatch):
    def read(path, **options):
        text = path.read_text()
        return Extraction((ExtractedPage(1, text, text),), (), False)

    monkeypatch.setattr("app.services.index_manager.extract_pages", read)


def test_generation_restart_and_deleted_source_filter(tmp_path, extraction):
    manager = make_manager(tmp_path)
    pdf = upload(manager)
    manager.submit("upload", pdf=pdf)
    finish(manager)
    assert manager.status()["ready"]
    assert manager.search_library("deadline")[0]["document_id"] == pdf.document_id
    version = manager.status()["index_version"]
    manager.close()
    reopened = make_manager(tmp_path)
    assert reopened.status()["index_version"] == version
    assert reopened.get_source_excerpt(reopened.search_library("deadline")[0]["chunk_id"])[
        "available"
    ]
    reopened.submit("delete", document_id=pdf.document_id)
    assert reopened.search_library("deadline") == []
    finish(reopened)
    assert reopened.status()["ready"]  # Valid initialized empty Library.
    assert not (reopened.library.directory / f"{pdf.document_id}.pdf").exists()
    reopened.close()


def test_rebuild_failure_keeps_previous_generation(tmp_path, extraction):
    manager = make_manager(tmp_path)
    manager.submit("upload", pdf=upload(manager))
    finish(manager)
    old = manager.status()["index_version"]
    with patch("app.services.index_manager.HybridSnapshot.save", side_effect=OSError("disk")):
        manager.submit("rebuild")
        finish(manager)
    assert manager.status()["index_version"] == old
    assert manager.status()["jobs"][0]["stage"] == "failed"
    assert manager.search_library("deadline")
    manager.settings.embedding_model = "different-model"
    assert manager.status()["rebuild_required"]
    with pytest.raises(IndexUnavailableError):
        manager.search_library("deadline")
    manager.close()


def test_second_mutation_rejected_while_job_running(tmp_path, extraction):
    from threading import Event

    manager = make_manager(tmp_path)
    entered, release = Event(), Event()
    original = manager._rebuild

    def blocked(job_id):
        entered.set()
        release.wait(timeout=10)
        return original(job_id)

    with patch.object(manager, "_rebuild", side_effect=blocked):
        manager.submit("upload", pdf=upload(manager))
        entered.wait(timeout=10)
        with pytest.raises(IndexConflictError):
            manager.submit("rebuild")
        release.set()
        finish(manager)
    manager.close()


def test_corrupt_generation_reports_unavailability_and_can_rebuild(tmp_path, extraction):
    manager = make_manager(tmp_path)
    manager.submit("upload", pdf=upload(manager))
    finish(manager)
    version = manager.status()["index_version"]
    manager.close()
    (tmp_path / "index/generations" / version / "chunks.jsonl").write_text("broken")
    reopened = make_manager(tmp_path)
    assert not reopened.status()["ready"]
    assert reopened.status()["warnings"]
    reopened.submit("rebuild")
    finish(reopened)
    assert reopened.search_library("deadline")
    reopened.close()


def test_externally_inaccessible_pdf_is_filtered_from_existing_generation(tmp_path, extraction):
    manager = make_manager(tmp_path)
    pdf = upload(manager)
    manager.submit("upload", pdf=pdf)
    finish(manager)
    source = manager.search_library("deadline")[0]
    managed_path = manager.library.directory / f"{pdf.document_id}.pdf"
    managed_path.unlink()

    assert manager.search_library("deadline") == []
    with pytest.raises(KeyError):
        manager.get_source_excerpt(source["chunk_id"])
    manager.close()


def test_multiple_documents_publish_as_one_validated_generation(tmp_path, extraction):
    from app.services.retrieval import HybridSnapshot

    manager = make_manager(tmp_path)
    first, second = (
        upload(manager, "Alpha source says the deadline is 15 days."),
        upload(manager, "Beta source says the review is 30 days."),
    )
    manager.submit("upload", pdf=first)
    finish(manager)
    manager.submit("upload", pdf=second)
    finish(manager)

    pointer = manager.library.manifest.read()["active_index"]
    generation = HybridSnapshot.load(manager.root / pointer["version"])
    included = {chunk.document_id for chunk in generation.chunks}
    assert included == {first.document_id, second.document_id}
    assert (
        pointer["manifest_sha256"]
        == sha256((manager.root / pointer["version"] / "generation.json").read_bytes()).hexdigest()
    )
    manager.close()


def test_embedding_configuration_change_rebuilds_vectors_with_new_identity(
    tmp_path, extraction, monkeypatch
):
    class ModelEmbeddings(Embeddings):
        def __init__(self, model, revision):
            self.identity = {**Embeddings.identity, "model": model, "revision": revision}
            self.version = f"{model}:{revision or 'default'}"

    manager = make_manager(tmp_path)
    manager.submit("upload", pdf=upload(manager))
    finish(manager)
    manager.settings.embedding_model = "second-fixture"
    manager.settings.embedding_revision = "revision-2"
    monkeypatch.setattr("app.services.index_manager.LocalEmbeddings", ModelEmbeddings)
    manager.submit("rebuild")
    finish(manager)

    assert not manager.status()["rebuild_required"]
    assert manager.search_library("deadline")
    assert manager._snapshot.embedding_identity["model"] == "second-fixture"
    assert manager._snapshot.embedding_identity["revision"] == "revision-2"
    manager.close()


def test_deletion_committed_during_rebuild_is_excluded_from_published_generation(
    tmp_path, extraction
):
    from threading import Event

    manager = make_manager(tmp_path)
    pdf = upload(manager)
    manager.submit("upload", pdf=pdf)
    finish(manager)
    entered, release = Event(), Event()
    original = manager._rebuild

    def pause_before_rebuild(job_id):
        entered.set()
        release.wait(timeout=10)
        return original(job_id)

    with patch.object(manager, "_rebuild", side_effect=pause_before_rebuild):
        manager.submit("rebuild")
        assert entered.wait(timeout=10)
        manager.library.update_status(pdf.document_id, "deleting")
        release.set()
        finish(manager)

    assert manager.search_library("deadline") == []
    assert all(chunk.document_id != pdf.document_id for chunk in manager._snapshot.chunks)
    manager.close()


def test_configured_reranker_orders_bounded_local_candidates_before_final_budget(
    tmp_path, extraction
):
    manager = make_manager(tmp_path)
    manager.settings.retrieval_tokens = 100
    manager.submit("upload", pdf=upload(manager, "Evidence alpha describes the first deadline."))
    finish(manager)
    manager.submit("upload", pdf=upload(manager, "Evidence beta describes the second deadline."))
    finish(manager)

    class ReverseCandidates:
        def __init__(self):
            self.seen = []

        def rank(self, query, candidates):
            self.seen = candidates
            return list(reversed(candidates))

    reranker = ReverseCandidates()
    manager.reranker = reranker
    result = manager.search_library("evidence", top_k=1)
    assert len(reranker.seen) == 2
    assert len(result) == 1
    assert result[0]["chunk_id"] == reranker.seen[-1]["chunk_id"]
    manager.close()


def test_reranker_failure_falls_back_to_hybrid_candidates(tmp_path, extraction):
    manager = make_manager(tmp_path)
    manager.submit("upload", pdf=upload(manager, "Evidence deadline is fifteen days."))
    finish(manager)

    class UnavailableReranker:
        def rank(self, query, candidates):
            from app.services.local_reranker import RerankerError

            raise RerankerError("model unavailable")

    manager.reranker = UnavailableReranker()
    assert manager.search_library("deadline", top_k=1)[0]["text"].startswith("Evidence")
    event = manager.activity.store.records()[-2]
    assert event["event_type"] == "library_reranking_completed"
    assert event["status"] == "fallback"
    manager.close()
