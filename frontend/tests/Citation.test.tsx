import { expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPage } from "../src/pages/ChatPage";
import { api } from "../src/lib/api";
import type { Chat, Message, SourceDetail } from "../src/lib/contracts";

vi.mock("../src/lib/api", () => ({ api: { sourceExcerpt: vi.fn() } }));

const chat: Chat = { chat_id: "chat", title: "Guide", created_at: "now", updated_at: "now" };
const citation = { chunk_id: "chunk-1", document_id: "doc-1", filename: "Guide.pdf", page_start: 7,
  page_end: 7, url: "/api/library/doc-1/pdf#page=7" };
const message: Message = { event_id: "event", chat_id: "chat", message_id: "message", request_id: "request",
  role: "assistant", content: "The deadline is 15 days. [[source:chunk-1]]", created_at: "now", completed: true,
  metadata: { citations: [citation] } };

it("renders validated source markers as citations and opens the exact-page source drawer", async () => {
  const source: SourceDetail = { ...citation, text: "The deadline is fifteen days.", index_version: "v1", available: true };
  vi.mocked(api.sourceExcerpt).mockResolvedValue(source);
  const user = userEvent.setup();
  render(<ChatPage chat={chat} messages={[message]} loading={false} onLibrary={() => {}} />);
  await user.click(screen.getByRole("button", { name: "Open source Guide.pdf, page 7" }));
  expect(await screen.findByRole("dialog", { name: "Source: Guide.pdf" })).toBeVisible();
  expect(await screen.findByText("The deadline is fifteen days.")).toBeVisible();
  expect(screen.getByTitle("Guide.pdf, page 7")).toHaveAttribute("src", source.url);
  expect(api.sourceExcerpt).toHaveBeenCalledWith("doc-1", "chunk-1", expect.any(AbortSignal));
});

it("does not turn an unvalidated citation marker into a source link", () => {
  render(<ChatPage chat={chat} messages={[{ ...message, metadata: { citations: [] } }]}
    loading={false} onLibrary={() => {}} />);
  expect(screen.queryByRole("button", { name: /Open source/ })).toBeNull();
  expect(screen.getByText(/\[\[source:chunk-1\]\]/)).toBeVisible();
});

it("copies the assistant's exact answer text", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
  const user = userEvent.setup({ writeToClipboard: false });
  render(<ChatPage chat={chat} messages={[message]} loading={false} onLibrary={() => {}} />);
  await user.click(screen.getByRole("button", { name: "Copy answer" }));
  expect(writeText).toHaveBeenCalledWith(message.content);
});
