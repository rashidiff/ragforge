import { expect, test } from "@playwright/test";

const pdfPath = process.env.RAG_E2E_PDF_PATH;
const question = process.env.RAG_E2E_QUESTION;
const expectedAnswer = process.env.RAG_E2E_EXPECTED_ANSWER;
const followup = process.env.RAG_E2E_FOLLOWUP;
const stopQuestion = process.env.RAG_E2E_STOP_QUESTION;

test("real PDF upload, grounded citations, follow-up, stop/retry, reload, and chat deletion", async ({ page, request }) => {
  const required = {
    RAG_E2E_PDF_PATH: pdfPath,
    RAG_E2E_QUESTION: question,
    RAG_E2E_EXPECTED_ANSWER: expectedAnswer,
    RAG_E2E_FOLLOWUP: followup,
    RAG_E2E_STOP_QUESTION: stopQuestion,
  };
  const missing = Object.entries(required).filter(([, value]) => !value).map(([name]) => name);
  expect(missing, `Set live end-to-end inputs: ${missing.join(", ")}`).toEqual([]);

  const [healthResponse, settingsResponse, priorChatsResponse] = await Promise.all([
    request.get("/api/health"), request.get("/api/settings"), request.get("/api/chats"),
  ]);
  expect(healthResponse.ok()).toBeTruthy();
  expect(settingsResponse.ok()).toBeTruthy();
  expect(priorChatsResponse.ok()).toBeTruthy();
  const settings = await settingsResponse.json() as { provider: string; model: string; has_key: boolean };
  expect(settings.has_key, "Configure a real provider key in Settings before the smoke").toBeTruthy();
  if (process.env.RAG_E2E_PROVIDER) expect(settings.provider).toBe(process.env.RAG_E2E_PROVIDER);
  if (process.env.RAG_E2E_MODEL) expect(settings.model).toBe(process.env.RAG_E2E_MODEL);
  const priorChats = await priorChatsResponse.json() as { chats: Array<{ chat_id: string }> };
  const priorIds = new Set(priorChats.chats.map((chat) => chat.chat_id));

  await page.goto("/");
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await page.locator('input[type="file"][accept*="application/pdf"]').setInputFiles(pdfPath!);
  await expect(page.locator(".document-status.ready").first()).toBeVisible({ timeout: 10 * 60 * 1000 });

  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(page.getByText("The key is never returned by the API.")).toBeVisible();
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  await expect.poll(async () => {
    const response = await request.get("/api/chats");
    const value = await response.json() as { chats: Array<{ chat_id: string }> };
    return value.chats.find((chat) => !priorIds.has(chat.chat_id))?.chat_id ?? "";
  }).not.toBe("");
  const afterCreate = await request.get("/api/chats");
  const createdChats = await afterCreate.json() as { chats: Array<{ chat_id: string }> };
  const createdChatId = createdChats.chats.find((chat) => !priorIds.has(chat.chat_id))!.chat_id;

  const composer = page.getByRole("textbox", { name: "Message" });
  await composer.fill(question!);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const firstAnswer = page.locator(".message.assistant").last();
  await expect(firstAnswer).toContainText(expectedAnswer!, { timeout: 3 * 60 * 1000 });
  const citation = firstAnswer.locator(".inline-citation").first();
  await expect(citation).toBeVisible();
  await citation.click();
  const sourceDialog = page.getByRole("dialog");
  await expect(sourceDialog.locator("iframe")).toBeVisible();
  await expect(sourceDialog.locator("blockquote")).not.toBeEmpty();
  await page.keyboard.press("Escape");
  await expect(sourceDialog).toBeHidden();

  await composer.fill(followup!);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".message.assistant")).toHaveCount(2, { timeout: 3 * 60 * 1000 });
  await expect(page.locator(".message.assistant").last().locator(".message-content")).not.toBeEmpty();

  await composer.fill(stopQuestion!);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const stop = page.getByRole("button", { name: "Stop", exact: true });
  await expect(stop).toBeVisible({ timeout: 60_000 });
  await stop.click();
  const retry = page.getByRole("button", { name: "Retry last response", exact: true });
  await expect(retry).toBeVisible({ timeout: 30_000 });
  await retry.click();
  const retryStop = page.getByRole("button", { name: "Stop", exact: true });
  await expect(retryStop).toBeVisible({ timeout: 30_000 });
  await expect(retryStop).toBeHidden({ timeout: 3 * 60 * 1000 });
  await expect(page.locator(".message.assistant").last().locator(".incomplete")).toHaveCount(0);

  await page.reload();
  await expect(page.getByRole("textbox", { name: "Message" })).toBeVisible();
  await expect(page.locator(".message.assistant").first()).toContainText(expectedAnswer!);
  await expect(page.locator(".message.user")).toContainText(stopQuestion!);

  const selectedRow = page.locator(".chat-list li.selected");
  await selectedRow.locator(".chat-actions button").last().click();
  const deleteDialog = page.getByRole("alertdialog");
  await deleteDialog.getByRole("button", { name: "Delete chat", exact: true }).click();
  await expect.poll(async () => {
    const response = await request.get("/api/chats");
    const value = await response.json() as { chats: Array<{ chat_id: string }> };
    return value.chats.some((chat) => chat.chat_id === createdChatId);
  }).toBe(false);
});
