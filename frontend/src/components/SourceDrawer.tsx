import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { api } from "../lib/api";
import type { Citation, SourceDetail } from "../lib/contracts";
import { useLocale } from "../lib/i18n";

interface Props {
  citation: Citation;
  onClose: () => void;
}

export function SourceDrawer({ citation, onClose }: Props) {
  const [source, setSource] = useState<SourceDetail | null>(null);
  const [error, setError] = useState("");
  const { t } = useLocale();
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previouslyFocused =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    closeButton.current?.focus();
    return () => previouslyFocused?.focus();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    api
      .sourceExcerpt(citation.document_id, citation.chunk_id, controller.signal)
      .then(setSource)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason.message
              : "This source is unavailable.",
          );
      });
    return () => controller.abort();
  }, [citation.chunk_id, citation.document_id]);

  return (
    <div
      className="source-scrim"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <aside
        className="source-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`${t("PDF source")}: ${citation.filename}`}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            onClose();
            return;
          }
          if (event.key === "Tab") {
            const focusable = event.currentTarget.querySelectorAll<HTMLElement>(
              "a[href], button:not(:disabled), iframe, input:not(:disabled)",
            );
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <header>
          <div>
            <p className="eyebrow">{t("PDF source")}</p>
            <h2 dir="auto">{citation.filename}</h2>
            <span dir="auto">
              {t("Page")} {citation.page_start}
              {citation.page_end > citation.page_start
                ? `–${citation.page_end}`
                : ""}
            </span>
          </div>
          <button
            ref={closeButton}
            className="icon-button"
            aria-label={t("Close source")}
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        {error ? (
          <p role="alert">{error}</p>
        ) : !source ? (
          <p role="status">{t("Loading source…")}</p>
        ) : (
          <>
            <blockquote dir="auto">{source.text}</blockquote>
            <a
              className="source-open"
              href={source.url}
              target="_blank"
              rel="noreferrer"
            >
              {t("Open PDF at page")} {source.page_start}
            </a>
            <iframe
              title={`${source.filename}, page ${source.page_start}`}
              src={source.url}
            />
          </>
        )}
      </aside>
    </div>
  );
}
