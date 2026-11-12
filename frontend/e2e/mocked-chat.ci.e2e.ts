import { expect, test } from "@playwright/test";

const chatId = "4fd02b08-6396-4a97-b146-2128cdfa8a96";
const userId = "1fd02b08-6396-4a97-b146-2128cdfa8a96";
const assistantId = "2fd02b08-6396-4a97-b146-2128cdfa8a96";
const requestId = "3fd02b08-6396-4a97-b146-2128cdfa8a96";
const now = "2026-11-12T12:00:00+00:00";

test("chat UI renders a mocked streamed answer and reloads saved history", async ({ page }) => {
  let selectedModel = "gpt-4.1";
  const requestBodies: unknown[] = [];
  let savedMessages: Array<Record<string, unknown>> = [];

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());

    if (pathname === "/api/settings/models") {
      await route.fulfill({json: {provider: "openai", current_model: selectedModel,
        default_model: "gpt-4.1", reviewed_at: "2026-11-12", source_url: null,
        models: [{id: "gpt-4.1", label: "GPT-4.1"}, {id: "gpt-4.1-mini", label: "GPT-4.1 mini"}]}});
      return;
    }
    if (pathname === "/api/settings/model" && request.method() === "PUT") {
      selectedModel = request.postDataJSON().model;
      await route.fulfill({json: {provider: "openai", model: selectedModel}});
      return;
    }
    if (pathname === "/api/health") {
      await route.fulfill({ json: {
        status: "ok", version: "ci", storage_ready: true, index_ready: true, warnings: [],
      } });
      return;
    }
    if (pathname === "/api/chats" && request.method() === "GET") {
      await route.fulfill({ json: { chats: [{
        chat_id: chatId, title: "CI conversation", created_at: now, updated_at: now,
      }] } });
      return;
    }
    if (pathname === `/api/chats/${chatId}/compaction`) {
      await route.fulfill({ json: {
        chat_id: chatId, state: "idle", summary_revision: 0,
        compacted_message_count: 0, pending_message_count: 0,
        batch_count: 0, retryable: false,
      } });
      return;
    }
    if (pathname === `/api/chats/${chatId}/messages` && request.method() === "GET") {
      await route.fulfill({ json: { messages: savedMessages } });
      return;
    }
    if (pathname === `/api/chats/${chatId}/messages/stream` && request.method() === "POST") {
      requestBodies.push(request.postDataJSON());
      savedMessages = [
        { event_id: userId, chat_id: chatId, message_id: userId, request_id: requestId,
          role: "user", content: "What is the CI answer?", created_at: now,
          completed: true, metadata: {} },
        { event_id: assistantId, chat_id: chatId, message_id: assistantId,
          request_id: requestId, role: "assistant", content: "The mocked answer is available.",
          created_at: now, completed: true, metadata: {} },
      ];
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream; charset=utf-8",
        body: [
          `event: status\ndata: ${JSON.stringify({ label: "Preparing request" })}\n\n`,
          `event: token\ndata: ${JSON.stringify({ request_id: requestId,
            delta: "The mocked answer is available." })}\n\n`,
          `event: done\ndata: ${JSON.stringify({ request_id: requestId,
            message_id: assistantId, complete: true })}\n\n`,
        ].join(""),
      });
      return;
    }
    await route.fulfill({ status: 404, json: { error: { code: "not_found", message: pathname } } });
  });

  await page.goto("/");
  const modelMenu = page.getByRole("combobox", {name: "LLM model"});
  await expect(modelMenu).toHaveValue("gpt-4.1");
  await modelMenu.selectOption("gpt-4.1-mini");
  await expect(modelMenu).toHaveValue("gpt-4.1-mini");
  const composer = page.getByRole("textbox", { name: "Message" });
  await expect(composer).toBeVisible();
  await composer.fill("What is the CI answer?");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  await expect(page.getByText("The mocked answer is available.")).toBeVisible();
  await expect.poll(() => requestBodies).toHaveLength(1);
  expect(requestBodies[0]).toMatchObject({ content: "What is the CI answer?" });
  await expect(page.locator(".message.assistant")).toContainText("The mocked answer is available.");
});
