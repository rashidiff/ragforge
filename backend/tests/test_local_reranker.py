import numpy as np

from app.services.local_reranker import LocalReranker


def test_cross_encoder_ranks_local_candidate_text_and_loads_on_cpu():
    loaded = {}

    class FakeModel:
        def predict(self, pairs, **options):
            assert options["show_progress_bar"] is False
            assert pairs == [("question فارسی", "weak"), ("question فارسی", "strong")]
            return np.asarray([0.1, 0.9])

    def factory(name, **options):
        loaded.update(name=name, **options)
        return FakeModel()

    reranker = LocalReranker("fixture/multilingual-cross-encoder", factory)
    candidates = [{"chunk_id": "a", "text": "weak"}, {"chunk_id": "b", "text": "strong"}]
    assert [row["chunk_id"] for row in reranker.rank("question فارسی", candidates)] == ["b", "a"]
    assert loaded == {"name": "fixture/multilingual-cross-encoder", "device": "cpu",
                      "trust_remote_code": False}


def test_rank_is_stable_for_equal_scores():
    class FakeModel:
        def predict(self, pairs, **options):
            return [0.5 for _ in pairs]

    reranker = LocalReranker("fixture", lambda *args, **kwargs: FakeModel())
    candidates = [{"chunk_id": "z", "text": "one"}, {"chunk_id": "a", "text": "two"}]
    assert [row["chunk_id"] for row in reranker.rank("question", candidates)] == ["a", "z"]


def test_empty_candidate_list_does_not_load_model():
    reranker = LocalReranker("fixture", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    assert reranker.rank("question", []) == []
