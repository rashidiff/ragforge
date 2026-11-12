import { afterEach, expect, it, vi } from "vitest";
import { readSseStream, streamMessage } from "../src/lib/stream";
import { ApiError } from "../src/lib/errors";

afterEach(() => vi.unstubAllGlobals());

function byteStream(text: string, splitAt: number[]) {
  const encoded = new TextEncoder().encode(text);
  const pieces: Uint8Array[] = [];
  let previous = 0;
  for (const position of [...new Set(splitAt)].sort(
    (left, right) => left - right,
  )) {
    pieces.push(encoded.slice(previous, position));
    previous = position;
  }
  pieces.push(encoded.slice(previous));
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const piece of pieces) controller.enqueue(piece);
      controller.close();
    },
  });
}

it("incrementally decodes split Unicode, CRLF frames, multiline data, and heartbeat comments", async () => {
  const body =
    'event: token\r\ndata: {"delta":\r\ndata: "فارسی français"}\r\n\r\n: heartbeat\r\n\r\nevent: done\r\ndata: {"complete":true}\r\n\r\n';
  const bytes = new TextEncoder().encode(body);
  const split = bytes.findIndex((byte, index) => byte >= 0x80 && index > 0) + 1;
  const received: Array<{ event: string; data: unknown }> = [];
  await readSseStream(byteStream(body, [split, 4, 18, 45]), (item) =>
    received.push(item),
  );
  expect(received).toEqual([
    { event: "token", data: { delta: "فارسی français" } },
    { event: "done", data: { complete: true } },
  ]);
});

it("posts JSON and reports a safe streamed provider error", async () => {
  const response = new Response(
    'event: error\ndata: {"error":{"code":"rate_limited","message":"Retry later","retryable":true}}\n\n',
    { status: 200, headers: { "content-type": "text/event-stream" } },
  );
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  await expect(
    streamMessage(
      "chat/id",
      { content: "question", client_message_id: "message-id" },
      new AbortController().signal,
      () => {},
    ),
  ).rejects.toMatchObject({
    name: "ApiError",
    code: "rate_limited",
    message: "Retry later",
  });
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/chats/chat%2Fid/messages/stream",
    expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ Accept: "text/event-stream" }),
    }),
  );
});

it("does not treat a stream without a terminal done event as complete", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response('event: token\ndata: {"delta":"partial"}\n\n', {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        }),
      ),
  );
  await expect(
    streamMessage(
      "chat",
      { content: "q", client_message_id: "id" },
      new AbortController().signal,
      () => {},
    ),
  ).rejects.toBeInstanceOf(ApiError);
});
