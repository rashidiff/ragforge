"""Validated, non-secret configuration. Importing this module creates no files."""
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAG_", env_file=PROJECT_ROOT / ".env", extra="ignore"
    )

    host: Literal["127.0.0.1"] = "127.0.0.1"
    port: int = Field(default=8000, ge=1024, le=65535)
    data_dir: Path = PROJECT_ROOT / "data"
    prompts_dir: Path = PROJECT_ROOT / "prompts"
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"
    dev_origin: str = "http://127.0.0.1:5173"
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_revision: str | None = None
    chunk_tokens: int = Field(default=500, ge=32, le=8192)
    chunk_overlap: int = Field(default=80, ge=0)
    ocr_enabled: bool = False
    ocr_languages: str = "eng+fra+fas"
    reranker_model: str | None = None
    retrieval_candidates: int = Field(default=20, ge=1, le=100)
    retrieval_snippets: int = Field(default=6, ge=1, le=20)
    retrieval_tokens: int = Field(default=4000, ge=128)
    summary_tokens: int = Field(default=700, ge=128)
    context_tokens: int = Field(default=16000, ge=1024)
    output_tokens: int = Field(default=2000, ge=1)
    max_tool_rounds: int = Field(default=2, ge=0, le=2)
    request_timeout_seconds: float = Field(default=90, gt=0)
    max_concurrent_requests: int = Field(default=4, ge=1, le=32)
    debug_chunks: bool = False

    @field_validator("data_dir", "prompts_dir", "frontend_dist", mode="before")
    @classmethod
    def resolve_paths(cls, value: str | Path) -> Path:
        path = Path(value).expanduser()
        return (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()

    @field_validator("embedding_model", "ocr_languages")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value cannot be empty")
        return value

    @field_validator("dev_origin")
    @classmethod
    def local_origin(cls, value: str) -> str:
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
                or parsed.username or parsed.password or parsed.path
                or parsed.query or parsed.fragment):
            raise ValueError("Development origin must be an HTTP 127.0.0.1 origin without a path")
        if parsed.port is None:
            raise ValueError("Development origin must include its port")
        return value

    @model_validator(mode="after")
    def budgets(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_tokens:
            raise ValueError("Chunk overlap must be smaller than chunk size")
        if self.output_tokens + self.summary_tokens >= self.context_tokens:
            raise ValueError("Context must leave room beyond summary and output budgets")
        return self

    def initialize_directories(self) -> None:
        for relative in ("", "library/pdfs", "index", "state"):
            (self.data_dir / relative).mkdir(parents=True, exist_ok=True)
