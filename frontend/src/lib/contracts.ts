/** Generated from backend/app/domain/schemas.py by scripts/generate_contracts.py. */

export interface ChatCreate {
  title?: string | null;
}

export interface ChatRename {
  title: string;
}

export interface Chat {
  chat_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  gc_pending?: boolean;
}

export interface ChatList {
  chats: Array<Chat>;
}

export interface Message {
  event_id: string;
  chat_id: string;
  message_id: string;
  request_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  completed: boolean;
  metadata?: Record<string, unknown>;
}

export interface MessageList {
  messages: Array<Message>;
}

export interface MessageSubmission {
  content?: string | null;
  client_message_id?: string | null;
  retry_of_request_id?: string | null;
}

export interface Health {
  status: "ok" | "degraded";
  version: string;
  storage_ready: boolean;
  index_ready: boolean;
  warnings?: Array<string>;
}

export interface ErrorDetail {
  code: string;
  message: string;
  retryable?: boolean;
  request_id?: string | null;
  details?: Array<Record<string, string>> | null;
}

export interface ErrorResponse {
  error: ErrorDetail;
}

export interface Document {
  document_id: string;
  original_name: string;
  title: string;
  sha256: string;
  size_bytes: number;
  page_count: number;
  imported_at: string;
  status: string;
  warnings: Array<string>;
  index_version: string | null;
  error: string | null;
}

export interface DocumentList {
  documents: Array<Document>;
}

export interface IndexJob {
  job_id: string;
  kind: string;
  document_id: string | null;
  stage: string;
  processed: number;
  total: number | null;
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface UploadAccepted {
  document: Document;
  job_id: string;
}

export interface DeletionAccepted {
  job_id: string;
  status: "deleting";
}

export interface IndexStatus {
  index_version: string | null;
  ready: boolean;
  jobs: Array<IndexJob>;
  warnings: Array<string>;
  rebuild_required: boolean;
}

export interface AppSettings {
  provider: "openai" | "anthropic" | "google" | "openai_compatible";
  model: string;
  context_tokens: number;
  output_tokens: number;
  embedding_model: string;
  embedding_revision: string | null;
  ocr_enabled: boolean;
  ocr_languages: string;
  compatible_base_url?: string | null;
  compatible_tools?: boolean;
  compatible_usage?: boolean;
  has_key: boolean;
  persistence_mode: "session" | "keyring";
}

export interface SettingsUpdate {
  provider?: "openai" | "anthropic" | "google" | "openai_compatible" | null;
  model?: string | null;
  context_tokens?: number | null;
  output_tokens?: number | null;
  embedding_model?: string | null;
  embedding_revision?: string | null;
  ocr_enabled?: boolean | null;
  ocr_languages?: string | null;
  compatible_base_url?: string | null;
  compatible_tools?: boolean | null;
  compatible_usage?: boolean | null;
  api_key?: string | null;
  persist_key?: boolean;
  remove_key?: boolean;
}

export interface ConnectionTestResult {
  provider: "openai" | "anthropic" | "google" | "openai_compatible";
  model: string;
  connected: boolean;
  capabilities: Record<string, unknown>;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  filename: string;
  page_start: number;
  page_end: number;
  url: string;
}

export interface SourceDetail {
  chunk_id: string;
  document_id: string;
  filename: string;
  page_start: number;
  page_end: number;
  url: string;
  text: string;
  index_version: string;
  available: boolean;
}

export interface StreamStatus {
  stage: string;
  label: string;
  request_id?: string | null;
}

export interface RetrievedSource {
  chunk_id: string;
  document_id: string;
  page: number;
  page_end: number;
  filename: string;
  score?: number | null;
}

export interface RetrievalEvent {
  request_id: string;
  sources: Array<RetrievedSource>;
}

export interface TokenEvent {
  request_id: string;
  delta: string;
}

export interface UsageEvent {
  request_id: string;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
}

export interface DoneEvent {
  request_id: string;
  message_id: string;
  complete: true;
  duration_ms: number;
}

export interface StreamCitationEvent {
  chunk_id: string;
  document_id: string;
  filename: string;
  page_start: number;
  page_end: number;
  url: string;
  request_id: string;
}

export interface CompactionStatus {
  chat_id: string;
  state: "idle" | "queued" | "running" | "completed" | "failed";
  summary_revision: number;
  compacted_message_count: number;
  pending_message_count: number;
  request_id?: string | null;
  provider?: "openai" | "anthropic" | "google" | "openai_compatible" | null;
  model?: string | null;
  batch_count: number;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  usage?: Record<string, number | null> | null;
  error_category?: string | null;
  retryable: boolean;
}
