import type {
  ErrorResponse,
  Chat,
  Health,
  Message,
  DocumentList,
  IndexStatus,
  UploadAccepted,
  IndexJob,
  DeletionAccepted,
  AppSettings,
  SettingsUpdate,
  ConnectionTestResult,
  SourceDetail,
  CompactionStatus,
} from "./contracts";
import { streamMessage } from "./stream";
import { ApiError } from "./errors";
export { ApiError } from "./errors";

export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      ...(init.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    let detail: ErrorResponse | undefined;
    try {
      detail = (await response.json()) as ErrorResponse;
    } catch {
      /* Safe fallback below. */
    }
    throw new ApiError(
      response.status,
      detail?.error?.code ?? "request_failed",
      detail?.error?.message ??
        `Request failed (${response.status}). Please retry.`,
    );
  }
  return response.status === 204
    ? (undefined as T)
    : ((await response.json()) as T);
}

async function download(path: string): Promise<Blob> {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    let detail: ErrorResponse | undefined;
    try {
      detail = (await response.json()) as ErrorResponse;
    } catch {
      /* Use a safe fallback. */
    }
    throw new ApiError(
      response.status,
      detail?.error?.code ?? "download_failed",
      detail?.error?.message ??
        `Download failed (${response.status}). Please retry.`,
    );
  }
  return response.blob();
}

export const api = {
  health: (signal?: AbortSignal) => request<Health>("/health", { signal }),
  chats: (signal?: AbortSignal) =>
    request<{ chats: Chat[] }>("/chats", { signal }),
  createChat: () => request<Chat>("/chats", { method: "POST", body: "{}" }),
  renameChat: (id: string, title: string) =>
    request<Chat>(`/chats/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteChat: (id: string) =>
    request<void>(`/chats/${encodeURIComponent(id)}`, { method: "DELETE" }),
  exportChat: (id: string, format: "markdown" | "json") =>
    download(`/chats/${encodeURIComponent(id)}/export?format=${format}`),
  backupHistory: () => download("/history/backup"),
  messages: (id: string, signal?: AbortSignal) =>
    request<{ messages: Message[] }>(
      `/chats/${encodeURIComponent(id)}/messages`,
      { signal },
    ),
  compactionStatus: (id: string, signal?: AbortSignal) =>
    request<CompactionStatus>(`/chats/${encodeURIComponent(id)}/compaction`, {
      signal,
    }),
  retryCompaction: (id: string) =>
    request<CompactionStatus>(
      `/chats/${encodeURIComponent(id)}/compaction/retry`,
      { method: "POST", body: "{}" },
    ),
  library: (signal?: AbortSignal) =>
    request<DocumentList>("/library", { signal }),
  indexStatus: (signal?: AbortSignal) =>
    request<IndexStatus>("/index/status", { signal }),
  uploadPdf: (file: File, signal?: AbortSignal) => {
    const body = new FormData();
    body.append("file", file);
    return request<UploadAccepted>("/library/upload", {
      method: "POST",
      body,
      signal,
    });
  },
  reindexPdf: (id: string) =>
    request<IndexJob>(`/library/${encodeURIComponent(id)}/reindex`, {
      method: "POST",
    }),
  deletePdf: (id: string) =>
    request<DeletionAccepted>(`/library/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  rebuildIndex: () => request<IndexJob>("/index/rebuild", { method: "POST" }),
  settings: (signal?: AbortSignal) =>
    request<AppSettings>("/settings", { signal }),
  updateSettings: (values: SettingsUpdate) =>
    request<AppSettings>("/settings", {
      method: "PUT",
      body: JSON.stringify(values),
    }),
  testProviderConnection: () =>
    request<ConnectionTestResult>("/settings/test-connection", {
      method: "POST",
      body: "{}",
    }),
  sourceExcerpt: (documentId: string, chunkId: string, signal?: AbortSignal) =>
    request<SourceDetail>(
      `/library/${encodeURIComponent(documentId)}/sources/${encodeURIComponent(chunkId)}`,
      { signal },
    ),
  streamMessage,
};
