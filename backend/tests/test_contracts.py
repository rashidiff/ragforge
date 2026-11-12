from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.schemas import ChatCreate, MessageSubmission
from app.main import create_app


def generator():
    root = Path(__file__).resolve().parents[2]
    specification = spec_from_file_location("generate_contracts", root / "scripts/generate_contracts.py")
    module = module_from_spec(specification)
    specification.loader.exec_module(module)
    return root, module


def test_checked_in_types_match_domain_contract():
    root, module = generator()
    source = (root / "backend/app/domain/schemas.py").read_text(encoding="utf-8")
    assert module.render(source) == (root / "frontend/src/lib/contracts.ts").read_text(encoding="utf-8")


def test_drift_is_detectable_when_field_changes():
    root, module = generator()
    source = (root / "backend/app/domain/schemas.py").read_text(encoding="utf-8")
    changed = source.replace("    version: str", "    version: int")
    assert module.render(changed) != (root / "frontend/src/lib/contracts.ts").read_text(encoding="utf-8")


def test_openapi_exposes_typed_request_and_responses_without_startup():
    contract = create_app().openapi()
    assert "ChatCreate" in contract["components"]["schemas"]
    assert "201" in contract["paths"]["/api/chats"]["post"]["responses"]
    assert "MessageList" in contract["components"]["schemas"]


def test_submission_preserves_content_and_rejects_ambiguous_retry():
    text = "  فارسی\nFrench\tEnglish  "
    assert MessageSubmission(content=text, client_message_id=uuid4()).content == text
    with pytest.raises(ValidationError):
        MessageSubmission(content=text, client_message_id=uuid4(), retry_of_request_id=uuid4())
    with pytest.raises(ValidationError):
        MessageSubmission(content=" \n", client_message_id=uuid4())
    with pytest.raises(ValidationError):
        ChatCreate(title="\t")
