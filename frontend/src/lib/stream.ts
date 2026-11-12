import type { ErrorResponse, MessageSubmission } from "./contracts";
import { ApiError } from "./errors";

export interface SseEvent {
  event: string;
  data: unknown;
}
type EventHandler = (event: SseEvent) => void;

export async function readSseStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: EventHandler,
) {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let buffer = "";
  let eventName = "message";
  let dataLines: string[] = [];

  const dispatch = () => {
    if (dataLines.length)
      onEvent({
        event: eventName,
        data: JSON.parse(dataLines.join("\n")) as unknown,
      });
    eventName = "message";
    dataLines = [];
  };
  const line = (value: string) => {
    if (!value) {
      dispatch();
      return;
    }
    if (value.startsWith(":")) return;
    const colon = value.indexOf(":");
    const field = colon < 0 ? value : value.slice(0, colon);
    const content = colon < 0 ? "" : value.slice(colon + 1).replace(/^ /, "");
    if (field === "event") eventName = content || "message";
    if (field === "data") dataLines.push(content);
  };
  const drain = (final: boolean) => {
    while (buffer.length) {
      const lf = buffer.indexOf("\n");
      const cr = buffer.indexOf("\r");
      const positions = [lf, cr].filter((position) => position >= 0);
      if (!positions.length) break;
      const end = Math.min(...positions);
      if (buffer[end] === "\r" && end === buffer.length - 1 && !final) break;
      const skip = buffer[end] === "\r" && buffer[end + 1] === "\n" ? 2 : 1;
      line(buffer.slice(0, end));
      buffer = buffer.slice(end + skip);
    }
    if (final && buffer.length) {
      line(buffer);
      buffer = "";
    }
    if (final) dispatch();
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      drain(false);
    }
    buffer += decoder.decode();
    drain(true);
  } catch (error) {
    await reader.cancel(error).catch(() => undefined);
    throw error;
  } finally {
    reader.releaseLock();
  }
}

export async function streamMessage(
  chatId: string,
  body: MessageSubmission,
  signal: AbortSignal,
  onEvent: EventHandler,
): Promise<void> {
  const response = await fetch(
    `/api/chats/${encodeURIComponent(chatId)}/messages/stream`,
    {
      method: "POST",
      signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    let details: ErrorResponse | undefined;
    try {
      details = (await response.json()) as ErrorResponse;
    } catch {
      /* Safe fallback follows. */
    }
    throw new ApiError(
      response.status,
      details?.error?.code ?? "request_failed",
      details?.error?.message ??
        `Request failed (${response.status}). Please retry.`,
    );
  }
  if (
    !response.headers.get("content-type")?.includes("text/event-stream") ||
    !response.body
  ) {
    throw new ApiError(
      response.status,
      "invalid_stream",
      "The server returned an unexpected response format.",
    );
  }
  let terminal = false;
  await readSseStream(response.body, (event) => {
    if (event.event === "error") {
      const failure = event.data as ErrorResponse;
      throw new ApiError(
        response.status,
        failure.error?.code ?? "generation_failed",
        failure.error?.message ?? "The request could not be completed.",
      );
    }
    if (event.event === "done") terminal = true;
    onEvent(event);
  });
  if (!terminal && !signal.aborted) {
    throw new ApiError(
      response.status,
      "incomplete_stream",
      "The response ended before completion.",
    );
  }
}
