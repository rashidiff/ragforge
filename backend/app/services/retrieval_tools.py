"""Strict dispatcher for the only model-callable local retrieval operations."""

from uuid import UUID

from app.llm.base import ToolCall


class ToolDispatchError(ValueError):
    pass


class RetrievalToolDispatcher:
    def __init__(self, index_manager):
        self.index = index_manager

    def dispatch(self, call: ToolCall) -> dict:
        if not isinstance(call.arguments, dict):
            raise ToolDispatchError("Tool arguments must be an object")
        if call.name == "search_library":
            arguments = call.arguments
            if set(arguments) - {"query", "top_k", "document_ids"}:
                raise ToolDispatchError("Unsupported search_library argument")
            query = arguments.get("query")
            top_k = arguments.get("top_k", 6)
            document_ids = arguments.get("document_ids")
            if not isinstance(query, str) or not query.strip():
                raise ToolDispatchError("Search query must be nonempty text")
            if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
                raise ToolDispatchError("Search top_k must be between 1 and 20")
            if document_ids is not None:
                if not isinstance(document_ids, list) or len(document_ids) > 100:
                    raise ToolDispatchError("Document filter must be a bounded list")
                try:
                    document_ids = [str(UUID(value)) for value in document_ids]
                except (ValueError, TypeError, AttributeError) as exc:
                    raise ToolDispatchError(
                        "Document filter contains an invalid identifier"
                    ) from exc
            results = self.index.search_library(query, top_k, document_ids)
            return {
                "sources": [
                    {
                        key: source[key]
                        for key in (
                            "chunk_id",
                            "document_id",
                            "filename",
                            "page",
                            "page_end",
                            "text",
                            "index_version",
                        )
                    }
                    for source in results
                ]
            }

        if call.name == "get_source_excerpt":
            arguments = call.arguments
            if set(arguments) != {"chunk_id"} or not isinstance(arguments["chunk_id"], str):
                raise ToolDispatchError("get_source_excerpt requires one chunk_id")
            source = self.index.get_source_excerpt(arguments["chunk_id"])
            return {
                key: source[key]
                for key in (
                    "chunk_id",
                    "document_id",
                    "filename",
                    "page_start",
                    "page_end",
                    "text",
                    "index_version",
                    "available",
                )
            }

        raise ToolDispatchError("Only Library retrieval tools are available")
