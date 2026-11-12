from uuid import uuid4

import pytest

from app.llm.base import ToolCall
from app.services.retrieval_tools import RetrievalToolDispatcher, ToolDispatchError


class FakeIndex:
    def __init__(self):
        self.search_args = None
        self.source_id = None

    def search_library(self, query, top_k, document_ids):
        self.search_args = (query, top_k, document_ids)
        return [
            {
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "filename": "local.pdf",
                "page": 4,
                "page_end": 4,
                "text": "local excerpt",
                "index_version": "v1",
                "score": 0.4,
                "private_extra": "not serialized",
            }
        ]

    def get_source_excerpt(self, chunk_id):
        self.source_id = chunk_id
        return {
            "chunk_id": chunk_id,
            "document_id": "doc-1",
            "filename": "local.pdf",
            "page_start": 4,
            "page_end": 4,
            "text": "current local excerpt",
            "index_version": "v1",
            "available": True,
            "score": 1.0,
        }


def test_search_tool_validates_and_returns_only_bounded_library_fields():
    index = FakeIndex()
    document_id = str(uuid4())
    result = RetrievalToolDispatcher(index).dispatch(
        ToolCall(
            "call-1",
            "search_library",
            {"query": "deadline فارسی", "top_k": 3, "document_ids": [document_id]},
        )
    )
    assert index.search_args == ("deadline فارسی", 3, [document_id])
    assert result == {
        "sources": [
            {
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "filename": "local.pdf",
                "page": 4,
                "page_end": 4,
                "text": "local excerpt",
                "index_version": "v1",
            }
        ]
    }


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": " "},
        {"query": "valid", "top_k": 21},
        {"query": "valid", "top_k": True},
        {"query": "valid", "document_ids": ["bad-id"]},
        {"query": "valid", "path": "C:/secret"},
    ],
)
def test_search_tool_rejects_invalid_or_privileged_arguments(arguments):
    with pytest.raises(ToolDispatchError):
        RetrievalToolDispatcher(FakeIndex()).dispatch(
            ToolCall("call-1", "search_library", arguments)
        )


def test_excerpt_tool_delegates_to_current_available_source_lookup():
    index = FakeIndex()
    result = RetrievalToolDispatcher(index).dispatch(
        ToolCall("call-2", "get_source_excerpt", {"chunk_id": "chunk-9"})
    )
    assert index.source_id == "chunk-9"
    assert result["available"] is True
    assert result["text"] == "current local excerpt"
    assert "score" not in result


def test_excerpt_tool_rejects_paths_and_extra_arguments():
    with pytest.raises(ToolDispatchError):
        RetrievalToolDispatcher(FakeIndex()).dispatch(
            ToolCall("call-3", "get_source_excerpt", {"chunk_id": "chunk-9", "path": "C:/secret"})
        )
