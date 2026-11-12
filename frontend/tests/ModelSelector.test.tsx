import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelSelector } from "../src/components/ModelSelector";
import { api } from "../src/lib/api";
import type { AppSettings, ModelCatalog } from "../src/lib/contracts";

vi.mock("../src/lib/api", () => ({
  api: { modelCatalog: vi.fn(), selectModel: vi.fn() },
}));
const catalog: ModelCatalog = {
  provider: "openai",
  current_model: "gpt-4.1",
  default_model: "gpt-4.1",
  models: [
    { id: "gpt-4.1", label: "GPT-4.1" },
    { id: "gpt-4.1-mini", label: "GPT-4.1 mini" },
  ],
  source_url: "https://developers.openai.com/api/docs/models",
  reviewed_at: "2026-11-12",
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.modelCatalog).mockResolvedValue(catalog);
  vi.mocked(api.selectModel).mockResolvedValue({
    model: "gpt-4.1-mini",
  } as AppSettings);
});

it("lists documented models and persists the model chosen in the chat header", async () => {
  const pending = vi.fn();
  const user = userEvent.setup();
  render(<ModelSelector disabled={false} onPendingChange={pending} />);
  const select = await screen.findByRole("combobox", { name: "LLM model" });
  await waitFor(() => expect(select).toHaveValue("gpt-4.1"));
  await user.selectOptions(select, "gpt-4.1-mini");
  await waitFor(() => expect(select).toHaveValue("gpt-4.1-mini"));
  expect(api.selectModel).toHaveBeenCalledWith({
    provider: "openai",
    model: "gpt-4.1-mini",
  });
  expect(pending).toHaveBeenNthCalledWith(1, true);
  expect(pending).toHaveBeenLastCalledWith(false);
});

it("retains the previous model and exposes errors when saving fails", async () => {
  vi.mocked(api.selectModel).mockRejectedValue(new Error("Provider changed"));
  const user = userEvent.setup();
  render(<ModelSelector disabled={false} onPendingChange={vi.fn()} />);
  const select = screen.getByRole("combobox", { name: "LLM model" });
  await waitFor(() => expect(select).toHaveValue("gpt-4.1"));
  await user.selectOptions(select, "gpt-4.1-mini");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Provider changed",
  );
  expect(select).toHaveValue("gpt-4.1");
});

it("disables switching during a response", async () => {
  render(<ModelSelector disabled={true} onPendingChange={vi.fn()} />);
  await screen.findByRole("option", { name: "GPT-4.1 mini" });
  expect(screen.getByRole("combobox", { name: "LLM model" })).toBeDisabled();
});

it("allows custom endpoint model IDs in the chat rather than Settings", async () => {
  vi.mocked(api.modelCatalog).mockResolvedValue({
    ...catalog,
    provider: "openai_compatible",
    current_model: "",
    models: [],
    source_url: null,
  });
  vi.mocked(api.selectModel).mockResolvedValue({
    model: "local/my-model",
  } as AppSettings);
  const user = userEvent.setup();
  render(<ModelSelector disabled={false} onPendingChange={vi.fn()} />);
  await waitFor(() =>
    expect(screen.getByRole("combobox", { name: "LLM model" })).toBeEnabled(),
  );
  await user.selectOptions(
    screen.getByRole("combobox", { name: "LLM model" }),
    "__custom__",
  );
  await user.type(screen.getByLabelText("Custom model ID"), "local/my-model");
  await user.click(screen.getByRole("button", { name: "Use model" }));
  await waitFor(() =>
    expect(api.selectModel).toHaveBeenCalledWith({
      provider: "openai_compatible",
      model: "local/my-model",
    }),
  );
});

it("can retry catalog loading without exposing credentials", async () => {
  vi.mocked(api.modelCatalog).mockRejectedValueOnce(new Error("Offline"));
  const user = userEvent.setup();
  render(<ModelSelector disabled={false} onPendingChange={vi.fn()} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Offline");
  await user.click(screen.getByRole("button", { name: "Reload models" }));
  await waitFor(() =>
    expect(screen.getByRole("combobox", { name: "LLM model" })).toHaveValue(
      "gpt-4.1",
    ),
  );
});
