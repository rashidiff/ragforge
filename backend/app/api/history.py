"""Safe download of the coherent canonical raw-history snapshot."""
from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/backup")
def download_history_backup(request: Request):
    history = request.app.state.runtime.history
    with history.lock:
        history.recover()
        snapshot = history.path.read_bytes() if history.path.exists() else b""
    return Response(snapshot, media_type="application/x-ndjson",
                    headers={
                        "Content-Disposition": 'attachment; filename="chat-history.jsonl"',
                        "X-Content-Warning": "Contains verbatim conversation history; may include sensitive text",
                        "Cache-Control": "no-store",
                    })
