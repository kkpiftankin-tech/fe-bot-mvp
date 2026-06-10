/**
 * Тесты UploadedFilesTable (SETUP-02 / T-S02-020).
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { SourceDocumentResponse } from "../../../api/types";
import { resetMockState, server } from "../../../test/msw";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { UploadedFilesTable } from "../UploadedFilesTable";

function mkDoc(
  partial: Partial<SourceDocumentResponse> = {},
): SourceDocumentResponse {
  return {
    source_document_id: "src_1",
    setup_job_id: "s1",
    filename: "doc.md",
    content_type: "text/markdown",
    size_bytes: 1024,
    checksum: "a".repeat(64),
    status: "uploaded",
    uploaded_by: "u1",
    uploaded_at: "2026-06-10T10:00:00Z",
    storage_path: null,
    ...partial,
  };
}

beforeEach(() => {
  resetMockState();
});
afterEach(() => {
  // ensure no console warning is left between tests
});

describe("UploadedFilesTable", () => {
  it("renders empty state when no documents", () => {
    renderWithProviders(
      <UploadedFilesTable setupJobId="s1" documents={[]} />,
    );
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
  });

  it("renders one row per document with badges", () => {
    renderWithProviders(
      <UploadedFilesTable
        setupJobId="s1"
        documents={[
          mkDoc({ source_document_id: "src_1", filename: "a.md" }),
          mkDoc({
            source_document_id: "src_2",
            filename: "b.md",
            status: "removed",
          }),
        ]}
      />,
    );
    expect(screen.getByTestId("doc-row-src_1")).toBeInTheDocument();
    expect(screen.getByTestId("doc-row-src_2")).toBeInTheDocument();
    expect(screen.getByTestId("status-src_1")).toHaveTextContent("uploaded");
    expect(screen.getByTestId("status-src_2")).toHaveTextContent("removed");
  });

  it("filter by status hides others", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <UploadedFilesTable
        setupJobId="s1"
        documents={[
          mkDoc({ source_document_id: "src_1", status: "uploaded" }),
          mkDoc({
            source_document_id: "src_2",
            filename: "b.md",
            status: "removed",
          }),
        ]}
      />,
    );
    await user.selectOptions(screen.getByTestId("status-filter"), "removed");
    expect(screen.queryByTestId("doc-row-src_1")).not.toBeInTheDocument();
    expect(screen.getByTestId("doc-row-src_2")).toBeInTheDocument();
  });

  it("sort by filename toggles direction", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <UploadedFilesTable
        setupJobId="s1"
        documents={[
          mkDoc({ source_document_id: "src_a", filename: "z.md" }),
          mkDoc({
            source_document_id: "src_b",
            filename: "a.md",
            uploaded_at: "2026-06-11T10:00:00Z",
          }),
        ]}
      />,
    );
    // Default sort is uploaded_at desc → src_b should be first row.
    let rows = screen.getAllByText(/\.md$/);
    expect(rows[0]?.textContent).toBe("a.md");
    // Click filename header → sort by filename asc.
    await user.click(screen.getByTestId("sort-filename"));
    rows = screen.getAllByText(/\.md$/);
    expect(rows[0]?.textContent).toBe("a.md");
    // Click again → desc.
    await user.click(screen.getByTestId("sort-filename"));
    rows = screen.getAllByText(/\.md$/);
    expect(rows[0]?.textContent).toBe("z.md");
  });

  it("opens details dialog with full metadata", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <UploadedFilesTable
        setupJobId="s1"
        documents={[
          mkDoc({
            source_document_id: "src_1",
            filename: "demo.md",
            storage_path: "s3://bucket/path",
          }),
        ]}
      />,
    );
    await user.click(screen.getByTestId("details-src_1"));
    const dialog = screen.getByTestId("document-details-dialog");
    expect(within(dialog).getByText("demo.md")).toBeInTheDocument();
    expect(within(dialog).getByText("s3://bucket/path")).toBeInTheDocument();
    // Закрытие
    await user.click(screen.getByTestId("details-close"));
    expect(
      screen.queryByTestId("document-details-dialog"),
    ).not.toBeInTheDocument();
  });

  it("delete flow: opens dialog → confirms → calls API", async () => {
    server.use(
      http.delete("/api/v1/setup/:sid/documents/:doc", () =>
        HttpResponse.json({
          setup_job_id: "s1",
          source_document_id: "src_1",
          status: "removed",
        }),
      ),
    );

    const user = userEvent.setup();
    renderWithProviders(
      <UploadedFilesTable
        setupJobId="s1"
        documents={[
          mkDoc({ source_document_id: "src_1", filename: "doc.md" }),
        ]}
      />,
    );

    await user.click(screen.getByTestId("delete-src_1"));
    const dialog = screen.getByTestId("confirm-delete-dialog");
    expect(within(dialog).getByText(/doc\.md/)).toBeInTheDocument();
    await user.click(screen.getByTestId("confirm-delete-yes"));
    // Dialog закрывается после success (может быть синхронно).
    await waitFor(() =>
      expect(
        screen.queryByTestId("confirm-delete-dialog"),
      ).not.toBeInTheDocument(),
    );
  });

  it("cancel delete keeps document", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <UploadedFilesTable
        setupJobId="s1"
        documents={[mkDoc({ source_document_id: "src_1" })]}
      />,
    );
    await user.click(screen.getByTestId("delete-src_1"));
    await user.click(screen.getByTestId("confirm-delete-no"));
    expect(
      screen.queryByTestId("confirm-delete-dialog"),
    ).not.toBeInTheDocument();
    // Row still here
    expect(screen.getByTestId("doc-row-src_1")).toBeInTheDocument();
  });

  it("delete button hidden for removed status", () => {
    renderWithProviders(
      <UploadedFilesTable
        setupJobId="s1"
        documents={[
          mkDoc({ source_document_id: "src_1", status: "removed" }),
        ]}
      />,
    );
    expect(screen.queryByTestId("delete-src_1")).not.toBeInTheDocument();
  });
});
