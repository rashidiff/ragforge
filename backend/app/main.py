"""Local API and static frontend hosting. Start with python -m app."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import chats, history, library, settings as settings_api, status, streaming
from app.api.upload_limits import UploadBodyLimit
from app.config import Settings
from app.domain.schemas import ErrorResponse
from app.llm.base import ProviderError
from app.services.chat_store import ChatNotFoundError
from app.services.history_store import HistoryCorruptionError
from app.services.prompt_loader import PromptLoader
from app.services.runtime import Runtime
from app.services.state_store import StateCorruptionError
from app.services.index_manager import IndexConflictError, IndexUnavailableError
from app.services.pdf_ingestion import PdfIntakeError
from app.services.generation_registry import GenerationConflictError


def error(status_code: int, code: str, message: str, *, retryable=False, details=None):
    return JSONResponse(status_code=status_code, content={"error": {
        "code": code, "message": message, "retryable": retryable, "details": details,
    }})


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        prompts = PromptLoader(config.prompts_dir)
        prompts.validate()
        runtime = Runtime(config, prompts)
        application.state.runtime = runtime
        application.state.prompts = prompts
        try:
            yield
        finally:
            runtime.close()

    application = FastAPI(title="Local RAG Chat", version="0.1.0", lifespan=lifespan,
                          responses={422: {"model": ErrorResponse},
                                     404: {"model": ErrorResponse},
                                     500: {"model": ErrorResponse}})
    origins = {f"http://127.0.0.1:{config.port}", config.dev_origin}
    application.add_middleware(CORSMiddleware, allow_origins=sorted(origins),
                               allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                               allow_headers=["Content-Type"], allow_credentials=False)
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    application.add_middleware(UploadBodyLimit, max_bytes=config.max_upload_bytes + 64 * 1024)

    @application.middleware("http")
    async def origin_guard(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return error(403, "origin_rejected", "This origin is not allowed")
        return await call_next(request)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Pydantic's input and ctx can contain keys or arbitrary user content: never echo them.
        details = [{"field": ".".join(map(str, item["loc"])), "code": item["type"]}
                   for item in exc.errors()]
        return error(422, "validation_error", "Invalid request fields", details=details)

    @application.exception_handler(ChatNotFoundError)
    async def not_found(request: Request, exc: ChatNotFoundError):
        return error(404, "chat_not_found", "Chat not found")

    @application.exception_handler(PdfIntakeError)
    async def pdf_error(request: Request, exc: PdfIntakeError):
        return error(exc.status, exc.code, str(exc), details=[{"document_id": exc.document_id}] if exc.document_id else None)

    @application.exception_handler(IndexConflictError)
    async def index_conflict(request: Request, exc: IndexConflictError):
        return error(409, "index_busy", str(exc), retryable=True)

    @application.exception_handler(IndexUnavailableError)
    async def index_unavailable(request: Request, exc: IndexUnavailableError):
        return error(503, "index_unavailable", str(exc), retryable=True)

    @application.exception_handler(ProviderError)
    async def provider_error(request: Request, exc: ProviderError):
        status_code = (401 if exc.status_code == 401 else
                       429 if exc.status_code == 429 else
                       502 if exc.status_code and exc.status_code >= 500 else
                       503 if exc.category in {"network_error", "timeout", "credential_vault_unavailable", "dependency_missing"} else
                       422 if exc.category in {"invalid_model", "invalid_provider", "unsupported_tools"} else 400)
        return error(status_code, exc.category, str(exc), retryable=exc.retryable)

    @application.exception_handler(GenerationConflictError)
    async def generation_conflict(request: Request, exc: GenerationConflictError):
        return error(exc.status_code, "generation_conflict", str(exc), retryable=True)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error(exc.status_code, "http_error", "Requested resource is unavailable")

    async def storage_error(request: Request, exc: Exception):
        return error(500, "storage_error",
                     "Local storage could not be read or saved. Check disk access and restore a backup if needed.",
                     retryable=True)

    for exception in (OSError, StateCorruptionError, HistoryCorruptionError):
        application.add_exception_handler(exception, storage_error)

    application.include_router(chats.router)
    application.include_router(history.router)
    application.include_router(library.router)
    application.include_router(status.router)
    application.include_router(settings_api.router)
    application.include_router(streaming.router)

    @application.get("/{asset_path:path}", include_in_schema=False)
    def frontend(asset_path: str):
        if asset_path == "api" or asset_path.startswith("api/"):
            return error(404, "route_not_found", "API route not found")
        root = config.frontend_dist.resolve()
        candidate = (root / asset_path).resolve()
        if not candidate.is_relative_to(root):
            return error(404, "asset_not_found", "Asset not found")
        if candidate.is_file():
            return FileResponse(candidate)
        if asset_path.startswith("assets/"):
            return error(404, "asset_not_found", "Asset not found")
        index = root / "index.html"
        if index.is_file() and index.resolve().is_relative_to(root):
            return FileResponse(index)
        return error(503, "frontend_not_built",
                     "Frontend assets are not available. Use the Vite development server or build the frontend.")

    return application
