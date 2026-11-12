import { BookOpen, Download, MessageSquare, Pencil, Plus, Settings, Trash2 } from "lucide-react";
import { useState } from "react";
import type { Chat } from "../lib/contracts";
import { useLocale } from "../lib/i18n";

export type Page = "chat" | "library" | "settings";
interface Props {
  chats: Chat[];
  selected: string | null;
  page: Page;
  loading: boolean;
  creating: boolean;
  onNavigate: (page: Page) => void;
  onSelect: (id: string) => void;
  onCreate: () => Promise<void>;
  onRename: (id: string, title: string) => Promise<void>;
  onDelete: (chat: Chat) => void;
  onExport: (id: string, format: "markdown" | "json") => void;
}

export function Sidebar(props: Props) {
  const { t } = useLocale();
  const [editing, setEditing] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);

  async function save(id: string) {
    if (!title.trim() || saving) return;
    setSaving(true);
    try { await props.onRename(id, title); setEditing(null); } catch { /* App shows the error. */ }
    finally { setSaving(false); }
  }

  return <aside id="sidebar" className="sidebar" aria-label={t("Chat navigation")}>
    <div className="brand"><span className="brand-mark"><BookOpen size={21} /></span>
      <div><strong>Local RAG Chat</strong><small>{t("Your documents, in focus")}</small></div></div>
    <button className="new-chat" disabled={props.creating} onClick={() => void props.onCreate()}>
      <Plus size={18} /> {t(props.creating ? "Creating…" : "New chat")}
    </button>
    <nav aria-label={t("Main navigation")}>
      <button aria-current={props.page === "library" ? "page" : undefined} onClick={() => props.onNavigate("library")}>
        <BookOpen size={18} />{t("Library")}
      </button>
      <button aria-current={props.page === "settings" ? "page" : undefined} onClick={() => props.onNavigate("settings")}>
        <Settings size={18} />{t("Settings")}
      </button>
    </nav>
    <h2 className="section-label">{t("Conversations")}</h2>
    {props.loading && <div role="status" className="muted" aria-busy="true"><span>{t("Loading chats…")}</span>
      <span className="skeleton skeleton-line" aria-hidden="true" /><span className="skeleton skeleton-line short" aria-hidden="true" /></div>}
    {!props.loading && props.chats.length === 0 && <p className="muted empty-list">{t("Your conversations will appear here.")}</p>}
    <ul className="chat-list">
      {props.chats.map((chat) => <li key={chat.chat_id} className={props.page === "chat" && props.selected === chat.chat_id ? "selected" : ""}>
        {editing === chat.chat_id ? <form className="rename-form" onSubmit={(e) => { e.preventDefault(); void save(chat.chat_id); }}>
          <input autoFocus aria-label={t("Chat title")} maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Escape") setEditing(null); }} />
          <button disabled={saving || !title.trim()} type="submit">{t("Save")}</button>
          <button type="button" disabled={saving} onClick={() => setEditing(null)}>{t("Cancel")}</button>
        </form> : <>
          <button className="chat-select" onClick={() => props.onSelect(chat.chat_id)}
            aria-current={props.page === "chat" && props.selected === chat.chat_id ? "page" : undefined}>
            <MessageSquare size={15} /><span dir="auto">{chat.title}</span>
          </button>
          <div className="chat-actions">
            <button className="icon-button" aria-label={`${t("Rename")} ${chat.title}`} onClick={() => { setEditing(chat.chat_id); setTitle(chat.title); }}><Pencil size={14} /></button>
            <button className="icon-button" aria-label={`${t("Export as Markdown")} ${chat.title}`} onClick={() => props.onExport(chat.chat_id, "markdown")}><Download size={14} /></button>
            <button className="icon-button" aria-label={`${t("Export as JSON")} ${chat.title}`} onClick={() => props.onExport(chat.chat_id, "json")}><Download size={14} /></button>
            <button className="icon-button" aria-label={`${t("Delete")} ${chat.title}`} onClick={() => props.onDelete(chat)}><Trash2 size={14} /></button>
          </div>
        </>}
      </li>)}
    </ul>
    <div className="sidebar-footer"><span className="local-dot" /> {t("Local storage · No account")}</div>
  </aside>;
}
