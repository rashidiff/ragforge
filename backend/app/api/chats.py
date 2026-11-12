from uuid import UUID
import json
import re

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import Response as DownloadResponse

from app.domain.schemas import Chat, ChatCreate, ChatList, ChatRename, CompactionStatus, MessageList
from app.services.compaction import CompactionRetryUnavailable

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("", response_model=ChatList)
def list_chats(request: Request):
    return {"chats": request.app.state.runtime.chats.list()}


@router.post("", response_model=Chat, status_code=201)
def create_chat(body: ChatCreate, request: Request):
    runtime = request.app.state.runtime
    chat = runtime.chats.create(body.title)
    runtime.activity.emit("chat_created", chat_id=chat["chat_id"])
    return chat


@router.patch("/{chat_id}", response_model=Chat)
def rename_chat(chat_id: UUID, body: ChatRename, request: Request):
    runtime = request.app.state.runtime
    chat = runtime.chats.rename(str(chat_id), body.title)
    runtime.activity.emit("chat_renamed", chat_id=str(chat_id))
    return chat


@router.delete("/{chat_id}", status_code=204)
def delete_chat(chat_id: UUID, request: Request):
    runtime = request.app.state.runtime
    runtime.chats.delete(str(chat_id))
    runtime.activity.emit("chat_deleted", chat_id=str(chat_id))
    return Response(status_code=204)


@router.get("/{chat_id}/messages", response_model=MessageList)
def messages(chat_id: UUID, request: Request):
    return {"messages": request.app.state.runtime.chats.messages(str(chat_id))}


@router.get("/{chat_id}/export")
def export_chat(chat_id: UUID, request: Request, format: str = Query(pattern="^(markdown|json)$")):
    runtime = request.app.state.runtime
    chat = runtime.chats.get(str(chat_id))
    messages = runtime.chats.messages(str(chat_id))
    if format == "json":
        payload = {
            "chat": {key: chat[key] for key in ("chat_id", "title", "created_at", "updated_at")},
            "messages": [{key: message[key] for key in (
                "event_id", "chat_id", "message_id", "request_id", "role", "content",
                "created_at", "completed", "metadata")} for message in messages],
        }
        body = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
        media_type, suffix = "application/json; charset=utf-8", "json"
    else:
        # Fence every message as literal text. Select a fence longer than any
        # backtick run in the content so user text cannot terminate the block.
        title_fence = "`" * max(3, max((len(run) for run in re.findall(r"`+", chat["title"])), default=0) + 1)
        parts = ["# Chat export", "", "Title:", title_fence, chat["title"], title_fence,
                 "", f"Chat ID: {chat['chat_id']}", ""]
        for item in messages:
            status = "" if item["completed"] else " · incomplete"
            parts.extend((f"## {item['role'].title()} · {item['created_at']}{status}", ""))
            longest = max((len(run) for run in re.findall(r"`+", item["content"])), default=0)
            fence = "`" * max(3, longest + 1)
            parts.extend((fence, item["content"], fence, ""))
        body = "\n".join(parts)
        media_type, suffix = "text/markdown; charset=utf-8", "md"
    return DownloadResponse(body, media_type=media_type,
                            headers={"Content-Disposition": f'attachment; filename="chat-{chat_id}.{suffix}"'})


@router.get("/{chat_id}/compaction", response_model=CompactionStatus)
def compaction_status(chat_id: UUID, request: Request):
    runtime = request.app.state.runtime
    return runtime.compactor.status(str(chat_id))


@router.post("/{chat_id}/compaction/retry", response_model=CompactionStatus, status_code=202)
async def retry_compaction(chat_id: UUID, request: Request):
    runtime = request.app.state.runtime
    try:
        return runtime.compactor.retry(str(chat_id))
    except CompactionRetryUnavailable as exc:
        raise HTTPException(status_code=409, detail="No failed eligible compaction batch is available to retry") from exc
