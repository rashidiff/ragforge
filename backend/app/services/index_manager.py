"""Serialized indexing jobs and atomic, restartable generation publication."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from threading import Event, RLock
from uuid import UUID, uuid4

from app.config import Settings

from .chunking import Chunker
from .embeddings import EmbeddingError, LocalEmbeddings
from .local_reranker import LocalReranker, RerankerError
from .pdf_extraction import extract_pages
from .pdf_ingestion import LibraryStore, PdfIntakeError, ValidatedPdf, managed_pdf_path
from .retrieval import HybridSnapshot
from .state_store import JsonState


def timestamp():
    return datetime.now(UTC).isoformat()


class IndexConflictError(RuntimeError):
    pass


class IndexUnavailableError(RuntimeError):
    pass


class IndexManager:
    def __init__(self, settings: Settings, activity, embeddings=None, reranker=None):
        self.settings, self.activity = settings, activity
        self.library = LibraryStore(settings.data_dir)
        self.embeddings = embeddings or LocalEmbeddings(
            settings.embedding_model, settings.embedding_revision
        )
        self.reranker = (
            reranker
            if reranker is not None
            else (LocalReranker(settings.reranker_model) if settings.reranker_model else None)
        )
        self._encoder_config = (settings.embedding_model, settings.embedding_revision)
        self.root = settings.data_dir / "index/generations"
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs = JsonState(
            settings.data_dir / "state/index_jobs.json", {"schema_version": 1, "jobs": {}}
        )
        self._lock, self._stop = RLock(), Event()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-index")
        self._busy = False
        self._snapshot: HybridSnapshot | None = None
        self._unavailable = None
        self._recover_jobs()
        self._restore()

    def _recover_jobs(self):
        def mutate(state):
            for job in state["jobs"].values():
                if job["stage"] not in {"ready", "failed"}:
                    job.update(
                        stage="failed",
                        finished_at=timestamp(),
                        error="Indexing was interrupted. Retry the operation.",
                    )

        self.jobs.update(mutate)

    def _restore(self):
        pointer = self.library.manifest.read().get("active_index")
        if pointer is None:
            return
        try:
            version = str(UUID(pointer["version"]))
            directory = self.root / version
            if not directory.resolve().is_relative_to(self.root.resolve()):
                raise ValueError("Invalid generation path")
            metadata = directory / "generation.json"
            if sha256(metadata.read_bytes()).hexdigest() != pointer["manifest_sha256"]:
                raise ValueError("Generation metadata mismatch")
            self._snapshot = HybridSnapshot.load(directory)
            if self._snapshot.version != version:
                raise ValueError("Generation version mismatch")
        except (OSError, ValueError, TypeError, KeyError, ImportError, RuntimeError):
            self._snapshot = None
            self._unavailable = "The saved index cannot be read. Install local RAG dependencies if missing, or rebuild from original PDFs."

    def _compatible(self, snapshot) -> bool:
        return (
            snapshot is not None
            and snapshot.embedding_identity.get("model") == self.settings.embedding_model
            and snapshot.embedding_identity.get("revision") == self.settings.embedding_revision
        )

    def _active_ids(self, state: dict, snapshot) -> set[str]:
        if snapshot is None:
            return set()
        present = {chunk.document_id for chunk in snapshot.chunks}
        return {
            identifier
            for identifier, document in state["documents"].items()
            if identifier in present
            and document["status"] == "ready"
            and managed_pdf_path(self.library.directory, identifier).is_file()
        }

    def status(self, job_id: str | None = None) -> dict:
        with self._lock:
            jobs = self.jobs.read()["jobs"]
            if job_id is not None and job_id not in jobs:
                raise KeyError("Job not found")
            state = self.library.manifest.read()
            documents = [
                document
                for document in state["documents"].values()
                if document["status"] not in {"deleting", "deleted"}
            ]
            compatible = self._compatible(self._snapshot)
            warnings = []
            if not documents:
                warnings.append("Library is empty. Upload PDFs to enable document search.")
            if self._unavailable:
                warnings.append(self._unavailable)
            if self._snapshot is not None and not compatible:
                warnings.append(
                    "Embedding configuration changed. A full rebuild is required before search."
                )
            return {
                "index_version": self._snapshot.version
                if compatible and self._snapshot is not None
                else None,
                "ready": (not documents and not self._unavailable)
                or (compatible and bool(self._active_ids(state, self._snapshot))),
                "jobs": [jobs[job_id]]
                if job_id
                else sorted(jobs.values(), key=lambda job: job["started_at"], reverse=True),
                "warnings": warnings,
                "rebuild_required": bool(documents) and not compatible,
            }

    def _progress(
        self,
        job_id: str,
        stage: str,
        processed: int = 0,
        total: int | None = None,
        document_id: str | None = None,
    ):
        if self._stop.is_set():
            raise IndexUnavailableError(
                "Indexing interrupted during application shutdown. Retry after restart."
            )

        def mutate(state):
            state["jobs"][job_id].update(
                stage=stage, processed=processed, total=total, document_id=document_id
            )

        self.jobs.update(mutate)
        self.activity.emit(
            "indexing_progress",
            job_id=job_id,
            stage=stage,
            document_id=document_id,
            processed=processed,
            total=total,
        )

    def submit(self, kind: str, document_id: str | None = None, pdf: ValidatedPdf | None = None):
        if kind not in {"upload", "reindex", "rebuild", "delete"}:
            raise ValueError("Unknown index operation")
        with self._lock:
            if self._busy or self._stop.is_set():
                raise IndexConflictError(
                    "Another Library update is running. Wait for it to finish."
                )
            document = None
            if kind == "upload":
                if pdf is None:
                    raise ValueError("A validated PDF is required")
                document = self.library.accept(pdf)
                document_id = document["document_id"]
            elif document_id is not None:
                document = next(
                    (
                        entry
                        for entry in self.library.list()
                        if entry["document_id"] == document_id
                        and entry["status"] not in {"deleted", "deleting"}
                    ),
                    None,
                )
                if document is None:
                    raise KeyError("Document not found")
                if kind == "delete":
                    # Commit exclusion before accepting new retrieval requests.
                    self.library.update_status(document_id, "deleting")
            identifier = str(uuid4())
            job = {
                "job_id": identifier,
                "kind": kind,
                "document_id": document_id,
                "stage": "queued",
                "processed": 0,
                "total": None,
                "started_at": timestamp(),
                "finished_at": None,
                "error": None,
            }
            self.jobs.update(lambda state: state["jobs"].__setitem__(identifier, job))
            self._busy = True
            try:
                self._executor.submit(self._run, identifier, kind, document_id)
            except BaseException:
                self._busy = False
                raise
            return {"job": job, "document": document}

    def _run(self, job_id: str, kind: str, document_id: str | None):
        started = time.monotonic()
        try:
            self._rebuild(job_id)
            for entry in self.library.list():
                if entry["status"] == "deleting":
                    # Also resume deletion left pending by a previous failed rebuild.
                    managed_pdf_path(self.library.directory, entry["document_id"]).unlink(
                        missing_ok=True
                    )
                    self.library.update_status(entry["document_id"], "deleted")
            if kind in {"upload", "reindex"} and document_id:
                current = next(
                    entry for entry in self.library.list() if entry["document_id"] == document_id
                )
                if current["status"] == "failed":
                    raise PdfIntakeError(
                        "no_searchable_text",
                        current["error"] or "No searchable text found. Local OCR may be required.",
                    )
            self._progress(job_id, "ready")
            self.jobs.update(lambda state: state["jobs"][job_id].update(finished_at=timestamp()))
            self.activity.emit(
                "indexing_completed",
                job_id=job_id,
                document_id=document_id,
                duration_ms=(time.monotonic() - started) * 1000,
            )
        except Exception as exc:  # noqa: BLE001 -- Worker records unexpected failures without publishing partial indexes.
            storage_details = (
                {"errno": exc.errno, "winerror": getattr(exc, "winerror", None)}
                if isinstance(exc, OSError)
                else None
            )
            safe = (
                str(exc)
                if isinstance(exc, (EmbeddingError, PdfIntakeError, IndexUnavailableError))
                else "Local indexing failed. Check dependencies, original PDFs and disk access, then retry."
            )
            if isinstance(exc, OSError):
                safe = (
                    f"Local index storage failed (OS error {exc.errno}). "
                    "Check write permissions and available disk space, then retry indexing."
                )
            try:
                if kind == "upload" and document_id:
                    self.library.update_status(document_id, "failed", error=safe)
                self.jobs.update(
                    lambda state: state["jobs"][job_id].update(
                        stage="failed", error=safe, finished_at=timestamp()
                    )
                )
                self.activity.emit(
                    "indexing_failed",
                    severity="ERROR",
                    job_id=job_id,
                    document_id=document_id,
                    error_category=type(exc).__name__,
                    storage_error=storage_details,
                    duration_ms=(time.monotonic() - started) * 1000,
                )
            finally:
                with self._lock:
                    self._busy = False
            return
        finally:
            with self._lock:
                self._busy = False

    def _rebuild(self, job_id: str):
        desired = (self.settings.embedding_model, self.settings.embedding_revision)
        if desired != self._encoder_config:
            with self._lock:
                self.embeddings = LocalEmbeddings(*desired)
                self._encoder_config = desired
        documents = [
            entry for entry in self.library.list() if entry["status"] not in {"deleted", "deleting"}
        ]
        chunks, included, warnings_by_id = [], {}, {}
        # An empty generation must also remove every old source, without a model download.
        if documents:
            self._progress(job_id, "loading_model")
            identity = self.embeddings.identity
            model_version = self.embeddings.version
            target = min(self.settings.chunk_tokens, self.embeddings.max_document_tokens)
            overlap = min(self.settings.chunk_overlap, max(0, target - 1))
            chunker = Chunker(self.embeddings.tokenizer, target, overlap)
        else:
            identity = {
                "model": self.settings.embedding_model,
                "revision": self.settings.embedding_revision,
                "resolved_revision": None,
                "normalized": True,
                "encoding": "empty",
            }
        for position, document in enumerate(documents):
            identifier = document["document_id"]
            self._progress(job_id, "extracting", position, len(documents), identifier)

            def report_ocr_page(processed: int, total: int, identifier=identifier):
                self.library.update_status(identifier, "ocr")
                self._progress(job_id, "ocr", processed, total, identifier)

            extraction = extract_pages(
                managed_pdf_path(self.library.directory, identifier),
                ocr_enabled=self.settings.ocr_enabled,
                ocr_languages=self.settings.ocr_languages,
                on_ocr_page=report_ocr_page,
            )
            warnings_by_id[identifier] = list(extraction.warnings)
            self._progress(job_id, "chunking", position, len(documents), identifier)
            document_chunks = chunker.chunks(
                identifier, document["original_name"], extraction.pages, model_version
            )
            if not document_chunks:
                self.library.update_status(
                    identifier,
                    "failed",
                    warnings=extraction.warnings,
                    error="No searchable text found. Enable local OCR when available or upload a text PDF.",
                )
                continue
            included[identifier] = document["sha256"]
            chunks.extend(document_chunks)
        self._progress(job_id, "embedding", 0, len(chunks))
        if chunks:
            import numpy as np

            batches = []
            for start in range(0, len(chunks), 32):
                self._progress(job_id, "embedding", start, len(chunks))
                batches.append(
                    self.embeddings.documents([chunk.text for chunk in chunks[start : start + 32]])
                )
            vectors = np.concatenate(batches, axis=0)
        else:
            import numpy as np

            vectors = np.empty((0, 1), dtype="float32")
        self._progress(job_id, "indexing", len(chunks), len(chunks))
        version = str(uuid4())
        directory = self.root / version
        directory.mkdir()
        snapshot = HybridSnapshot.build(version, identity, chunks, vectors)
        snapshot.save(directory)
        # This is runtime generation validation, not a development test/verification run.
        for path in directory.iterdir():
            # Windows flushes require a writable handle; read-only fsync can fail
            # even when the index files were written successfully.
            with path.open("r+b") as stream:
                os.fsync(stream.fileno())
        validated = HybridSnapshot.load(directory)
        if os.name == "posix":
            for parent in (directory, self.root):
                descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        pointer = {
            "version": version,
            "manifest_sha256": sha256((directory / "generation.json").read_bytes()).hexdigest(),
        }
        with self._lock:

            def publish(state):
                for identifier, content_hash in included.items():
                    current = state["documents"].get(identifier)
                    if (
                        current is None
                        or current["sha256"] != content_hash
                        or current["status"] in {"deleted", "deleting"}
                    ):
                        raise IndexConflictError(
                            "Library changed before index publication. Rebuild again."
                        )
                state["active_index"] = pointer
                for identifier in included:
                    state["documents"][identifier].update(
                        status="ready",
                        index_version=version,
                        warnings=warnings_by_id[identifier],
                        error=None,
                    )

            self.library.manifest.update(publish)
            self._snapshot, self._unavailable = validated, None

    def search_library(
        self, query: str, top_k: int = 6, optional_document_ids: list[str] | None = None
    ):
        if not 1 <= top_k <= 20 or not query.strip():
            raise ValueError("Search requires nonblank text and top_k between 1 and 20")
        with self._lock:
            snapshot = self._snapshot
            encoder = self.embeddings
            if snapshot is None or not self._compatible(snapshot):
                raise IndexUnavailableError(
                    "Library index is unavailable or uses another embedding model. Rebuild it."
                )
            active = self._active_ids(self.library.manifest.read(), snapshot)
            if optional_document_ids is not None:
                active &= {str(UUID(identifier)) for identifier in optional_document_ids}
        if not active:
            return []
        if encoder.identity != snapshot.embedding_identity:
            raise IndexUnavailableError(
                "Embedding model revision changed. Rebuild before querying."
            )
        candidates = snapshot.search(
            query,
            encoder.query(query),
            active,
            candidate_count=self.settings.retrieval_candidates,
            snippet_count=min(self.settings.retrieval_candidates, 20),
            token_budget=self.settings.retrieval_tokens * 4,
            count_tokens=encoder.count_tokens,
        )
        sources = candidates
        if self.reranker is not None and candidates:
            started = time.monotonic()
            try:
                sources = self.reranker.rank(query, candidates)
                self.activity.emit(
                    "library_reranking_completed",
                    index_version=snapshot.version,
                    model=self.settings.reranker_model,
                    candidate_count=len(candidates),
                    duration_ms=int((time.monotonic() - started) * 1000),
                    status="success",
                )
            except RerankerError:
                # A configured enhancement cannot take deterministic local retrieval offline.
                self.activity.emit(
                    "library_reranking_completed",
                    index_version=snapshot.version,
                    model=self.settings.reranker_model,
                    candidate_count=len(candidates),
                    duration_ms=int((time.monotonic() - started) * 1000),
                    status="fallback",
                    error_category="local_reranker_unavailable",
                )
        selected, used, seen = [], 0, set()
        for source in sources:
            key = (
                source["document_id"],
                source["page"],
                source.get("page_end", source["page"]),
                source["sha256"],
            )
            cost = encoder.count_tokens(source["text"])
            if key in seen or used + cost > self.settings.retrieval_tokens:
                continue
            selected.append(source)
            seen.add(key)
            used += cost
            if len(selected) >= top_k:
                break
        sources = selected
        with self._lock:
            current_active = self._active_ids(self.library.manifest.read(), snapshot)
            sources = [source for source in sources if source["document_id"] in current_active]
        self.activity.emit(
            "library_search",
            query=query,
            index_version=snapshot.version,
            sources=[
                {key: source[key] for key in ("chunk_id", "document_id", "page", "score")}
                for source in sources
            ],
        )
        return sources

    def get_source_excerpt(self, chunk_id: str):
        with self._lock:
            if self._snapshot is None or not self._compatible(self._snapshot):
                raise IndexUnavailableError("Library index is unavailable")
            active = self._active_ids(self.library.manifest.read(), self._snapshot)
            for chunk in self._snapshot.chunks:
                if chunk.chunk_id == chunk_id and chunk.document_id in active:
                    return {
                        **chunk.record(),
                        "index_version": self._snapshot.version,
                        "available": True,
                    }
        raise KeyError("Source not found or unavailable")

    def close(self):
        self._stop.set()
        self._executor.shutdown(wait=True, cancel_futures=True)
