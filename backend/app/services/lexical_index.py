"""BM25 with Unicode tokens and JSON persistence; never unpickle local text."""
import json
from pathlib import Path
import re
import unicodedata


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+(?:[-./]\w+)*", unicodedata.normalize("NFC", text).casefold())


class LexicalIndex:
    def __init__(self, chunk_ids: list[str], texts: list[str]):
        from rank_bm25 import BM25Okapi
        if len(chunk_ids) != len(texts) or len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("Invalid lexical mapping")
        self.chunk_ids, self.texts = tuple(chunk_ids), tuple(texts)
        self.tokens = [tokenize(text) for text in texts]
        self.bm25 = BM25Okapi(self.tokens) if self.tokens and any(self.tokens) else None

    def save(self, directory: Path):
        (directory / "bm25_index.json").write_text(json.dumps(
            {"chunk_ids": self.chunk_ids, "texts": self.texts}, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, directory: Path):
        data = json.loads((directory / "bm25_index.json").read_text(encoding="utf-8"))
        if not all(isinstance(text, str) for text in data["texts"]):
            raise ValueError("Invalid lexical document text")
        return cls(data["chunk_ids"], data["texts"])

    def search(self, query: str, top_k: int, allowed: set[str] | None = None):
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query_tokens = tokenize(query)
        if self.bm25 is None or not query_tokens:
            return []
        scores = self.bm25.get_scores(query_tokens)
        terms = set(query_tokens)
        candidates = [(self.chunk_ids[index], float(score)) for index, score in enumerate(scores)
                      if terms.intersection(self.tokens[index])
                      and (allowed is None or self.chunk_ids[index] in allowed)]
        return sorted(candidates, key=lambda item: (-item[1], item[0]))[:top_k]
