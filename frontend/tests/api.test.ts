import { afterEach, expect, it, vi } from "vitest";
import { ApiError, api } from "../src/lib/api";

afterEach(() => vi.unstubAllGlobals());

it("handles 204 without parsing an empty JSON response", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
  await expect(api.deleteChat("id")).resolves.toBeUndefined();
});

it("preserves safe API error categories for retry UI", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    error: { code: "storage_error", message: "Check disk access" },
  }), { status: 500 })));
  await expect(api.chats()).rejects.toMatchObject({
    name: "ApiError", code: "storage_error", status: 500, message: "Check disk access",
  });
});

it("requests Markdown and coherent raw-history downloads as blobs", async () => {
  const payload = "Exact فارسی\n";
  const fetchMock = vi.fn().mockResolvedValue(new Response(payload, { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  expect(await (await api.exportChat("chat/id", "markdown")).text()).toBe(payload);
  expect(fetchMock).toHaveBeenLastCalledWith("/api/chats/chat%2Fid/export?format=markdown");
  expect(await (await api.backupHistory()).text()).toBe(payload);
  expect(fetchMock).toHaveBeenLastCalledWith("/api/history/backup");
});
