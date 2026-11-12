import { useState } from "react";
import { useEffect, useLayoutEffect, useRef } from "react";
import { BookOpen, MessageSquare } from "lucide-react";
import type { Chat, Citation, CompactionStatus, Message } from "../lib/contracts";
import { SourceDrawer } from "../components/SourceDrawer";
import { MarkdownMessage } from "../components/MarkdownMessage";
import { useLocale } from "../lib/i18n";
import { containsPotentialSecret } from "../lib/secrets";

interface Props {
  chat: Chat | undefined;
  messages: Message[];
  loading: boolean;
  onLibrary: () => void;
  onSend?: (content: string) => void;
  onStop?: () => void;
  onRetry?: (requestId: string) => void;
  streaming?: boolean;
  stage?: string;
  streamError?: string;
  liveAssistantId?: string;
  onDismissError?: () => void;
  compaction?: CompactionStatus | null;
  onRetryCompaction?: () => void;
}

export function ChatPage({ chat, messages, loading, onLibrary, onSend, onStop, onRetry,
  streaming = false, stage = "", streamError = "", liveAssistantId, onDismissError,
  compaction = null, onRetryCompaction }: Props) {
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [draft, setDraft] = useState("");
  const [copiedId, setCopiedId] = useState("");
  const [copyError, setCopyError] = useState("");
  const { t } = useLocale();
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const shouldFollowMessages = useRef(true);
  const retryUser = [...messages].reverse().find((message) => message.role === "user");
  const hasCompletedAnswer = retryUser && messages.some((message) => message.role === "assistant" &&
    message.request_id === retryUser.request_id && message.completed);
  const canRetry = !streaming && Boolean(retryUser) && !hasCompletedAnswer;

  useEffect(() => {
    const element = composerRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 180)}px`;
  }, [draft]);

  useEffect(() => {
    const updateFollowPreference = () => {
      const scrolling = document.scrollingElement;
      if (!scrolling) return;
      shouldFollowMessages.current = scrolling.scrollTop + scrolling.clientHeight >= scrolling.scrollHeight - 120;
    };
    window.addEventListener("scroll", updateFollowPreference, { passive: true });
    updateFollowPreference();
    return () => window.removeEventListener("scroll", updateFollowPreference);
  }, []);

  useLayoutEffect(() => {
    const scrolling = document.scrollingElement;
    if (shouldFollowMessages.current && scrolling) window.scrollTo(0, scrolling.scrollHeight);
  }, [messages]);

  function send() {
    if (!draft.trim() || streaming) return;
    onSend?.(draft);
    setDraft("");
  }

  return <section className="conversation" aria-label={t("Conversation")}>
    {loading ? <div role="status" className="loading-message" aria-busy="true"><p>{t("Loading conversation…")}</p>
      <span className="skeleton skeleton-line" aria-hidden="true" /><span className="skeleton skeleton-line short" aria-hidden="true" /></div> : messages.length > 0 ?
      <ol className="messages" aria-live="polite">{messages.map((message) => <li key={message.message_id} className={`message ${message.role}`}>
        <span className="message-role">{t(message.role === "user" ? "You" : "Assistant")}</span>
        <div dir="auto" className="message-content"><MarkdownMessage content={message.content}
          citations={citationsFor(message)} onCitation={setSelectedCitation} /></div>
        {message.role === "assistant" && <button className="copy-button" onClick={async () => {
          try {
            await navigator.clipboard.writeText(message.content);
            setCopiedId(message.message_id); setCopyError("");
          } catch { setCopyError(t("Could not copy the answer. Select its text to copy it manually.")); }
        }}>{t(copiedId === message.message_id ? "Copied" : "Copy answer")}</button>}
        {!message.completed && !(streaming && message.message_id === liveAssistantId) &&
          <small className="incomplete">{t("Interrupted answer · incomplete")}</small>}
      </li>)}</ol> :
      <div className="welcome">
        <div className="welcome-icon"><BookOpen size={30} strokeWidth={1.5} /></div>
        <p className="eyebrow">{t("A workspace for your PDFs")}</p>
        <h1>{t(chat ? "Start with your documents." : "Make room for a clearer answer.")}</h1>
        <p>{t("Create a conversation, collect your PDFs, and keep the original context close at hand.")}</p>
        <button className="primary" onClick={onLibrary}><BookOpen size={17} />{t("Open Library")}</button>
        <div className="feature-note"><MessageSquare size={17} /><span>{t("Ask questions grounded in your active PDF Library.")}</span></div>
      </div>}
    <div className="composer-area">
      {streamError && <div role="alert" className="error-banner"><span>{streamError}</span>
        <button className="icon-button" aria-label={t("Dismiss generation error")} onClick={onDismissError}>×</button></div>}
      {copyError && <div role="alert" className="error-banner"><span>{copyError}</span>
        <button className="icon-button" aria-label={t("Dismiss copy error")} onClick={() => setCopyError("")}>×</button></div>}
      {stage && <p role="status" className="request-stage">{t(stage)}</p>}
      {compaction && ["queued", "running"].includes(compaction.state) &&
        <p role="status" className="request-stage">{t("Compacting previous conversation messages")}</p>}
      {compaction?.state === "failed" && <div role="alert" className="error-banner">
        <span>{t("Conversation memory could not be updated")} ({compaction.error_category ?? "compaction_failed"}). {t("Your saved messages remain available.")}</span>
        {compaction.retryable && <button className="retry-button" onClick={onRetryCompaction}>{t("Retry memory update")}</button>}
      </div>}
      {canRetry && retryUser && <button className="retry-button" onClick={() => onRetry?.(retryUser.request_id)}>{t("Retry last response")}</button>}
      <form className="composer" onSubmit={(event) => { event.preventDefault(); send(); }}>
        <label className="sr-only" htmlFor="message-composer">{t("Message")}</label>
        <textarea ref={composerRef} id="message-composer" dir="auto" value={draft} onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); }
          }} placeholder={t("Ask about your PDFs…")} disabled={streaming} />
        {streaming ? <button type="button" className="stop-button" onClick={onStop}>{t("Stop")}</button>
          : <button type="submit" className="send-button" disabled={!draft.trim()}>{t("Send")}</button>}
      </form>
      {containsPotentialSecret(draft) && <p role="status" className="secret-warning">{t("This message looks like it may contain an API key or secret. It will be saved verbatim in local history and may be sent to the selected provider. Remove it before sending if unintended.")}</p>}
      <p>{t("Original PDFs and conversation history stay on this computer. Remote providers may receive selected excerpts and conversation context when generation is enabled.")}</p>
    </div>
    {selectedCitation && <SourceDrawer citation={selectedCitation} onClose={() => setSelectedCitation(null)} />}
  </section>;
}

function citationsFor(message: Message): Citation[] {
  const candidate = message.metadata?.citations;
  if (!Array.isArray(candidate)) return [];
  return candidate.filter((item): item is Citation => Boolean(item && typeof item === "object" &&
    typeof item.chunk_id === "string" && typeof item.document_id === "string" &&
    typeof item.filename === "string" && Number.isInteger(item.page_start) &&
    Number.isInteger(item.page_end) && typeof item.url === "string"));
}
