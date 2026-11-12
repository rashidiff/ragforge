import asyncio

import pytest

from app.services.generation_registry import GenerationConflictError, GenerationRegistry


def test_registry_allows_different_chats_but_rejects_same_chat_and_enforces_limit():
    registry = GenerationRegistry(maximum=2)
    first = registry.acquire("chat-one")
    second = registry.acquire("chat-two")
    with pytest.raises(GenerationConflictError) as duplicate:
        registry.acquire("chat-one")
    assert duplicate.value.status_code == 409
    with pytest.raises(GenerationConflictError) as busy:
        registry.acquire("chat-three")
    assert busy.value.status_code == 429
    assert registry.cancel("chat-two") is True
    assert registry.cancel("missing") is False
    asyncio.run(second.cancellation.wait())
    registry.release(first)
    next_lease = registry.acquire("chat-three")
    registry.release(next_lease)
    registry.release(second)
