import { expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPage } from "../src/pages/ChatPage";

it("sends on Enter, preserves a newline on Shift+Enter, and exposes Stop during a stream", async () => {
  const onSend = vi.fn();
  const onStop = vi.fn();
  const user = userEvent.setup();
  const view = render(<ChatPage chat={undefined} messages={[]} loading={false}
    onLibrary={() => {}} onSend={onSend} onStop={onStop} />);
  const composer = screen.getByRole("textbox", { name: "Message" });
  await user.type(composer, "first line");
  await user.keyboard("{Shift>}{Enter}{/Shift}");
  expect(composer).toHaveValue("first line\n");
  await user.type(composer, "second line");
  await user.keyboard("{Enter}");
  expect(onSend).toHaveBeenCalledWith("first line\nsecond line");
  view.rerender(<ChatPage chat={undefined} messages={[]} loading={false} onLibrary={() => {}}
    onSend={onSend} onStop={onStop} streaming stage="Streaming answer" />);
  await user.click(screen.getByRole("button", { name: "Stop" }));
  expect(onStop).toHaveBeenCalledOnce();
  expect(screen.getByRole("status")).toHaveTextContent("Streaming answer");
});

it("shows running compaction progress and offers a retry after failure", async () => {
  const retry = vi.fn();
  const user = userEvent.setup();
  const view = render(<ChatPage chat={undefined} messages={[]} loading={false} onLibrary={() => {}}
    compaction={{ chat_id: "chat", state: "running", summary_revision: 0,
      compacted_message_count: 0, pending_message_count: 8, batch_count: 8, retryable: false }} />);
  expect(screen.getByRole("status")).toHaveTextContent("Compacting previous conversation messages");
  view.rerender(<ChatPage chat={undefined} messages={[]} loading={false} onLibrary={() => {}}
    onRetryCompaction={retry} compaction={{ chat_id: "chat", state: "failed", summary_revision: 0,
      compacted_message_count: 0, pending_message_count: 8, batch_count: 8,
      error_category: "network_error", retryable: true }} />);
  expect(screen.getByRole("alert")).toHaveTextContent("network_error");
  await user.click(screen.getByRole("button", { name: "Retry memory update" }));
  expect(retry).toHaveBeenCalledOnce();
});

it("keeps the reader's scroll position when new streamed content arrives", () => {
  const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  const scrolling = document.scrollingElement!;
  Object.defineProperty(scrolling, "scrollTop", { configurable: true, value: 0 });
  Object.defineProperty(scrolling, "clientHeight", { configurable: true, value: 400 });
  Object.defineProperty(scrolling, "scrollHeight", { configurable: true, value: 1200 });
  const view = render(<ChatPage chat={undefined} messages={[]} loading={false} onLibrary={() => {}} />);
  scrollTo.mockClear();
  window.dispatchEvent(new Event("scroll"));
  view.rerender(<ChatPage chat={undefined} messages={[{
    event_id: "event", chat_id: "chat", message_id: "message", request_id: "request",
    role: "assistant", content: "New streamed text", created_at: "2026-11-12T10:00:00Z",
    completed: false, metadata: {},
  }]} loading={false} onLibrary={() => {}} />);
  expect(scrollTo).not.toHaveBeenCalled();
});

it("warns about likely pasted credentials while preserving the exact draft", async () => {
  const onSend = vi.fn();
  const user = userEvent.setup();
  render(<ChatPage chat={undefined} messages={[]} loading={false} onLibrary={() => {}} onSend={onSend} />);
  const text = `sk-ant-${"x".repeat(25)}`;
  const composer = screen.getByRole("textbox", { name: "Message" });
  await user.type(composer, text);
  expect(screen.getByRole("status")).toHaveTextContent("may contain an API key or secret");
  await user.keyboard("{Enter}");
  expect(onSend).toHaveBeenCalledWith(text);
});
