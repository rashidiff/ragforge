"""Conservative per-model context accounting for the logical provider request."""

import json
import math
from dataclasses import dataclass

from app.llm.base import GenerationRequest


@dataclass(frozen=True)
class ContextBudgetReport:
    provider: str
    model: str
    context_tokens: int
    output_reserve: int
    safety_reserve: int
    estimated_input_tokens: int

    @property
    def input_limit(self) -> int:
        return self.context_tokens - self.output_reserve - self.safety_reserve

    @property
    def fits(self) -> bool:
        return self.estimated_input_tokens <= self.input_limit


class ContextBudget:
    """Use model tokenization when locally available; otherwise fail conservatively.

    UTF-8 byte count is an upper bound for byte-pair tokenizers and avoids silently
    undercounting multilingual text when a provider tokenizer is unavailable.
    """

    def __init__(
        self, provider: str, model: str, context_tokens: int, output_tokens: int, token_counter=None
    ):
        if context_tokens < 1 or not 0 < output_tokens < context_tokens:
            raise ValueError("A valid model context window and output reserve are required")
        self.provider, self.model = provider, model
        self.context_tokens, self.output_tokens = context_tokens, output_tokens
        self.token_counter = token_counter

    def count(self, text: str) -> int:
        if self.token_counter is not None:
            return max(0, int(self.token_counter(text)))
        if self.provider == "openai":
            try:
                import tiktoken

                try:
                    encoding = tiktoken.encoding_for_model(self.model)
                except KeyError:
                    encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(text))
            except (ImportError, KeyError):
                pass
        # Without an installed provider tokenizer, one UTF-8 byte per token is a
        # deliberately conservative bound rather than a guessed language ratio.
        return len(text.encode("utf-8"))

    @property
    def safety_reserve(self) -> int:
        return max(128, math.ceil(self.context_tokens * 0.05))

    def measure(self, request: GenerationRequest) -> ContextBudgetReport:
        parts = ["System instructions:\n", request.system]
        if request.memory:
            parts.extend(("\n\nPersisted conversation memory:\n", request.memory))
        for message in request.tail:
            parts.extend((f"\n\n{message.role}:\n", message.content))
        for source in request.sources:
            parts.extend(
                (
                    (
                        f"\n\n[Untrusted source id={source.chunk_id}; file={source.filename}; "
                        f"pages={source.page_start}-{source.page_end}]\n"
                    ),
                    source.text,
                )
            )
        parts.extend(("\n\nCurrent question:\n", request.current_question))
        if request.tool_exchanges:
            parts.extend(
                (
                    "\n\nTool exchanges:\n",
                    json.dumps(
                        [
                            {
                                "name": exchange.call.name,
                                "arguments": exchange.call.arguments,
                                "result": exchange.result,
                            }
                            for exchange in request.tool_exchanges
                        ],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                )
            )
        input_tokens = self.count("".join(parts))
        # Provider message framing and tool definitions are not represented by text.
        input_tokens += 8 * (len(request.tail) + len(request.sources) + 3)
        if request.tools_enabled:
            input_tokens += 256
        return ContextBudgetReport(
            self.provider,
            self.model,
            self.context_tokens,
            self.output_tokens,
            self.safety_reserve,
            input_tokens,
        )

    def report(self, request: GenerationRequest) -> ContextBudgetReport:
        return self.measure(request)
