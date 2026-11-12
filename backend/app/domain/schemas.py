"""Public API models. Credentials never belong in response or history schemas."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatCreate(Contract):
    title: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def valid_title(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip() if value is not None else None


class ChatRename(ChatCreate):
    title: str = Field(min_length=1, max_length=200)


class Chat(Contract):
    chat_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    gc_pending: bool = False


class ChatList(Contract):
    chats: list[Chat]


class Message(Contract):
    event_id: UUID
    chat_id: UUID
    message_id: UUID
    request_id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    completed: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class MessageList(Contract):
    messages: list[Message]


class MessageSubmission(Contract):
    content: str | None = None
    client_message_id: UUID | None = None
    retry_of_request_id: UUID | None = None

    @model_validator(mode="after")
    def exclusive_attempt(self) -> "MessageSubmission":
        if self.retry_of_request_id:
            if self.content is not None or self.client_message_id is not None:
                raise ValueError("Retry cannot include new content or a client message ID")
        elif self.content is None or not self.content.strip() or self.client_message_id is None:
            raise ValueError("A new attempt requires nonblank content and a client message ID")
        return self


class Health(Contract):
    status: Literal["ok", "degraded"]
    version: str
    storage_ready: bool
    index_ready: bool
    warnings: list[str] = Field(default_factory=list)


class ErrorDetail(Contract):
    code: str
    message: str
    retryable: bool = False
    request_id: UUID | None = None
    details: list[dict[str, str]] | None = None


class ErrorResponse(Contract):
    error: ErrorDetail


class Document(Contract):
    document_id: UUID
    original_name: str
    title: str
    sha256: str
    size_bytes: int = Field(ge=0)
    page_count: int = Field(ge=1)
    imported_at: datetime
    status: str
    warnings: list[str]
    index_version: str | None
    error: str | None


class DocumentList(Contract):
    documents: list[Document]


class IndexJob(Contract):
    job_id: UUID
    kind: str
    document_id: UUID | None
    stage: str
    processed: int
    total: int | None
    started_at: datetime
    finished_at: datetime | None
    error: str | None


class UploadAccepted(Contract):
    document: Document
    job_id: UUID


class DeletionAccepted(Contract):
    job_id: UUID
    status: Literal["deleting"]


class IndexStatus(Contract):
    index_version: str | None
    ready: bool
    jobs: list[IndexJob]
    warnings: list[str]
    rebuild_required: bool


class AppSettings(Contract):
    provider: Literal["openai", "anthropic", "google", "openai_compatible"]
    model: str
    context_tokens: int = Field(ge=1024)
    output_tokens: int = Field(ge=1)
    embedding_model: str
    embedding_revision: str | None
    ocr_enabled: bool
    ocr_languages: str
    compatible_base_url: str | None = None
    compatible_tools: bool = False
    compatible_usage: bool = False
    has_key: bool
    persistence_mode: Literal["session", "keyring"]

    @field_validator("embedding_model")
    @classmethod
    def required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value cannot be blank")
        return value.strip()

    @model_validator(mode="after")
    def model_budget(self) -> "AppSettings":
        if self.output_tokens >= self.context_tokens:
            raise ValueError("Output budget must be smaller than the context window")
        if self.provider == "openai_compatible" and not self.compatible_base_url:
            raise ValueError("Configure the OpenAI-compatible endpoint before selecting it")
        return self


class SettingsUpdate(Contract):
    provider: Literal["openai", "anthropic", "google", "openai_compatible"] | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)
    context_tokens: int | None = Field(default=None, ge=1024)
    output_tokens: int | None = Field(default=None, ge=1)
    embedding_model: str | None = Field(default=None, min_length=1, max_length=300)
    embedding_revision: str | None = Field(default=None, max_length=200)
    ocr_enabled: bool | None = None
    ocr_languages: str | None = Field(default=None, min_length=1, max_length=100)
    compatible_base_url: str | None = Field(default=None, max_length=2048)
    compatible_tools: bool | None = None
    compatible_usage: bool | None = None
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)
    persist_key: bool = False
    remove_key: bool = False

    @field_validator("model", "embedding_model")
    @classmethod
    def nonblank_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("Value cannot be blank")
        return value.strip()

    @field_validator("compatible_base_url")
    @classmethod
    def safe_compatible_endpoint(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        from urllib.parse import urlsplit

        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if any(character.isspace() for character in normalized) or "\\" in normalized:
            raise ValueError("Compatible endpoint URL contains invalid characters")
        local_http = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if (
            parsed.scheme != "https" and not (parsed.scheme == "http" and local_http)
        ) or not parsed.hostname:
            raise ValueError(
                "Compatible endpoint must use HTTPS (HTTP is allowed only for loopback)"
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Compatible endpoint cannot contain credentials, query or fragment")
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("Compatible endpoint has an invalid port") from exc
        return normalized

    @model_validator(mode="after")
    def credential_operations(self) -> "SettingsUpdate":
        if self.remove_key and self.api_key is not None:
            raise ValueError("Set or remove a key in separate operations")
        if self.persist_key and self.api_key is None:
            raise ValueError("Keyring opt-in requires a key in this request")
        return self


class ConnectionTestResult(Contract):
    provider: Literal["openai", "anthropic", "google", "openai_compatible"]
    model: str
    connected: bool
    capabilities: dict[str, Any]


class Citation(Contract):
    chunk_id: str
    document_id: UUID
    filename: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    url: str


class SourceDetail(Citation):
    text: str
    index_version: str
    available: bool


class StreamStatus(Contract):
    stage: str
    label: str
    request_id: UUID | None = None


class RetrievedSource(Contract):
    chunk_id: str
    document_id: UUID
    page: int = Field(ge=1)
    page_end: int = Field(ge=1)
    filename: str
    score: float | None = None


class RetrievalEvent(Contract):
    request_id: UUID
    sources: list[RetrievedSource]


class TokenEvent(Contract):
    request_id: UUID
    delta: str


class UsageEvent(Contract):
    request_id: UUID
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class DoneEvent(Contract):
    request_id: UUID
    message_id: UUID
    complete: Literal[True]
    duration_ms: int = Field(ge=0)


class StreamCitationEvent(Citation):
    request_id: UUID


class CompactionStatus(Contract):
    chat_id: UUID
    state: Literal["idle", "queued", "running", "completed", "failed"]
    summary_revision: int = Field(ge=0)
    compacted_message_count: int = Field(ge=0)
    pending_message_count: int = Field(ge=0)
    request_id: UUID | None = None
    provider: Literal["openai", "anthropic", "google", "openai_compatible"] | None = None
    model: str | None = None
    batch_count: int = Field(ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    usage: dict[str, int | None] | None = None
    error_category: str | None = None
    retryable: bool
