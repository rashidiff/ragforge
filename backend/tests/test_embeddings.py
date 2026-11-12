import numpy as np
import pytest

from app.services.embeddings import EmbeddingError, LocalEmbeddings


class Tokenizer:
    is_fast = True

    def encode(self, text, add_special_tokens=False):
        return list(range(len(text.split()) + (2 if add_special_tokens else 0)))

    def num_special_tokens_to_add(self, pair=False):
        return 2


class Model:
    tokenizer = Tokenizer()
    max_seq_length = 512
    prompts = {}

    def __init__(self):
        self.calls = []

    def get_sentence_embedding_dimension(self):
        return 2

    def encode(self, texts, **options):
        self.calls.append((texts, options))
        return np.array([[3, 4] for text in texts], dtype="float32")


def test_e5_prefixes_normalization_and_cpu_loading():
    model = Model()
    loads = []

    def factory(name, **options):
        loads.append((name, options))
        return model

    encoder = LocalEmbeddings(revision="pinned", model_factory=factory)
    assert loads == []
    vectors = encoder.documents(["فارسی français", "English passage"])
    query = encoder.query("query text")
    assert model.calls[0][0] == ["passage: فارسی français", "passage: English passage"]
    assert model.calls[1][0] == ["query: query text"]
    assert loads[0][1]["device"] == "cpu"
    assert loads[0][1]["trust_remote_code"] is False
    assert loads[0][1]["revision"] == "pinned"
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1)
    np.testing.assert_allclose(np.linalg.norm(query), 1)


def test_input_limit_is_not_silently_truncated():
    model = Model()
    model.max_seq_length = 8
    encoder = LocalEmbeddings(model_factory=lambda *args, **kwargs: model)
    with pytest.raises(EmbeddingError, match="exceeds"):
        encoder.query(" ".join(["word"] * 10))
    assert model.calls == []


def test_native_model_uses_native_document_encoder_and_changes_identity():
    model = Model()
    model.encode_document = model.encode
    model.encode_query = model.encode
    encoder = LocalEmbeddings("local/native", model_factory=lambda *args, **kwargs: model)
    encoder.documents(["text"])
    assert model.calls[0][0] == ["text"]
    other = LocalEmbeddings(
        "local/native", revision="other", model_factory=lambda *args, **kwargs: model
    )
    assert encoder.version != other.version
