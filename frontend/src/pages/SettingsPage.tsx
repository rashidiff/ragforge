import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ShieldCheck } from "lucide-react";
import { api } from "../lib/api";
import type { AppSettings } from "../lib/contracts";
import { useLocale } from "../lib/i18n";

export function SettingsPage({ onBackup }: { onBackup?: () => void }) {
  const { t } = useLocale();
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [configuredProvider, setConfiguredProvider] = useState<AppSettings["provider"] | null>(null);
  const [key, setKey] = useState("");
  const [persistKey, setPersistKey] = useState(false);
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [connection, setConnection] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    api.settings(controller.signal).then((value) => { setSettings(value); setConfiguredProvider(value.provider); }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : t("Settings could not be loaded."));
    });
    return () => controller.abort();
  }, [t]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings || busy) return;
    setBusy(true); setError(""); setNotice(""); setConnection("");
    try {
      const updated = await api.updateSettings({
        provider: settings.provider, model: settings.model,
        compatible_base_url: settings.compatible_base_url,
        compatible_tools: settings.compatible_tools,
        compatible_usage: settings.compatible_usage,
        context_tokens: Number(settings.context_tokens), output_tokens: Number(settings.output_tokens),
        embedding_model: settings.embedding_model, embedding_revision: settings.embedding_revision,
        ocr_enabled: settings.ocr_enabled, ocr_languages: settings.ocr_languages,
        ...(key ? { api_key: key, ...(persistKey ? { persist_key: true } : {}) } : {}),
      });
      setSettings(updated); setConfiguredProvider(updated.provider); setKey(""); setPersistKey(false);
      setNotice(t("Settings saved. The API key was cleared from this form."));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Settings could not be saved."));
    } finally { setBusy(false); }
  }

  async function removeKey() {
    if (!settings || busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const updated = await api.updateSettings({ provider: settings.provider, remove_key: true });
      setSettings(updated); setConfiguredProvider(updated.provider); setKey(""); setNotice(t("The provider key was removed."));
    } catch (reason) { setError(reason instanceof Error ? reason.message : t("The key could not be removed.")); }
    finally { setBusy(false); }
  }

  async function testConnection() {
    if (!settings || testing) return;
    setTesting(true); setConnection(""); setError("");
    try {
      const result = await api.testProviderConnection();
      if (result.provider === "openai_compatible") {
        const capabilities = result.capabilities;
        setConnection(`${t("Connected to")} ${result.model} ${t("using OpenAI Responses.")} ${t("Library tools")}: ${t(capabilities.tools === true ? "available" : "unavailable")}; ${t("token usage")}: ${t(capabilities.usage === true ? "reported" : "unavailable")}.`);
      } else {
        setConnection(`${t("Connected to")} ${result.provider} ${t("using")} ${result.model}.`);
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The connection test failed."); }
    finally { setTesting(false); }
  }

  function change<K extends keyof AppSettings>(field: K, value: AppSettings[K]) {
    setSettings((current) => current ? { ...current, [field]: value } : current);
  }

  const selectedProviderHasKey = Boolean(settings?.has_key && settings.provider === configuredProvider);

  return <section className="info-page settings-page">
    <ShieldCheck size={32} strokeWidth={1.5} />
    <p className="eyebrow">{t("Settings & privacy")}</p><h1>{t("Your workspace stays local.")}</h1>
        <p>{t("PDFs and indexes stay on this computer. A selected remote provider receives only retrieved PDF snippets, your question, instructions and needed conversation context.")}</p>
    {error && <p className="error-banner" role="alert">{error}</p>}
    {notice && <p className="success-message" role="status">{notice}</p>}
    {connection && <p className="success-message" role="status">{connection}</p>}
    {!settings ? <div role="status" aria-busy="true"><p>{t("Loading settings…")}</p>
      <span className="skeleton skeleton-line" aria-hidden="true" /><span className="skeleton skeleton-line short" aria-hidden="true" /></div> : <form className="settings-form" onSubmit={save}>
      <div className="info-card settings-card">
        <h2>{t("Language model")}</h2>
        <label>{t("Provider")}<select value={settings.provider} onChange={(event) => change("provider", event.target.value as AppSettings["provider"])}>
          <option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="google">Google Gemini</option>
          <option value="openai_compatible">OpenAI-compatible endpoint</option>
        </select></label>
        {settings.provider === "openai_compatible" && <>
      <label>{t("Responses API base URL")}<input required type="url" value={settings.compatible_base_url ?? ""}
            onChange={(event) => change("compatible_base_url", event.target.value || null)}
            placeholder="https://provider.example/v1" /></label>
          <label className="checkbox-row"><input type="checkbox" checked={settings.compatible_tools}
            onChange={(event) => change("compatible_tools", event.target.checked)} />{t("Endpoint supports the configured Library tools")}</label>
          <label className="checkbox-row"><input type="checkbox" checked={settings.compatible_usage}
            onChange={(event) => change("compatible_usage", event.target.checked)} />{t("Endpoint reports token usage")}</label>
      <p className="field-note">{t("The connection test checks the OpenAI Responses protocol at this URL. Tool and usage capabilities are explicit endpoint settings; unsupported behavior remains an error or is reported unavailable.")}</p>
        </>}
        <label>{t("Model name")}<input required maxLength={200} value={settings.model} onChange={(event) => change("model", event.target.value)} /></label>
        <label>{t("API key")}<input type="password" autoComplete="new-password" value={key} onChange={(event) => setKey(event.target.value)} placeholder={selectedProviderHasKey ? t("A key is configured") : t("Enter a provider key")} /></label>
        <label className="checkbox-row"><input type="checkbox" checked={persistKey} onChange={(event) => setPersistKey(event.target.checked)} />{t("Save key in the OS credential vault")}</label>
        <p className="field-note">{t("Keys stay in session memory by default. The browser field clears after saving. A missing OS vault produces an error and never falls back to a file.")}</p>
        <div className="settings-actions">
          <button type="submit" disabled={busy}>{t(busy ? "Saving…" : "Save settings")}</button>
          <button type="button" onClick={testConnection} disabled={testing || busy || !selectedProviderHasKey || !settings.model.trim()}>{t(testing ? "Testing…" : "Test connection")}</button>
          {selectedProviderHasKey && <button type="button" onClick={removeKey} disabled={busy}>{t("Remove key")}</button>}
        </div>
        <p className="field-note">{t("Key status")}: {selectedProviderHasKey ? `${t("configured")} (${settings.persistence_mode})` : t("not configured for this provider")}. {t("The key is never returned by the API.")}</p>
      </div>
      <div className="info-card settings-card">
        <h2>{t("Local document processing")}</h2>
        <label>{t("Embedding model")}<input value={settings.embedding_model} onChange={(event) => change("embedding_model", event.target.value)} /></label>
        <label>{t("Embedding revision")}<input value={settings.embedding_revision ?? ""} onChange={(event) => change("embedding_revision", event.target.value || null)} /></label>
        <p className="field-note">{t("Changing the embedding model requires a full local Library rebuild. Initial model and package downloads may need internet access.")}</p>
        <label className="checkbox-row"><input type="checkbox" checked={settings.ocr_enabled} onChange={(event) => change("ocr_enabled", event.target.checked)} />{t("Enable optional local OCR")}</label>
        <p className="field-note">{t("OCR runs locally with Tesseract. Missing Tesseract or language packs produces a warning, and scans that remain unreadable are not marked searchable.")}</p>
        <label>{t("OCR languages")}<input value={settings.ocr_languages} onChange={(event) => change("ocr_languages", event.target.value)} /></label>
        <label>{t("Model context tokens")}<input type="number" min={1024} value={settings.context_tokens} onChange={(event) => change("context_tokens", Number(event.target.value))} /></label>
        <label>{t("Maximum output tokens")}<input type="number" min={1} value={settings.output_tokens} onChange={(event) => change("output_tokens", Number(event.target.value))} /></label>
      </div>
    </form>}
    <div className="info-card"><h2>{t("Local data and remote generation")}</h2>
        <p>{t("Conversation history, activity logs, PDFs, indexes and memory are stored locally. Local history can contain sensitive text; files are not encrypted by the application.")}</p>
      <p>{t("There is no account, analytics, or telemetry. Provider calls and initial model/package downloads require internet access.")}</p>
      <button type="button" onClick={onBackup}>{t("Download raw history backup")}</button>
    </div>
  </section>;
}
