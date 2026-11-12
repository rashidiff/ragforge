"""Bound raw multipart traffic before it can grow an unbounded spool file."""
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class UploadBodyLimit:
    def __init__(self, app, max_bytes: int):
        self.app, self.limit = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != "/api/library/upload":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length is not None:
            try:
                declared = int(length)
                if declared < 0:
                    raise ValueError()
            except ValueError:
                return await JSONResponse({"error": {"code": "invalid_length", "message": "Invalid request length", "retryable": False}}, status_code=400)(scope, receive, send)
            if declared > self.limit:
                return await JSONResponse({"error": {"code": "upload_too_large", "message": "Upload exceeds the configured size limit", "retryable": False}}, status_code=413)(scope, receive, send)
        received = 0
        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.limit:
                    raise HTTPException(413, "Upload exceeds the configured size limit")
            return message
        return await self.app(scope, bounded_receive, send)
