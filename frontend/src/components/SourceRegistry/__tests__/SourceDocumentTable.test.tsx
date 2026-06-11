/**
 * Тесты SourceDocumentTable (SETUP-03 / T-S03-024).
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type {
  SourceDocumentListItemDTO,
  SourceDocumentStatus,
} from "../../../api/types";
import { SourceDocumentTable } from "../SourceDocumentTable";

function mkItem(
  overrides: Partial<SourceDocumentListItemDTO> = {},
): SourceDocumentListItemDTO {
  return {
    source_document_id: "src_001",
    setup_job_id: "s1",
    filename: "doc.md",
    document_kind: null,
    content_type: "text/markdown",
    size_bytes: 1024,
    checksum_short: "abc123def456",
    status: "registered" as SourceDocumentStatus,
    uploaded_by: "u1",
    uploaded_at: "2026-06-11T10:00:00Z",
    parsed_sections_count: 0,
    rag_cards_count: 0,
    chunks_count: 0,
    last_error: null,
    ...overrides,
  };
}

describe("SourceDocumentTable", () => {
  it("renders empty state when no items", () => {
    render(
      <SourceDocumentTable
        items={[]}
        onDetails={() => {}}
      />,
    );
    expect(screen.getByTestId("sources-empty")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    render(
      <SourceDocumentTable items={[]} onDetails={() => {}} loading />,
    );
    expect(screen.getByTestId("sources-loading")).toBeInTheDocument();
  });

  it("renders one row per item with status badge", () => {
    render(
      <SourceDocumentTable
        items={[
          mkItem({ source_document_id: "src_A", status: "registered" }),
          mkItem({ source_document_id: "src_B", status: "parse_failed" }),
        ]}
        onDetails={() => {}}
      />,
    );
    expect(screen.getByTestId("source-row-src_A")).toBeInTheDocument();
    expect(screen.getByTestId("source-row-src_B")).toBeInTheDocument();
    expect(screen.getByTestId("source-status-src_A")).toHaveTextContent(
      "registered",
    );
    expect(screen.getByTestId("source-status-src_B")).toHaveTextContent(
      "parse_failed",
    );
  });

  it("shows error message when last_error set", () => {
    render(
      <SourceDocumentTable
        items={[mkItem({ last_error: "Parser timeout" })]}
        onDetails={() => {}}
      />,
    );
    expect(screen.getByTestId("source-error-src_001")).toHaveTextContent(
      "Parser timeout",
    );
  });

  it("calls onDetails when Details clicked", async () => {
    const onDetails = vi.fn();
    const user = userEvent.setup();
    render(
      <SourceDocumentTable items={[mkItem()]} onDetails={onDetails} />,
    );
    await user.click(screen.getByTestId("source-details-src_001"));
    expect(onDetails).toHaveBeenCalledWith("src_001");
  });

  it("shows Retry button only for retryable statuses", () => {
    const onRetry = vi.fn();
    const { rerender } = render(
      <SourceDocumentTable
        items={[mkItem({ status: "registered" })]}
        onDetails={() => {}}
        onRetry={onRetry}
      />,
    );
    expect(screen.queryByTestId("source-retry-src_001")).not.toBeInTheDocument();
    rerender(
      <SourceDocumentTable
        items={[mkItem({ status: "parse_failed" })]}
        onDetails={() => {}}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByTestId("source-retry-src_001")).toBeInTheDocument();
  });

  it("hides Delete button for published documents", () => {
    const onDelete = vi.fn();
    render(
      <SourceDocumentTable
        items={[mkItem({ status: "published" })]}
        onDetails={() => {}}
        onDelete={onDelete}
      />,
    );
    expect(screen.queryByTestId("source-delete-src_001")).not.toBeInTheDocument();
  });

  it("hides Delete button for already-removed documents", () => {
    const onDelete = vi.fn();
    render(
      <SourceDocumentTable
        items={[mkItem({ status: "removed" })]}
        onDetails={() => {}}
        onDelete={onDelete}
      />,
    );
    expect(screen.queryByTestId("source-delete-src_001")).not.toBeInTheDocument();
  });

  it("calls onDelete with id when clicked", async () => {
    const onDelete = vi.fn();
    const user = userEvent.setup();
    render(
      <SourceDocumentTable
        items={[mkItem()]}
        onDetails={() => {}}
        onDelete={onDelete}
      />,
    );
    await user.click(screen.getByTestId("source-delete-src_001"));
    expect(onDelete).toHaveBeenCalledWith("src_001");
  });
});
