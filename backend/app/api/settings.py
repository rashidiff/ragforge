"""Provider configuration and write-only credential routes."""

from fastapi import APIRouter, HTTPException, Request

from app.domain.schemas import AppSettings, ConnectionTestResult, SettingsUpdate
from app.llm.anthropic import AnthropicAdapter
from app.llm.base import Capabilities, ProviderError
from app.llm.gemini import GeminiAdapter
from app.llm.openai import OpenAIAdapter

router = APIRouter(prefix="/api/settings", tags=["settings"])
_ADAPTERS = {"openai": OpenAIAdapter, "anthropic": AnthropicAdapter, "google": GeminiAdapter}


def _adapter(provider: str, values: dict, timeout: float):
    if provider == "openai_compatible":
        endpoint = values.get("compatible_base_url")
        if not endpoint:
            raise HTTPException(422, "Configure a valid OpenAI-compatible endpoint")
        return OpenAIAdapter(base_url=endpoint, timeout=timeout)
    return _ADAPTERS[provider](timeout=timeout)


def public_settings(runtime) -> AppSettings:
    values = runtime.app_settings.read()
    provider = values["provider"]
    return AppSettings(
        **values,
        has_key=runtime.credentials.has_key(provider),
        persistence_mode=runtime.credentials.persistence_mode(provider),
    )


@router.get("", response_model=AppSettings)
def read_settings(request: Request):
    return public_settings(request.app.state.runtime)


@router.put("", response_model=AppSettings)
def update_settings(body: SettingsUpdate, request: Request):
    runtime = request.app.state.runtime
    values = runtime.app_settings.read()
    provided = body.model_fields_set
    changes = {
        key: getattr(body, key)
        for key in provided
        if key not in {"api_key", "persist_key", "remove_key"}
        and (getattr(body, key) is not None or key == "embedding_revision")
    }
    combined = {**values, **changes}
    if combined["provider"] == "openai_compatible" and not combined.get("compatible_base_url"):
        raise HTTPException(422, "Configure an OpenAI-compatible endpoint before selecting it")
    if (
        combined["output_tokens"] >= combined["context_tokens"]
        or combined["output_tokens"] + runtime.settings.summary_tokens >= combined["context_tokens"]
    ):
        raise HTTPException(422, "Invalid model budget")

    if changes:
        runtime.app_settings.update(changes)
        for key, value in changes.items():
            if hasattr(runtime.settings, key):
                setattr(runtime.settings, key, value)
        runtime.index.settings = runtime.settings

    provider = combined["provider"]
    if body.remove_key:
        runtime.credentials.remove(provider)
    elif body.api_key is not None:
        runtime.credentials.set(provider, body.api_key, persist=body.persist_key)
    runtime.activity.emit(
        "settings_updated",
        provider=provider,
        changed_fields=sorted(changes),
        key_operation=(
            "removed" if body.remove_key else "saved" if body.api_key is not None else "unchanged"
        ),
    )
    return public_settings(runtime)


@router.post("/test-connection", response_model=ConnectionTestResult)
async def test_connection(request: Request):
    runtime = request.app.state.runtime
    values = runtime.app_settings.read()
    provider, model = values["provider"], values["model"]
    if not model.strip():
        raise HTTPException(422, "Enter a model name before testing the connection")
    key = runtime.credentials.get(provider)
    if not key:
        raise ProviderError("missing_key", "Add a provider API key before testing the connection")
    compatible = provider == "openai_compatible"
    capabilities = Capabilities(
        context_tokens=values["context_tokens"],
        max_output_tokens=values["output_tokens"],
        tools=values["compatible_tools"] if compatible else False,
        usage=values["compatible_usage"] if compatible else False,
    )
    adapter = _adapter(provider, values, runtime.settings.request_timeout_seconds)
    runtime.activity.emit("provider_test_started", provider=provider, model=model)
    try:
        try:
            result = await adapter.test_connection(model, key, capabilities)
        except ProviderError as exc:
            # An endpoint can support the base Responses protocol but reject optional
            # tools; negotiate that capability separately and keep deterministic RAG.
            if not compatible or not values["compatible_tools"] or exc.status_code != 400:
                raise
            result = await adapter.test_connection(
                model,
                key,
                Capabilities(
                    context_tokens=values["context_tokens"],
                    max_output_tokens=values["output_tokens"],
                    tools=False,
                    usage=values["compatible_usage"],
                ),
            )
            result["capabilities"]["tools"] = False
            result["capabilities"]["tool_schema_accepted"] = False
        if compatible:
            result["provider"] = "openai_compatible"
            result["capabilities"].update(
                protocol="openai-responses",
                tools_configured=bool(result["capabilities"].get("tools")),
            )
            runtime.app_settings.update(
                {
                    "compatible_tools": bool(result["capabilities"].get("tools")),
                    "compatible_usage": bool(
                        values["compatible_usage"] and result["capabilities"].get("usage")
                    ),
                }
            )
        runtime.activity.emit(
            "provider_test_completed", provider=provider, model=model, status="success"
        )
        return result
    except ProviderError as exc:
        runtime.activity.emit(
            "provider_test_completed",
            provider=provider,
            model=model,
            status="error",
            error_category=exc.category,
            status_code=exc.status_code,
        )
        raise
