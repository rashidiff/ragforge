import { beforeEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LibraryPage } from "../src/pages/LibraryPage";
import { api } from "../src/lib/api";
import type { Document, IndexStatus } from "../src/lib/contracts";

vi.mock("../src/lib/api", () => ({ api: {
  library: vi.fn(), indexStatus: vi.fn(), uploadPdf: vi.fn(), reindexPdf: vi.fn(), deletePdf: vi.fn(), rebuildIndex: vi.fn(),
} }));

const document: Document = { document_id: "a", title: "Contrat.pdf", original_name: "Contrat.pdf", sha256: "hash", size_bytes: 100,
  page_count: 12, imported_at: "2026-11-12T10:00:00Z", status: "ready", warnings: [], index_version: "v1", error: null };
const status: IndexStatus = { ready: true, index_version: "v1", jobs: [], warnings: [], rebuild_required: false };

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.library).mockResolvedValue({ documents: [document] });
  vi.mocked(api.indexStatus).mockResolvedValue(status);
});

it("shows metadata and opens exact PDF page preview", async () => {
  const user = userEvent.setup();
  render(<LibraryPage />);
  expect(await screen.findByRole("heading", { name: "Contrat.pdf" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Preview" }));
  fireEvent.change(screen.getByRole("spinbutton", { name: "Page" }), { target: { value: "7" } });
  expect(screen.getByTitle("Contrat.pdf, page 7")).toHaveAttribute("src", "/api/library/a/pdf#page=7");
});

it("submits a selected PDF and preserves clear upload errors", async () => {
  const user = userEvent.setup();
  vi.mocked(api.uploadPdf).mockRejectedValue(new Error("This PDF is already in the Library"));
  render(<LibraryPage />);
  await screen.findByRole("heading", { name: "Contrat.pdf" });
  const file = new File(["%PDF-fixture"], "source.pdf", { type: "application/pdf" });
  await user.upload(screen.getByLabelText("Choose PDF file"), file);
  await waitFor(() => expect(api.uploadPdf).toHaveBeenCalledWith(file, expect.any(AbortSignal)));
  expect(await screen.findByRole("alert")).toHaveTextContent("already in the Library");
});

it("renders only real job progress and disables conflicting mutations", async () => {
  vi.mocked(api.indexStatus).mockResolvedValue({ ...status, jobs: [{ job_id: "job", kind: "upload", document_id: "a",
    stage: "embedding", processed: 32, total: 64, started_at: document.imported_at, finished_at: null, error: null }] });
  render(<LibraryPage />);
  expect(await screen.findByText(/Embedding locally/)).toBeVisible();
  expect(screen.getByText("32 / 64")).toBeVisible();
  expect(screen.getByRole("button", { name: "Upload PDF" })).toBeDisabled();
  expect(screen.queryByText(/Thinking/)).not.toBeInTheDocument();
});

it("supports drag and drop without interpreting the filename as markup", async () => {
  vi.mocked(api.uploadPdf).mockRejectedValue(new Error("Rejected fixture"));
  render(<LibraryPage />);
  await screen.findByRole("heading", { name: "Contrat.pdf" });
  const file = new File(["%PDF-fixture"], "<script>.pdf", { type: "application/pdf" });
  fireEvent.drop(screen.getByText(/Drop a PDF/).parentElement!, { dataTransfer: { files: [file] } });
  await waitFor(() => expect(api.uploadPdf).toHaveBeenCalled());
});
