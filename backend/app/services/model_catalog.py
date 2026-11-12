"""Reviewed text-model suggestions, not a claim of account-specific entitlement."""

from typing import Literal

from app.domain.schemas import ModelCatalog, ModelOption

REVIEWED_AT = "2026-11-12"
CATALOG: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {
    "openai": (
        "https://developers.openai.com/api/docs/models",
        (
            ("gpt-4.1", "GPT-4.1"),
            ("gpt-4.1-mini", "GPT-4.1 mini"),
            ("gpt-4.1-nano", "GPT-4.1 nano"),
            ("gpt-6.1-sol", "GPT-6.1 Sol"),
            ("gpt-6.1-terra", "GPT-6.1 Terra"),
            ("gpt-6-astra", "GPT-6 Astra"),
            ("gpt-6-luna", "GPT-6 Luna"),
        ),
    ),
    "anthropic": (
        "https://platform.claude.com/docs/en/models/overview",
        (
            ("claude-sonnet-5-5", "Claude Sonnet 5.5"),
            ("claude-opus-5-5", "Claude Opus 5.5"),
            ("claude-haiku-5-5", "Claude Haiku 5.5"),
            ("claude-fable-5-2", "Claude Fable 5.2"),
        ),
    ),
    "google": (
        "https://ai.google.dev/gemini-api/docs/models",
        (
            ("gemini-3.8-flash", "Gemini 3.8 Flash"),
            ("gemini-3.6-flash", "Gemini 3.6 Flash"),
            ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite"),
            ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite"),
            ("gemini-4-carbon", "Gemini 4 Carbon"),
            ("gemini-4-argon", "Gemini 4 Argon"),
        ),
    ),
}


def default_model(provider: str) -> str:
    entry = CATALOG.get(provider)
    return entry[1][0][0] if entry else ""


def model_catalog(
    provider: Literal["openai", "anthropic", "google", "openai_compatible"], current_model: str
) -> ModelCatalog:
    entry = CATALOG.get(provider)
    models = (
        [ModelOption(id=identifier, label=label) for identifier, label in entry[1]] if entry else []
    )
    if current_model and not any(model.id == current_model for model in models):
        models.append(ModelOption(id=current_model, label=f"{current_model} (saved)"))
    return ModelCatalog(
        provider=provider,
        current_model=current_model,
        default_model=default_model(provider),
        models=models,
        source_url=entry[0] if entry else None,
        reviewed_at=REVIEWED_AT,
    )
