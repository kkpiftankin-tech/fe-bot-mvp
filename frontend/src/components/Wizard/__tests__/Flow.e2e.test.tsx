/**
 * E2E-like flow tests: проходим весь wizard от create до report через MSW.
 */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useWizardStore } from "../../../store/wizardStore";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { resetMockState } from "../../../test/msw";
import { WizardLayout } from "../WizardLayout";

beforeEach(() => {
  useWizardStore.getState().reset();
  resetMockState();
});
afterEach(() => useWizardStore.getState().reset());

describe("Wizard happy-path flow", () => {
  it("end-to-end: create → upload → run → review → tests → publish → report", async () => {
    renderWithProviders(<WizardLayout />);
    const user = userEvent.setup();

    // --- Step 1: create
    await user.type(screen.getByTestId("project-name"), "Demo KB");
    await user.click(screen.getByTestId("submit-create"));
    await waitFor(() =>
      expect(useWizardStore.getState().setupJobId).toMatch(/^setup_/),
    );

    // --- Step 2: upload (sample markdown)
    const file = new File(["# Schema\n\nbody"], "doc.md", {
      type: "text/markdown",
    });
    const fileInput = await screen.findByTestId("file-input");
    await user.upload(fileInput, file);
    await user.click(screen.getByTestId("submit-upload"));
    await waitFor(() =>
      expect(screen.getByTestId("doc-list")).toHaveTextContent("doc.md"),
    );

    // --- continue to step 3
    await user.click(screen.getByTestId("continue-to-run"));

    // --- Step 3: run pipeline
    await user.click(await screen.findByTestId("submit-run"));
    await waitFor(() =>
      expect(screen.getByTestId("result-final-status")).toHaveTextContent(
        "review_required",
      ),
    );

    // --- continue to step 4 (review)
    await user.click(screen.getByTestId("continue-to-review"));

    // --- Step 4: approve the card
    await waitFor(() =>
      expect(screen.getByTestId("card-list")).toBeInTheDocument(),
    );
    await user.click(screen.getByTestId("toggle-schema_card.x.v1"));
    await user.click(screen.getByTestId("approve-schema_card.x.v1"));
    await waitFor(() =>
      expect(screen.getByTestId("status-schema_card.x.v1")).toHaveTextContent(
        "approved",
      ),
    );

    // --- continue to tests
    await user.click(screen.getByTestId("continue-to-tests"));

    // --- Step 5: retrieval-tests
    await user.type(screen.getByTestId("query-0"), "find x");
    await user.type(screen.getByTestId("expected-0"), "schema_card.x.v1");
    await user.click(screen.getByTestId("submit-eval"));
    await waitFor(() =>
      expect(screen.getByTestId("eval-banner")).toHaveTextContent("PASSED"),
    );

    // --- continue to publish
    await user.click(screen.getByTestId("continue-to-publish"));

    // --- Step 6: publish
    await user.click(await screen.findByTestId("submit-publish"));
    await waitFor(() =>
      expect(screen.getByTestId("published-status")).toHaveTextContent("active"),
    );

    // --- continue to report
    await user.click(screen.getByTestId("continue-to-report"));

    // --- Step 7: report
    await waitFor(() =>
      expect(screen.getByTestId("report-banner")).toHaveTextContent(
        "Active KB",
      ),
    );
  }, 15000);
});
