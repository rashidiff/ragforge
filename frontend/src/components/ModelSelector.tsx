import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ChevronDown } from "lucide-react";
import { api } from "../lib/api";
import type { ModelCatalog } from "../lib/contracts";
import { useLocale } from "../lib/i18n";

const providers = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google Gemini",
  openai_compatible: "OpenAI-compatible",
};

export function ModelSelector({
  disabled,
  onPendingChange,
}: {
  disabled: boolean;
  onPendingChange: (pending: boolean) => void;
}) {
  const { t } = useLocale();
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [custom, setCustom] = useState(false);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    api
      .modelCatalog(controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setCatalog(value);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error ? reason.message : "Could not load models.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);

  async function choose(model: string) {
    if (!catalog || disabled || saving || !model.trim()) return;
    setSaving(true);
    setError("");
    onPendingChange(true);
    try {
      const updated = await api.selectModel({
        provider: catalog.provider,
        model: model.trim(),
      });
      setCatalog((current) =>
        current
          ? {
              ...current,
              current_model: updated.model,
              models: current.models.some(
                (option) => option.id === updated.model,
              )
                ? current.models
                : [
                    ...current.models,
                    { id: updated.model, label: updated.model },
                  ],
            }
          : current,
      );
      setCustom(false);
      setDraft("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not select model.",
      );
    } finally {
      setSaving(false);
      onPendingChange(false);
    }
  }

  function submitCustom(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void choose(draft);
  }

  return (
    <div className="chat-model-picker" aria-busy={loading || saving}>
      <label
        className="chat-model-control"
        title={t("Model access depends on your provider account.")}
      >
        <span className="model-provider">
          {catalog ? providers[catalog.provider] : "LLM"}
        </span>
        <select
          aria-label={t("LLM model")}
          disabled={disabled || loading || saving || !catalog}
          value={custom ? "__custom__" : (catalog?.current_model ?? "")}
          onChange={(event) => {
            if (event.target.value === "__custom__") {
              setCustom(true);
              return;
            }
            setCustom(false);
            void choose(event.target.value);
          }}
        >
          <option value="" disabled>
            {t(loading ? "Loading models…" : "Choose a model")}
          </option>
          {catalog?.models.map((model) => (
            <option key={model.id} value={model.id}>
              {model.label}
            </option>
          ))}
          <option value="__custom__">{t("Other model…")}</option>
        </select>
        <ChevronDown size={15} aria-hidden="true" />
      </label>
      {(custom || error) && (
        <div className="chat-model-popover">
          {custom && (
            <form onSubmit={submitCustom}>
              <label>
                {t("Custom model ID")}
                <input
                  autoFocus
                  maxLength={200}
                  required
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  disabled={disabled || saving}
                />
              </label>
              <p>{t("Model access depends on your provider account.")}</p>
              <button
                type="submit"
                disabled={disabled || saving || !draft.trim()}
              >
                {t("Use model")}
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => setCustom(false)}
              >
                {t("Cancel")}
              </button>
            </form>
          )}
          {error && (
            <div role="alert">
              <p>{error}</p>
              <button
                type="button"
                disabled={disabled || saving}
                onClick={() => {
                  setError("");
                  setLoading(true);
                  setRevision((value) => value + 1);
                }}
              >
                {t("Reload models")}
              </button>
            </div>
          )}
          {catalog?.source_url && (
            <a href={catalog.source_url} target="_blank" rel="noreferrer">
              {t("Model documentation")}
            </a>
          )}
        </div>
      )}
    </div>
  );
}
