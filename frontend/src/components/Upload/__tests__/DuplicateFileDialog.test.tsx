/**
 * Тесты DuplicateFileDialog (SETUP-02 / T-S02-022).
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { SourceDocumentResponse } from "../../../api/types";
import { DuplicateFileDialog } from "../DuplicateFileDialog";

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
    ...partial,
  };
}

describe("DuplicateFileDialog", () => {
  it("renders nothing if no duplicates", () => {
    const { container } = render(
      <DuplicateFileDialog duplicates={[]} onClose={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders list of duplicates with existing ids", () => {
    render(
      <DuplicateFileDialog
        duplicates={[
          mkDoc({ source_document_id: "existing_1", filename: "a.md" }),
          mkDoc({ source_document_id: "existing_2", filename: "b.md" }),
        ]}
        onClose={() => {}}
      />,
    );
    expect(screen.getByTestId("duplicate-file-dialog")).toBeInTheDocument();
    const list = screen.getByTestId("duplicate-list");
    expect(list).toHaveTextContent("a.md");
    expect(list).toHaveTextContent("b.md");
    expect(list).toHaveTextContent("existing_1");
    expect(list).toHaveTextContent("existing_2");
  });

  it("does not show feature flags by default (MVP)", () => {
    render(
      <DuplicateFileDialog
        duplicates={[mkDoc()]}
        onClose={() => {}}
      />,
    );
    expect(
      screen.queryByTestId("action-new-version"),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("action-replace")).not.toBeInTheDocument();
  });

  it("shows feature flags when enabled", () => {
    render(
      <DuplicateFileDialog
        duplicates={[mkDoc()]}
        onClose={() => {}}
        enableUploadAsNewVersion
        enableReplaceExisting
      />,
    );
    expect(screen.getByTestId("action-new-version")).toBeInTheDocument();
    expect(screen.getByTestId("action-replace")).toBeInTheDocument();
  });

  it("calls onClose when default button clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <DuplicateFileDialog duplicates={[mkDoc()]} onClose={onClose} />,
    );
    await user.click(screen.getByTestId("dup-dialog-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when backdrop clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <DuplicateFileDialog duplicates={[mkDoc()]} onClose={onClose} />,
    );
    await user.click(screen.getByTestId("duplicate-file-dialog"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("is accessible: dialog role + aria-modal + label", () => {
    render(
      <DuplicateFileDialog duplicates={[mkDoc()]} onClose={() => {}} />,
    );
    const dialog = screen.getByTestId("duplicate-file-dialog");
    expect(dialog).toHaveAttribute("role", "dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-labelledby");
  });
});
