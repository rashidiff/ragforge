from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.domain.schemas import Health, IndexJob, IndexStatus
from app.llm.base import ProviderError

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/health", response_model=Health)
def health(request: Request):
    runtime = request.app.state.runtime
    runtime.chats.list()  # Surface corrupt/unreadable state rather than report healthy storage.
    index_status = runtime.index.status()
    warnings = list(index_status["warnings"])
    settings = runtime.app_settings.read()
    if not settings["model"].strip():
        warnings.append("Choose a language model in Settings before asking questions with PDF evidence.")
    else:
        try:
            if not runtime.credentials.has_key(settings["provider"]):
                warnings.append("Add a provider API key in Settings to generate answers from retrieved PDFs.")
        except ProviderError:
            warnings.append("The opted-in OS credential vault is unavailable.")
    return Health(status="ok" if index_status["ready"] else "degraded", version="0.1.0", storage_ready=True,
                  index_ready=index_status["ready"], warnings=warnings)


@router.get("/index/status", response_model=IndexStatus)
def index_status(request: Request, job_id: UUID | None = None):
    try:
        return request.app.state.runtime.index.status(str(job_id) if job_id else None)
    except KeyError as exc:
        raise HTTPException(404) from exc


@router.post("/index/rebuild", response_model=IndexJob, status_code=202)
def rebuild_index(request: Request):
    return request.app.state.runtime.index.submit("rebuild")["job"]
