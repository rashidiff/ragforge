"""Persistent hybrid retrieval and bounded source selection from one immutable generation."""
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable

from .chunking import Chunk
from .lexical_index import LexicalIndex
from .vector_index import VectorIndex

FILES = ("faiss.index", "faiss_ids.json", "bm25_index.json", "chunks.jsonl")


def reciprocal_rank_fusion(*rankings: list[tuple[str, float]], constant: int = 60):
    scores = {}
    for ranking in rankings:
        seen = set()
        for rank, (identifier, _) in enumerate(ranking, start=1):
            if identifier not in seen:
                scores[identifier] = scores.get(identifier, 0) + 1 / (constant + rank)
                seen.add(identifier)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


@dataclass(frozen=True)
class HybridSnapshot:
    version: str
    embedding_identity: dict
    chunks: tuple[Chunk, ...]
    vector: VectorIndex
    lexical: LexicalIndex

    @classmethod
    def build(cls, version: str, identity: dict, chunks: list[Chunk], vectors):
        identifiers = [chunk.chunk_id for chunk in chunks]
        return cls(version, dict(identity), tuple(chunks), VectorIndex.build(vectors, identifiers),
                   LexicalIndex(identifiers, [chunk.text for chunk in chunks]))

    def save(self, directory: Path):
        self.vector.save(directory)
        self.lexical.save(directory)
        (directory / "chunks.jsonl").write_text("".join(
            json.dumps(chunk.record(), ensure_ascii=False) + "\n" for chunk in self.chunks), encoding="utf-8")
        manifest = {"schema_version": 1, "version": self.version,
                    "embedding_identity": self.embedding_identity,
                    "hashes": {name: sha256((directory / name).read_bytes()).hexdigest() for name in FILES}}
        (directory / "generation.json").write_text(json.dumps(manifest), encoding="utf-8")

    @classmethod
    def load(cls, directory: Path):
        manifest = json.loads((directory / "generation.json").read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            raise ValueError("Unsupported index generation schema")
        for name in FILES:
            path = directory / name
            if not path.resolve().is_relative_to(directory.resolve()) or not path.is_file():
                raise ValueError("Missing or unsafe index generation file")
            if sha256(path.read_bytes()).hexdigest() != manifest["hashes"][name]:
                raise ValueError("Index checksum mismatch; rebuild from original PDFs")
        chunks = tuple(Chunk(**json.loads(line)) for line in
                       (directory / "chunks.jsonl").read_text(encoding="utf-8").splitlines())
        vector, lexical = VectorIndex.load(directory), LexicalIndex.load(directory)
        ids = tuple(chunk.chunk_id for chunk in chunks)
        if ids != vector.chunk_ids or ids != lexical.chunk_ids or tuple(chunk.text for chunk in chunks) != lexical.texts:
            raise ValueError("Index generation contains mismatched mappings")
        for chunk in chunks:
            if sha256(chunk.text.encode("utf-8")).hexdigest() != chunk.sha256 or chunk.page_start < 1 or chunk.page_end < chunk.page_start:
                raise ValueError("Chunk provenance is invalid")
        return cls(manifest["version"], manifest["embedding_identity"], chunks, vector, lexical)

    def search(self, query: str, query_vector, active_document_ids: set[str],
               candidate_count: int = 20, snippet_count: int = 6, token_budget: int = 4000,
               count_tokens: Callable[[str], int] | None = None) -> list[dict]:
        if not query.strip() or min(candidate_count, snippet_count, token_budget) < 1:
            raise ValueError("A nonempty query and positive retrieval budgets are required")
        by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
        allowed = {chunk.chunk_id for chunk in self.chunks if chunk.document_id in active_document_ids}
        if not allowed:
            return []
        dense = self.vector.search(query_vector, candidate_count, allowed)
        lexical = self.lexical.search(query, candidate_count, allowed)
        fused = reciprocal_rank_fusion(dense, lexical)
        used, seen, sources = 0, set(), []
        counter = count_tokens or (lambda text: len(text.encode("utf-8")))
        for identifier, score in fused:
            chunk = by_id[identifier]
            key = (chunk.document_id, chunk.page_start, chunk.page_end, chunk.sha256)
            cost = counter(chunk.text)
            if key in seen or cost + used > token_budget:
                continue
            seen.add(key)
            used += cost
            sources.append({**chunk.record(), "page": chunk.page_start, "score": score,
                            "index_version": self.version, "available": True})
            if len(sources) >= snippet_count:
                break
        return sources
