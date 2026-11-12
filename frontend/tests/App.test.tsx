import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/app/App";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
  api: {
    modelCatalog: vi.fn(),
    selectModel: vi.fn(),
    chats: vi.fn(),
    health: vi.fn(),
    messages: vi.fn(),
    createChat: vi.fn(),
    compactionStatus: vi.fn(),
    retryCompaction: vi.fn(),
    renameChat: vi.fn(),
    deleteChat: vi.fn(),
    exportChat: vi.fn(),
    backupHistory: vi.fn(),
    library: vi.fn(),
    indexStatus: vi.fn(),
    streamMessage: vi.fn(),
  },
}));

const chat = {
  chat_id: "4fd02b08-6396-4a97-b146-2128cdfa8a96",
  title: "فارسی",
  created_at: "2026-11-12T10:00:00+00:00",
  updated_at: "2026-11-12T10:00:00+00:00",
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.modelCatalog).mockResolvedValue({ provider: "openai", current_model: "gpt-4.1", default_model: "gpt-4.1", models: [{id: "gpt-4.1", label: "GPT-4.1"}], source_url: null, reviewed_at: "2026-11-12" });
  window.localStorage.clear();
  document.documentElement.dir = "ltr";
  document.documentElement.lang = "en";
  vi.mocked(api.chats).mockResolvedValue({ chats: [chat] });
  vi.mocked(api.messages).mockResolvedValue({ messages: [] });
  vi.mocked(api.compactionStatus).mockResolvedValue({
    chat_id: chat.chat_id,
    state: "idle",
    summary_revision: 0,
    compacted_message_count: 0,
    pending_message_count: 0,
    batch_count: 0,
    retryable: false,
  });
  vi.mocked(api.library).mockResolvedValue({ documents: [] });
  vi.mocked(api.indexStatus).mockResolvedValue({
    index_version: null,
    ready: true,
    jobs: [],
    warnings: [],
    rebuild_required: false,
  });
  vi.mocked(api.health).mockResolvedValue({
    status: "ok",
    version: "0.1.0",
    storage_ready: true,
    index_ready: false,
    warnings: [],
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("foundation workspace", () => {
  it("loads chronological chats and navigates by keyboard", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByRole("button", { name: "فارسی" })).toBeVisible();
    const library = screen.getByRole("button", {
      name: "Library",
    });
    library.focus();
    await user.keyboard("{Enter}");
    expect(
      screen.getByRole("heading", { name: "Your documents, together." }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Upload PDF" })).toBeVisible();
  });

  it("creates and renames chats without replacing content", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createChat).mockResolvedValue({
      ...chat,
      chat_id: "new-id",
      title: "New chat",
    });
    vi.mocked(api.renameChat).mockResolvedValue({ ...chat, title: "Français" });
    render(<App />);
    await screen.findByRole("button", { name: "Rename فارسی" });
    await user.click(screen.getByRole("button", { name: "Rename فارسی" }));
    const input = screen.getByRole("textbox", { name: "Chat title" });
    await user.clear(input);
    await user.type(input, "Français");
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(api.renameChat).toHaveBeenCalledWith(chat.chat_id, "Français"),
    );
    await user.click(screen.getByRole("button", { name: "New chat" }));
    await waitFor(() => expect(api.createChat).toHaveBeenCalledOnce());
  });

  it("requires confirmation before deletion and keeps failures visible", async () => {
    const user = userEvent.setup();
    vi.mocked(api.deleteChat).mockRejectedValue(new Error("Disk unavailable"));
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Delete فارسی" }),
    );
    expect(api.deleteChat).not.toHaveBeenCalled();
    const dialog = screen.getByRole("alertdialog");
    await user.click(
      within(dialog).getByRole("button", { name: "Delete chat" }),
    );
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Disk unavailable",
    );
    expect(
      screen.getByRole("button", { name: "فارسی", hidden: true }),
    ).toBeInTheDocument();
  });

  it("renders untrusted historical messages as text, including incomplete labels", async () => {
    vi.mocked(api.messages).mockResolvedValue({
      messages: [
        {
          event_id: "event",
          chat_id: chat.chat_id,
          message_id: "message",
          request_id: "request",
          role: "assistant",
          content: '<img src=x onerror="alert(1)"> فارسی',
          completed: false,
          created_at: chat.created_at,
          metadata: {},
        },
      ],
    });
    render(<App />);
    expect(await screen.findByText(/<img src=x/)).toBeVisible();
    expect(document.querySelector(".message-content img")).toBeNull();
    expect(screen.getByText(/Interrupted answer/)).toBeVisible();
  });

  it("submits a question, displays actual stream deltas, and reloads saved history", async () => {
    const crypto = globalThis.crypto;
    vi.stubGlobal("crypto", {
      randomUUID: () => "client-message-id",
      getRandomValues: crypto.getRandomValues.bind(crypto),
      subtle: crypto.subtle,
    });
    vi.mocked(api.messages)
      .mockResolvedValueOnce({ messages: [] })
      .mockResolvedValueOnce({
        messages: [
          {
            event_id: "event",
            chat_id: chat.chat_id,
            message_id: "assistant-id",
            request_id: "request-id",
            role: "assistant",
            content: "The PDF answer",
            created_at: chat.created_at,
            completed: true,
            metadata: {},
          },
        ],
      });
    vi.mocked(api.streamMessage).mockImplementation(
      async (_chatId, _body, _signal, onEvent) => {
        onEvent({ event: "status", data: { label: "Calling provider" } });
        onEvent({ event: "token", data: { delta: "The PDF answer" } });
        onEvent({ event: "done", data: { complete: true } });
      },
    );
    const user = userEvent.setup();
    render(<App />);
    const composer = await screen.findByRole("textbox", { name: "Message" });
    await user.type(composer, "What does the PDF say?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("The PDF answer")).toBeVisible();
    expect(api.streamMessage).toHaveBeenCalledWith(
      chat.chat_id,
      {
        content: "What does the PDF say?",
        client_message_id: "client-message-id",
      },
      expect.any(AbortSignal),
      expect.any(Function),
    );
  });

  it("supports English and French preferences without a Persian interface option", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("button", { name: "New chat" });
    const language = screen.getByRole("combobox", { name: "Interface language" });
    expect(within(language).queryByRole("option", { name: "فارسی" })).toBeNull();
    await user.selectOptions(language, "fr");
    await waitFor(() => expect(document.documentElement.lang).toBe("fr"));
    expect(document.documentElement.dir).toBe("ltr");
    expect(window.localStorage.getItem("local-rag-locale")).toBe("fr");
    await user.selectOptions(screen.getByRole("combobox", { name: "Langue de l’interface" }), "en");
    await user.click(screen.getByRole("button", { name: "Use dark theme" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem("local-rag-theme")).toBe("dark");
    expect(screen.getByRole("button", { name: "New chat" })).toBeVisible();
  });

  it("migrates a stored Persian interface preference to English without changing Unicode chats", async () => {
    window.localStorage.setItem("local-rag-locale", "fa");
    render(<App />);
    expect(await screen.findByRole("button", { name: "فارسی" })).toBeVisible();
    expect(document.documentElement.lang).toBe("en");
    expect(document.documentElement.dir).toBe("ltr");
    expect(window.localStorage.getItem("local-rag-locale")).toBe("en");
  });
  it("warns before exporting a chat and downloads the selected format", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:export"),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.mocked(api.exportChat).mockResolvedValue(new Blob(["chat"]));
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Export as Markdown فارسی" }),
    );
    await waitFor(() =>
      expect(api.exportChat).toHaveBeenCalledWith(chat.chat_id, "markdown"),
    );
    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringContaining("verbatim"),
    );
  });

  it("opens mobile navigation and restores focus after Escape closes it", async () => {
    const user = userEvent.setup();
    render(<App />);
    const toggle = await screen.findByRole("button", {
      name: "Open navigation",
    });
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "New chat" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveFocus();
  });
});
