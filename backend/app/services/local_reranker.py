"""Optional CPU-only multilingual cross-encoder reranking for local candidates."""

from collections.abc import Callable
from threading import RLock


class RerankerError(RuntimeError):
    pass


class LocalReranker:
    """Load a configured Sentence Transformers CrossEncoder lazily and keep text local."""

    def __init__(self, model_name: str, model_factory: Callable | None = None):
        if not model_name.strip():
            raise ValueError("A reranker model name is required")
        self.model_name = model_name
        self._factory = model_factory
        self._model = None
        self._lock = RLock()

    @property
    def model(self):
        with self._lock:
            if self._model is None:
                factory = self._factory
                if factory is None:
                    try:
                        from sentence_transformers import CrossEncoder
                    except ImportError as exc:
                        raise RerankerError(
                            "Install the local RAG dependencies to enable reranking"
                        ) from exc
                    factory = CrossEncoder
                try:
                    self._model = factory(self.model_name, device="cpu", trust_remote_code=False)
                except Exception as exc:
                    raise RerankerError(
                        "The configured local reranker could not be loaded"
                    ) from exc
            return self._model

    def rank(self, query: str, candidates: list[dict]) -> list[dict]:
        if not candidates:
            return []
        try:
            scores = self.model.predict(
                [(query, item["text"]) for item in candidates], show_progress_bar=False
            )
            values = [float(score) for score in scores]
            if len(values) != len(candidates):
                raise ValueError("Reranker returned a mismatched score count")
        except RerankerError:
            raise
        except Exception as exc:
            raise RerankerError("Local reranking failed") from exc
        return [
            item
            for _, item in sorted(
                zip(values, candidates), key=lambda pair: (-pair[0], pair[1]["chunk_id"])
            )
        ]
