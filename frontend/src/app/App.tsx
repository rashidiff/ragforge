import { useCallback, useEffect, useRef, useState } from "react";
import { Menu, Moon, Sun, X } from "lucide-react";
import { Sidebar } from "../components/Sidebar";
import type { Page } from "../components/Sidebar";
import { DeleteChatDialog } from "../components/DeleteChatDialog";
import { ChatPage } from "../pages/ChatPage";
import { LibraryPage } from "../pages/LibraryPage";
import { SettingsPage } from "../pages/SettingsPage";
import { api } from "../lib/api";
import { LocaleProvider, translate } from "../lib/i18n";
import type { Locale } from "../lib/i18n";
import type { Chat, Citation, CompactionStatus, Health, Message, MessageSubmission } from "../lib/contracts";

function message(error: unknown) {
  return error instanceof Error ? error.message : "The request could not finish. Please retry.";
}

export function App() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [page, setPage] = useState<Page>("chat");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Chat | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [dark, setDark] = useState(() => {
    try { return window.localStorage.getItem("local-rag-theme") === "dark"; } catch { return false; }
  });
  const [locale, setLocale] = useState<Locale>(() => {
    try {
      const stored = window.localStorage.getItem("local-rag-locale");
      return stored === "fr" || stored === "fa" ? stored : "en";
    } catch { return "en"; }
  });
  const [health, setHealth] = useState<Health | null>(null);
  const [streamChatId, setStreamChatId] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState("");
  const [streamError, setStreamError] = useState("");
  const [streamErrorChatId, setStreamErrorChatId] = useState<string | null>(null);
  const [compaction, setCompaction] = useState<CompactionStatus | null>(null);
  const [compactionVersion, setCompactionVersion] = useState(0);
  const [optimisticUser, setOptimisticUser] = useState<Message | null>(null);
  const [liveAssistant, setLiveAssistant] = useState<Message | null>(null);
  const streamController = useRef<AbortController | null>(null);
  const selectedRef = useRef<string | null>(null);
  const navigationToggle = useRef<HTMLButtonElement>(null);
  const wasSidebarOpen = useRef(false);

  function saveBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = filename; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  async function exportChat(id: string, format: "markdown" | "json") {
    if (!window.confirm(translate(locale, "Export warning"))) return;
    try { saveBlob(await api.exportChat(id, format), `chat-${id}.${format === "markdown" ? "md" : "json"}`); }
    catch (reason) { setError(message(reason)); }
  }

  async function backupHistory() {
    if (!window.confirm(translate(locale, "Backup warning"))) return;
    try { saveBlob(await api.backupHistory(), "chat-history.jsonl"); }
    catch (reason) { setError(message(reason)); }
  }

  useEffect(() => { selectedRef.current = selected; }, [selected]);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try { window.localStorage.setItem("local-rag-theme", dark ? "dark" : "light"); } catch { /* Theme is a nonessential preference. */ }
  }, [dark]);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === "fa" ? "rtl" : "ltr";
    try { window.localStorage.setItem("local-rag-locale", locale); } catch { /* Locale is a nonessential preference. */ }
  }, [locale]);

  useEffect(() => {
    if (sidebarOpen && !wasSidebarOpen.current) {
      document.querySelector<HTMLButtonElement>("#sidebar .new-chat")?.focus();
    } else if (!sidebarOpen && wasSidebarOpen.current) {
      navigationToggle.current?.focus();
    }
    wasSidebarOpen.current = sidebarOpen;
  }, [sidebarOpen]);

  useEffect(() => {
    if (!sidebarOpen) return;
    const handleNavigationKeys = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setSidebarOpen(false); return; }
      if (event.key !== "Tab" || window.matchMedia("(min-width: 761px)").matches) return;
      const sidebar = document.getElementById("sidebar");
      if (!sidebar) return;
      const items = [navigationToggle.current, ...Array.from(sidebar.querySelectorAll<HTMLElement>(
        'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)'))]
        .filter((item): item is HTMLElement => item instanceof HTMLElement && item.offsetParent !== null);
      const first = items[0]; const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    window.addEventListener("keydown", handleNavigationKeys);
    return () => window.removeEventListener("keydown", handleNavigationKeys);
  }, [sidebarOpen]);

  useEffect(() => {
    const controller = new AbortController();
    api.chats(controller.signal).then((data) => {
      setChats(data.chats); setSelected(data.chats[0]?.chat_id ?? null);
      selectedRef.current = data.chats[0]?.chat_id ?? null;
    }).catch((reason: unknown) => { if (!controller.signal.aborted) setError(message(reason)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    api.health(controller.signal).then(setHealth).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(message(reason));
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setMessages([]);
    if (!selected) { setLoadingMessages(false); return () => controller.abort(); }
    setLoadingMessages(true);
    api.messages(selected, controller.signal).then((data) => {
      if (!controller.signal.aborted) setMessages(data.messages);
    }).catch((reason: unknown) => { if (!controller.signal.aborted) setError(message(reason)); })
      .finally(() => { if (!controller.signal.aborted) setLoadingMessages(false); });
    return () => controller.abort();
  }, [selected]);

  useEffect(() => {
    if (!selected) { setCompaction(null); return; }
    const controller = new AbortController();
    let timer: number | undefined;
    const load = async () => {
      try {
        const next = await api.compactionStatus(selected, controller.signal);
        if (controller.signal.aborted) return;
        setCompaction(next);
        if (next.state === "queued" || next.state === "running")
          timer = window.setTimeout(load, 900);
      } catch (reason) {
        if (!controller.signal.aborted) setError(message(reason));
      }
    };
    void load();
    return () => { controller.abort(); if (timer !== undefined) window.clearTimeout(timer); };
  }, [selected, compactionVersion]);

  const navigate = useCallback((next: Page) => { setPage(next); setSidebarOpen(false); }, []);

  async function create() {
    if (creating) return;
    setCreating(true); setError("");
    try {
      const chat = await api.createChat();
      setChats((current) => [chat, ...current]); setSelected(chat.chat_id); selectedRef.current = chat.chat_id; navigate("chat");
    } catch (reason) { setError(message(reason)); }
    finally { setCreating(false); }
  }

  async function rename(id: string, title: string) {
    try {
      const updated = await api.renameChat(id, title);
      setChats((current) => [updated, ...current.filter((chat) => chat.chat_id !== id)]);
    } catch (reason) { setError(message(reason)); throw reason; }
  }

  async function remove() {
    if (!deleteTarget || deleting) return;
    const id = deleteTarget.chat_id;
    setDeleting(true); setDeleteError("");
    try {
      await api.deleteChat(id);
      const remaining = chats.filter((chat) => chat.chat_id !== id);
      setChats(remaining);
      if (selected === id) { setSelected(remaining[0]?.chat_id ?? null); selectedRef.current = remaining[0]?.chat_id ?? null; }
      setDeleteTarget(null);
    } catch (reason) { setDeleteError(message(reason)); }
    finally { setDeleting(false); }
  }

  async function startMessage(content: string, retryOfRequestId?: string) {
    if (streamController.current || (!retryOfRequestId && !content.trim())) return;
    setStreamError(""); setStreamErrorChatId(null); setStreamStatus("Preparing request…");
    let chatId = selectedRef.current;
    if (!chatId) {
      try {
        const created = await api.createChat();
        chatId = created.chat_id;
        setChats((current) => [created, ...current]);
        selectedRef.current = chatId; setSelected(chatId); navigate("chat");
      } catch (reason) { setStreamError(message(reason)); return; }
    }
    const clientId = crypto.randomUUID();
    if (!retryOfRequestId) {
      setOptimisticUser({ event_id: clientId, chat_id: chatId, message_id: clientId,
        request_id: clientId, role: "user", content, created_at: new Date().toISOString(),
        completed: true, metadata: {} });
    }
    setLiveAssistant(null);
    setStreamChatId(chatId);
    const controller = new AbortController();
    streamController.current = controller;
    let liveText = "";
    let citations: Citation[] = [];
    const submission: MessageSubmission = retryOfRequestId
      ? { retry_of_request_id: retryOfRequestId }
      : { content, client_message_id: clientId };
    try {
      await api.streamMessage(chatId, submission, controller.signal, ({ event, data }) => {
        if (!data || typeof data !== "object") return;
        const payload = data as Record<string, unknown>;
        if (event === "status" && typeof payload.label === "string") setStreamStatus(payload.label);
        if (event === "token" && typeof payload.delta === "string") {
          liveText += payload.delta;
          setLiveAssistant({ event_id: clientId, chat_id: chatId!, message_id: `live-${clientId}`,
            request_id: typeof payload.request_id === "string" ? payload.request_id : clientId,
            role: "assistant", content: liveText, created_at: new Date().toISOString(),
            completed: false, metadata: { citations } });
        }
        if (event === "citation" && typeof payload.chunk_id === "string" &&
            typeof payload.document_id === "string" && typeof payload.filename === "string" &&
            typeof payload.page_start === "number" && typeof payload.page_end === "number" &&
            typeof payload.url === "string") {
          const { request_id: _requestId, ...citation } = payload;
          citations = [...citations.filter((item) => item.chunk_id !== citation.chunk_id), citation as Citation];
          setLiveAssistant((current) => current ? { ...current, metadata: { citations } } : current);
        }
      });
    } catch (reason) {
      if (!controller.signal.aborted) { setStreamError(message(reason)); setStreamErrorChatId(chatId); }
    } finally {
      try {
        const latest = await api.messages(chatId);
        if (selectedRef.current === chatId) setMessages(latest.messages);
      } catch (reason) {
        if (selectedRef.current === chatId) { setStreamError(message(reason)); setStreamErrorChatId(chatId); }
      }
      setOptimisticUser(null); setLiveAssistant(null); setStreamChatId(null); setStreamStatus("");
      setCompactionVersion((value) => value + 1);
      if (streamController.current === controller) streamController.current = null;
    }
  }

  function stopMessage() { streamController.current?.abort(); }

  async function retryCompaction() {
    if (!selected) return;
    try {
      await api.retryCompaction(selected);
      setCompactionVersion((value) => value + 1);
    } catch (reason) { setError(message(reason)); }
  }

  const current = chats.find((chat) => chat.chat_id === selected);
  const currentStream = streamChatId === selected;
  const visibleMessages = [
    ...messages,
    ...(currentStream && optimisticUser && optimisticUser.chat_id === selected ? [optimisticUser] : []),
    ...(currentStream && liveAssistant && liveAssistant.chat_id === selected ? [liveAssistant] : []),
  ];
  return <LocaleProvider locale={locale}><div className={`app ${sidebarOpen ? "sidebar-open" : ""}`}>
    <a className="skip-link" href="#main">{translate(locale, "Skip to content")}</a>
    {sidebarOpen && <button className="sidebar-scrim" aria-label={translate(locale, "Close navigation")} onClick={() => setSidebarOpen(false)} />}
    <Sidebar chats={chats} selected={selected} page={page} loading={loading} creating={creating}
      onCreate={create} onRename={rename} onDelete={(chat) => { setDeleteTarget(chat); setDeleteError(""); }}
      onExport={(id, format) => void exportChat(id, format)}
      onSelect={(id) => { setSelected(id); navigate("chat"); }} onNavigate={navigate} />
    <main id="main" tabIndex={-1}>
      <header className="topbar">
        <button ref={navigationToggle} className="icon-button navigation-toggle" aria-label={translate(locale, sidebarOpen ? "Close navigation" : "Open navigation")}
          aria-expanded={sidebarOpen} aria-controls="sidebar" onClick={() => setSidebarOpen(!sidebarOpen)}><Menu size={21} /></button>
        <div className="page-title" dir="auto">{page === "chat" ? current?.title ?? translate(locale, "Your workspace") : translate(locale, page === "library" ? "Library" : "Settings")}</div>
        <span className="connection-state">{health?.storage_ready ? translate(locale, "Local workspace") : translate(locale, "Connecting…")}</span>
        <label className="locale-select"><span className="sr-only">{translate(locale, "Interface language")}</span><select aria-label={translate(locale, "Interface language")}
          value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
          <option value="en">English</option><option value="fr">Français</option><option value="fa">فارسی</option>
        </select></label>
        <button className="icon-button" aria-pressed={dark} aria-label={translate(locale, dark ? "Use light theme" : "Use dark theme")} onClick={() => setDark(!dark)}>
          {dark ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </header>
      {error && <div className="error-banner" role="alert"><span>{error}</span><button className="icon-button" aria-label={translate(locale, "Close error")} onClick={() => setError("")}><X size={17} /></button></div>}
      {page === "chat" && <ChatPage chat={current} messages={visibleMessages} loading={loadingMessages}
        onLibrary={() => navigate("library")} onSend={(content) => startMessage(content)}
        onStop={stopMessage} onRetry={(requestId) => startMessage("", requestId)}
        streaming={currentStream} stage={currentStream ? streamStatus : ""}
        streamError={streamError && (!streamErrorChatId || streamErrorChatId === selected) ? streamError : ""}
        liveAssistantId={liveAssistant?.message_id}
        compaction={compaction?.chat_id === selected ? compaction : null}
        onRetryCompaction={retryCompaction}
        onDismissError={() => { setStreamError(""); setStreamErrorChatId(null); }} />}
      {page === "library" && <LibraryPage />}
      {page === "settings" && <SettingsPage onBackup={() => void backupHistory()} />}
    </main>
    <DeleteChatDialog chat={deleteTarget} busy={deleting} error={deleteError}
      onCancel={() => setDeleteTarget(null)} onConfirm={remove} />
  </div></LocaleProvider>;
}
