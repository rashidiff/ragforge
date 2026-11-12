"""Local FAISS inner-product search over normalized vectors and stable chunk IDs."""

import json
from pathlib import Path


class VectorIndex:
    def __init__(self, index, chunk_ids: list[str]):
        if len(chunk_ids) != index.ntotal or len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("Vector/chunk mapping is inconsistent")
        self.index, self.chunk_ids = index, tuple(chunk_ids)

    @classmethod
    def build(cls, vectors, chunk_ids: list[str]):
        import faiss
        import numpy as np

        matrix = np.ascontiguousarray(vectors, dtype="float32")
        if matrix.ndim != 2 or matrix.shape[0] != len(chunk_ids) or matrix.shape[1] < 1:
            raise ValueError("Invalid vector matrix")
        if not np.isfinite(matrix).all():
            raise ValueError("Vectors must be finite")
        if len(matrix) and not np.allclose(np.linalg.norm(matrix, axis=1), 1, atol=1e-4):
            raise ValueError("Vectors must be consistently normalized")
        index = faiss.IndexIDMap2(faiss.IndexFlatIP(matrix.shape[1]))
        if len(matrix):
            index.add_with_ids(matrix, np.arange(len(matrix), dtype="int64"))
        return cls(index, chunk_ids)

    def save(self, directory: Path):
        import faiss

        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(directory / "faiss.index"))
        (directory / "faiss_ids.json").write_text(
            json.dumps(list(self.chunk_ids)), encoding="utf-8"
        )

    @classmethod
    def load(cls, directory: Path):
        import faiss
        import numpy as np

        # Caller verifies generation file hashes before invoking FAISS deserialization.
        chunk_ids = json.loads((directory / "faiss_ids.json").read_text(encoding="utf-8"))
        if not isinstance(chunk_ids, list) or not all(
            isinstance(value, str) for value in chunk_ids
        ):
            raise ValueError("Invalid chunk mapping")
        index = faiss.read_index(str(directory / "faiss.index"))
        if not hasattr(index, "id_map") or not np.array_equal(
            faiss.vector_to_array(index.id_map), np.arange(len(chunk_ids), dtype="int64")
        ):
            raise ValueError("Vector IDs do not match the stable mapping")
        return cls(index, chunk_ids)

    def search(self, query, top_k: int, allowed: set[str] | None = None) -> list[tuple[str, float]]:
        import numpy as np

        if top_k < 1:
            raise ValueError("top_k must be positive")
        vector = np.asarray(query, dtype="float32").reshape(1, -1)
        if vector.shape[1] != self.index.d or not np.isfinite(vector).all():
            raise ValueError("Query vector does not match the index")
        norm = np.linalg.norm(vector)
        if norm <= 0:
            raise ValueError("Query vector cannot be empty")
        vector = np.ascontiguousarray(vector / norm)
        if self.index.ntotal == 0:
            return []
        count = self.index.ntotal if allowed is not None else min(top_k, self.index.ntotal)
        scores, identifiers = self.index.search(vector, count)
        results = []
        for identifier, score in zip(identifiers[0], scores[0]):
            if identifier < 0:
                continue
            chunk_id = self.chunk_ids[int(identifier)]
            if allowed is None or chunk_id in allowed:
                results.append((chunk_id, float(score)))
                if len(results) == top_k:
                    break
        return results
