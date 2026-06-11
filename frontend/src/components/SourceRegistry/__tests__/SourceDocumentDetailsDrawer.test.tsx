/**
 * Тесты SourceDocumentDetailsDrawer (SETUP-03 / T-S03-025).
 */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { SourceDocumentDetailsDrawer } from "../SourceDocumentDetailsDrawer";

describe("SourceDocumentDetailsDrawer", () => {
  it("renders drawer with overview tab active by default", async () => {
    renderWithProviders(
      <SourceDocumentDetailsDrawer
        setupJobId="s1"
        sourceDocumentId="src_001"
        onClose={() => {}}
      />,
    );
    expect(screen.getByTestId("source-details-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("tab-panel-overview")).toBeInTheDocument();
  });

  it("switches to metadata tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <SourceDocumentDetailsDrawer
        setupJobId="s1"
        sourceDocumentId="src_001"
        onClose={() => {}}
      />,
    );
    await user.click(screen.getByTestId("tab-metadata"));
    expect(screen.getByTestId("tab-panel-metadata")).toBeInTheDocument();
  });

  it("switches to history tab and loads entries", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <SourceDocumentDetailsDrawer
        setupJobId="s1"
        sourceDocumentId="src_001"
        onClose={() => {}}
      />,
    );
    await user.click(screen.getByTestId("tab-history"));
    await waitFor(() => {
      expect(screen.getByTestId("history-list")).toBeInTheDocument();
    });
  });

  it("switches to log tab and loads entries", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <SourceDocumentDetailsDrawer
        setupJobId="s1"
        sourceDocumentId="src_001"
        onClose={() => {}}
      />,
    );
    await user.click(screen.getByTestId("tab-log"));
    await waitFor(() => {
      expect(screen.getByTestId("log-list")).toBeInTheDocument();
    });
  });

  it("switches to lineage tab", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <SourceDocumentDetailsDrawer
        setupJobId="s1"
        sourceDocumentId="src_001"
        onClose={() => {}}
      />,
    );
    await user.click(screen.getByTestId("tab-lineage"));
    await waitFor(() => {
      expect(screen.getByTestId("lineage-content")).toBeInTheDocument();
    });
  });

  it("calls onClose when Close button clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <SourceDocumentDetailsDrawer
        setupJobId="s1"
        sourceDocumentId="src_001"
        onClose={onClose}
      />,
    );
    await user.click(screen.getByTestId("details-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("has accessibility attributes", () => {
    renderWithProviders(
      <SourceDocumentDetailsDrawer
        setupJobId="s1"
        sourceDocumentId="src_001"
        onClose={() => {}}
      />,
    );
    const drawer = screen.getByTestId("source-details-drawer");
    expect(drawer).toHaveAttribute("role", "dialog");
    expect(drawer).toHaveAttribute("aria-modal", "true");
  });
});
