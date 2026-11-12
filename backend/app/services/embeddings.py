"""CPU-only local embeddings. No text is sent to an embedding API."""

from collections.abc import Callable
from threading import RLock


class EmbeddingError(RuntimeError):
    pass


class LocalEmbeddings:
    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-small",
        revision: str | None = None,
        batch_size: int = 32,
        model_factory: Callable | None = None,
    ):
        if not model_name.strip() or batch_size < 1:
            raise ValueError("Embedding model and a positive batch size are required")
        self.model_name = model_name
        self.revision = revision
        self.batch_size = batch_size
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
                        from sentence_transformers import SentenceTransformer
                    except ImportError as exc:
                        raise EmbeddingError(
                            "Install the backend rag dependencies to enable local embeddings"
                        ) from exc
                    factory = SentenceTransformer
                try:
                    self._model = factory(
                        self.model_name,
                        revision=self.revision,
                        device="cpu",
                        trust_remote_code=False,
                        token=False,
                    )
                except Exception as exc:
                    raise EmbeddingError(
                        "Local embedding model could not be loaded. Check the model name, cache and initial download access."
                    ) from exc
            return self._model

    @property
    def tokenizer(self):
        tokenizer = self.model.tokenizer
        if not getattr(tokenizer, "is_fast", False):
            raise EmbeddingError(
                "This embedding model needs a fast tokenizer with source offsets for chunking"
            )
        return tokenizer

    @property
    def identity(self) -> dict:
        model = self.model
        try:
            commit = getattr(model[0].auto_model.config, "_commit_hash", None)
        except (AttributeError, IndexError, TypeError):
            commit = None
        return {
            "model": self.model_name,
            "revision": self.revision,
            "resolved_revision": commit,
            "normalized": True,
            "encoding": "e5-prefix-v1" if self.is_e5 else "model-native-v1",
        }

    @property
    def version(self) -> str:
        import json
        from hashlib import sha256

        return sha256(json.dumps(self.identity, sort_keys=True).encode()).hexdigest()

    @property
    def is_e5(self) -> bool:
        return "e5" in self.model_name.lower().split("/")[-1]

    def _prefix(self, query: bool) -> str:
        if self.is_e5:
            return "query: " if query else "passage: "
        prompts = getattr(self.model, "prompts", {}) or {}
        return prompts.get(
            "query" if query else "document", prompts.get("passage", "") if not query else ""
        )

    @property
    def max_document_tokens(self) -> int:
        tokenizer = self.tokenizer
        prefix_tokens = len(tokenizer.encode(self._prefix(False), add_special_tokens=False))
        special = tokenizer.num_special_tokens_to_add(pair=False)
        return max(1, int(self.model.max_seq_length) - prefix_tokens - special - 2)

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def _encode(self, texts: list[str], query: bool):
        import numpy as np

        with self._lock:
            model = self.model
            dimension = int(model.get_sentence_embedding_dimension())
            if not texts:
                return np.empty((0, dimension), dtype="float32")
            prefix = self._prefix(query)
            for text in texts:
                if not isinstance(text, str) or not text.strip():
                    raise EmbeddingError("Cannot embed empty text")
                tokens = self.tokenizer.encode(prefix + text, add_special_tokens=True)
                if len(tokens) > model.max_seq_length:
                    raise EmbeddingError(
                        "Text exceeds the embedding model limit; reduce chunk size or shorten the retrieval query"
                    )
            try:
                if self.is_e5:
                    vectors = model.encode(
                        [prefix + text for text in texts],
                        prompt="",
                        batch_size=self.batch_size,
                        normalize_embeddings=True,
                        convert_to_numpy=True,
                        show_progress_bar=False,
                    )
                else:
                    method = getattr(model, "encode_query" if query else "encode_document", None)
                    vectors = (method or model.encode)(
                        texts,
                        batch_size=self.batch_size,
                        normalize_embeddings=True,
                        convert_to_numpy=True,
                        show_progress_bar=False,
                        **({"prompt": prefix} if method is None else {}),
                    )
                matrix = np.asarray(vectors, dtype="float32")
                if matrix.shape != (len(texts), dimension) or not np.isfinite(matrix).all():
                    raise ValueError("Invalid embedding shape or values")
                norms = np.linalg.norm(matrix, axis=1, keepdims=True)
                if (norms <= 0).any():
                    raise ValueError("Embedding contains a zero vector")
                return np.ascontiguousarray(matrix / norms, dtype="float32")
            except EmbeddingError:
                raise
            except Exception as exc:
                raise EmbeddingError("Local embedding computation failed") from exc

    def documents(self, texts: list[str]):
        return self._encode(texts, query=False)

    def query(self, text: str):
        return self._encode([text], query=True)[0]
