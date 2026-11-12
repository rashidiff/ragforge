import asyncio

import pytest
from starlette.exceptions import HTTPException

from app.api.upload_limits import UploadBodyLimit


def test_declared_oversized_request_is_rejected_before_multipart_parser():
    async def scenario():
        called = False
        events = []
        async def app(scope, receive, send):
            nonlocal called
            called = True
        async def receive():
            raise AssertionError("Body must not be read")
        async def send(message):
            events.append(message)
        await UploadBodyLimit(app, 10)({"type": "http", "path": "/api/library/upload",
                                       "headers": [(b"content-length", b"11")]}, receive, send)
        assert not called
        assert events[0]["status"] == 413
    asyncio.run(scenario())


def test_chunked_request_has_running_byte_limit():
    async def scenario():
        async def receive():
            return {"type": "http.request", "body": b"123456", "more_body": True}
        async def send(message):
            pass
        async def app(scope, receive, send):
            await receive()
            await receive()
        with pytest.raises(HTTPException) as failure:
            await UploadBodyLimit(app, 10)({"type": "http", "path": "/api/library/upload", "headers": []}, receive, send)
        assert failure.value.status_code == 413
    asyncio.run(scenario())
