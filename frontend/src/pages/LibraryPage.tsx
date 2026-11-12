import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, ExternalLink, Plus, RefreshCw, Trash2, X } from "lucide-react";
import { api } from "../lib/api";
import type { Document as LibraryDocument, IndexStatus } from "../lib/contracts";
import { useLocale } from "../lib/i18n";

const labels: Record<string, string> = {
  queued: "Queued", loading_model: "Loading local embedding model", extracting: "Extracting pages",
  ocr: "Checking or running local OCR", chunking: "Chunking text", embedding: "Embedding locally",
  indexing: "Publishing index", ready: "Ready", failed: "Failed", deleting: "Removing PDF",
};

export function LibraryPage() {
  const { t } = useLocale();
  const [documents, setDocuments] = useState<LibraryDocument[]>([]);
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState<LibraryDocument | null>(null);
  const [page, setPage] = useState(1);
  const input = useRef<HTMLInputElement>(null);
  const controller = useRef<AbortController | null>(null);

  const reload = useCallback(async (signal?: AbortSignal) => {
    const [library, index] = await Promise.all([api.library(signal), api.indexStatus(signal)]);
    if (signal?.aborted) return;
    setDocuments(library.documents);
    setStatus(index);
    setPreview((current) => current ? library.documents.find((item) => item.document_id === current.document_id) ?? null : null);
  }, []);

  useEffect(() => {
    const abort = new AbortController();
    controller.current = abort;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { await reload(abort.signal); }
      catch (reason) { if (!abort.signal.aborted) setError(reason instanceof Error ? reason.message : "Library could not be loaded."); }
      finally {
        if (!abort.signal.aborted) { setLoading(false); timer = setTimeout(() => void poll(), 1500); }
      }
    }
    void poll();
    return () => { abort.abort(); clearTimeout(timer); };
  }, [reload]);

  const busy = mutating || uploading || (status?.jobs.some((job) => !["ready", "failed"].includes(job.stage)) ?? false);

  async function upload(files: FileList | File[]) {
    if (busy || files.length === 0) return;
    if (files.length !== 1) { setError("Upload one PDF at a time so each indexing job can finish."); return; }
    const file = files[0];
    if (!file.name.toLowerCase().endsWith(".pdf")) { setError("Only PDF files are accepted."); return; }
    setUploading(true); setError("");
    try { await api.uploadPdf(file, controller.current?.signal); await reload(controller.current?.signal); }
    catch (reason) { if (!controller.current?.signal.aborted) setError(reason instanceof Error ? reason.message : "Upload failed."); }
    finally { setUploading(false); if (input.current) input.current.value = ""; }
  }

  async function mutation(action: () => Promise<unknown>) {
    if (busy) return;
    setMutating(true); setError("");
    try { await action(); await reload(controller.current?.signal); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Library update failed."); }
    finally { setMutating(false); }
  }

  function open(document: LibraryDocument) { setPage(1); setPreview(document); }
  const sourceUrl = preview ? `/api/library/${encodeURIComponent(preview.document_id)}/pdf#page=${page}` : "";

  return <section className="library-page" aria-label={t("PDF Library")}>
    <div className="library-heading"><div><p className="eyebrow">{t("Library")}</p><h1>{t("Your documents, together.")}</h1>
      <p>{t("PDFs are shared across chats once local indexing succeeds.")}</p></div>
      <div className="library-toolbar"><button disabled={busy || loading} onClick={() => void mutation(api.rebuildIndex)}><RefreshCw size={16} />{t("Rebuild index")}</button>
        <button className="primary" disabled={busy} onClick={() => input.current?.click()}><Plus size={17} />{t("Upload PDF")}</button></div>
    </div>
    <input ref={input} className="file-input" type="file" accept=".pdf,application/pdf" aria-label={t("Choose PDF file")}
      onChange={(event) => { if (event.target.files) void upload(event.target.files); }} />
    {error && <div className="error-banner" role="alert"><span>{error}</span><button className="icon-button" aria-label={t("Dismiss Library error")} onClick={() => setError("")}><X size={16} /></button></div>}
    <div className={`upload-drop ${dragging ? "dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); void upload(event.dataTransfer.files); }}>
      <BookOpen size={23} /><p>{t(uploading ? "Uploading and validating PDF…" : "Drop a PDF here, or choose Upload PDF.")}</p>
      <small>{t("Original files and all indexing stay on this computer.")}</small>
    </div>
    {loading && <div role="status" aria-busy="true"><p>{t("Loading Library…")}</p>
      <span className="skeleton skeleton-line" aria-hidden="true" /><span className="skeleton skeleton-line short" aria-hidden="true" /></div>}
    {status?.warnings.map((warning) => <p className="library-warning" key={warning}>{warning}</p>)}
    <div className="index-jobs" aria-live="polite">
      {status?.jobs.slice(0, 3).map((job) => <div key={job.job_id} className={`job-stage ${job.stage}`}>
        <span dir="auto">{t(labels[job.stage] ?? job.stage)} · {t(job.kind)}</span>
        {job.total != null && job.total > 0 && <span> {job.processed} / {job.total}</span>}
        {job.error && <p role="alert">{job.error}</p>}
      </div>)}
    </div>
    <ul className="document-list" aria-label={t("Library documents")}>
      {documents.map((document) => <li key={document.document_id} className="document-card">
        <div className="document-main"><BookOpen size={21} /><div><h2 dir="auto">{document.title}</h2>
          <p dir="auto">{document.page_count} {t("pages")} · {(document.size_bytes / 1024 / 1024).toFixed(2)} MB · {new Date(document.imported_at).toLocaleDateString()}</p>
          <span className={`document-status ${document.status}`}>{t(labels[document.status] ?? document.status)}</span>
          {document.original_name !== document.title && <small dir="auto">{document.original_name}</small>}
        </div></div>
        {document.warnings.map((warning) => <p className="library-warning" key={warning}>{warning}</p>)}
        {document.error && <p role="alert" className="error">{document.error}</p>}
        <div className="document-actions"><button onClick={() => open(document)}>{t("Preview")}</button>
          <button disabled={busy} onClick={() => void mutation(() => api.reindexPdf(document.document_id))}><RefreshCw size={14} />{t("Reindex")}</button>
          <button disabled={busy} onClick={() => { if (window.confirm(`${t("Remove")} ${document.original_name} ${t("from the Library? Historical chats will be preserved.")}`)) void mutation(() => api.deletePdf(document.document_id)); }}><Trash2 size={14} />{t("Remove")}</button></div>
      </li>)}
    </ul>
    {preview && <section className="pdf-preview" aria-label={`${t("Preview")} ${preview.original_name}`}>
      <div className="preview-toolbar"><strong dir="auto">{preview.original_name}</strong>
        <label>{t("Page")} <input type="number" min={1} max={preview.page_count} value={page}
          onChange={(event) => setPage(Math.max(1, Math.min(preview.page_count, Number(event.target.value) || 1)))} /></label>
        <a href={sourceUrl} target="_blank" rel="noreferrer"><ExternalLink size={14} />{t("Open PDF")}</a>
        <button className="icon-button" aria-label={t("Close PDF preview")} onClick={() => setPreview(null)}><X size={18} /></button>
      </div>
      <iframe key={`${preview.document_id}:${page}`} title={`${preview.original_name}, page ${page}`} src={sourceUrl} />
    </section>}
  </section>;
}
