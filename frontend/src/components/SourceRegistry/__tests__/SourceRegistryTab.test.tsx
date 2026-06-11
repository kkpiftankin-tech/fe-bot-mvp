/**
 * Тесты SourceRegistryTab (SETUP-03 / T-S03-024).
 */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { SourceRegistryTab } from "../SourceRegistryTab";

describe("SourceRegistryTab", () => {
  it("renders tab with empty state initially", async () => {
    renderWithProviders(<SourceRegistryTab setupJobId="s_unknown" />);
    expect(screen.getByTestId("source-registry-tab")).toBeInTheDocument();
    // Loading или empty.
    await waitFor(() => {
      const empty = screen.queryByTestId("sources-empty");
      const loading = screen.queryByTestId("sources-loading");
      expect(empty || loading).toBeTruthy();
    });
  });

  it("renders status filter dropdown", () => {
    renderWithProviders(<SourceRegistryTab setupJobId="s1" />);
    expect(screen.getByTestId("source-status-filter")).toBeInTheDocument();
  });

  it("renders include_removed toggle", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SourceRegistryTab setupJobId="s1" />);
    const toggle = screen.getByTestId("include-removed-toggle") as HTMLInputElement;
    expect(toggle.checked).toBe(false);
    await user.click(toggle);
    expect(toggle.checked).toBe(true);
  });
});
