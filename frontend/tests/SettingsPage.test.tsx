import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SettingsPage } from "../src/pages/SettingsPage";
import { api } from "../src/lib/api";
import type { AppSettings } from "../src/lib/contracts";

vi.mock("../src/lib/api", () => ({
  api: {
    settings: vi.fn(),
    updateSettings: vi.fn(),
    testProviderConnection: vi.fn(),
  },
}));

const configured: AppSettings = {
  provider: "openai",
  model: "model-one",
  context_tokens: 16000,
  output_tokens: 2000,
  embedding_model: "local-model",
  embedding_revision: null,
  ocr_enabled: false,
  ocr_languages: "eng+fra+fas",
  compatible_base_url: null,
  compatible_tools: false,
  compatible_usage: false,
  has_key: false,
  persistence_mode: "session",
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.settings).mockResolvedValue(configured);
});

it("loads settings, clears entered key after save, and never persists without opt-in", async () => {
  vi.mocked(api.updateSettings).mockResolvedValue({
    ...configured,
    has_key: true,
  });
  const user = userEvent.setup();
  render(<SettingsPage />);
  await screen.findByLabelText("Provider");
  expect(screen.queryByLabelText("Model name")).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("API key"), "session-key");
  await user.click(screen.getByRole("button", { name: "Save settings" }));
  await waitFor(() =>
    expect(api.updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({ api_key: "session-key" }),
    ),
  );
  expect(api.updateSettings).not.toHaveBeenCalledWith(
    expect.objectContaining({ persist_key: true }),
  );
  expect(await screen.findByLabelText("API key")).toHaveValue("");
});

it("tests the configured provider and displays a real success response", async () => {
  vi.mocked(api.settings).mockResolvedValue({ ...configured, has_key: true });
  vi.mocked(api.testProviderConnection).mockResolvedValue({
    provider: "openai",
    model: "model-one",
    connected: true,
    capabilities: { streaming: true },
  });
  const user = userEvent.setup();
  render(<SettingsPage />);
  await user.click(
    await screen.findByRole("button", { name: "Test connection" }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Connected to openai using model-one",
  );
});

it("configures an explicit OpenAI Responses-compatible endpoint and capability flags", async () => {
  vi.mocked(api.updateSettings).mockResolvedValue({
    ...configured,
    provider: "openai_compatible",
    compatible_base_url: "https://llm.example/v1",
    compatible_tools: true,
    compatible_usage: true,
  });
  const user = userEvent.setup();
  render(<SettingsPage />);
  await user.selectOptions(
    await screen.findByLabelText("Provider"),
    "openai_compatible",
  );
  await user.type(
    screen.getByLabelText("Responses API base URL"),
    "https://llm.example/v1",
  );
  await user.click(
    screen.getByLabelText("Endpoint supports the configured Library tools"),
  );
  await user.click(screen.getByLabelText("Endpoint reports token usage"));
  await user.click(screen.getByRole("button", { name: "Save settings" }));
  await waitFor(() =>
    expect(api.updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: "openai_compatible",
        compatible_base_url: "https://llm.example/v1",
        compatible_tools: true,
        compatible_usage: true,
      }),
    ),
  );
});

it("allows explicit OS-keyring opt-in and key removal", async () => {
  vi.mocked(api.updateSettings).mockResolvedValue({
    ...configured,
    has_key: true,
    persistence_mode: "keyring",
  });
  const user = userEvent.setup();
  render(<SettingsPage />);
  await user.type(await screen.findByLabelText("API key"), "saved-key");
  await user.click(
    screen.getByLabelText("Save key in the OS credential vault"),
  );
  await user.click(screen.getByRole("button", { name: "Save settings" }));
  await waitFor(() =>
    expect(api.updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        api_key: "saved-key",
        persist_key: true,
      }),
    ),
  );
  vi.mocked(api.updateSettings).mockResolvedValue({
    ...configured,
    has_key: false,
  });
  await user.click(await screen.findByRole("button", { name: "Remove key" }));
  expect(api.updateSettings).toHaveBeenLastCalledWith({
    provider: "openai",
    remove_key: true,
  });
});
