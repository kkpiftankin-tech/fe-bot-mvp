/**
 * E2E-like flow tests: проходим весь wizard от create до report через MSW.
 *
 * Идёт строго по гранулярному пути мастера (3 → 4 → 5 → 6 → 7 → 8 → 9 → 10).
 * Legacy "Быстрый запуск" (/run) больше не часть навигации мастера — см.
 * wizardStore.ts и RunPipelineStep.tsx — поэтому этот тест его не использует.
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
  it(
    "end-to-end: create → upload → parse → generate → review → validation → chunking → tests → publish → report",
    async () => {
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
        expect(
          screen.getByTestId("uploaded-files-table"),
        ).toHaveTextContent("doc.md"),
      );
      await user.click(screen.getByTestId("continue-to-parse"));

      // --- Step 3: parsing
      await user.click(screen.getByTestId("create-parse-job"));
      await waitFor(() =>
        expect(screen.getByTestId("run-parse-job")).not.toBeDisabled(),
      );
      await user.click(screen.getByTestId("run-parse-job"));
      await waitFor(() =>
        expect(screen.getByTestId("parse-job-status")).toHaveTextContent(
          "completed",
        ),
      );
      await waitFor(() =>
        expect(
          screen.getByTestId("continue-to-rag-card-generation"),
        ).not.toBeDisabled(),
      );
      await user.click(screen.getByTestId("continue-to-rag-card-generation"));

      // --- Step 4: RAG card generation
      await user.click(screen.getByTestId("create-rag-card-job"));
      await waitFor(() =>
        expect(screen.getByTestId("run-rag-card-job")).not.toBeDisabled(),
      );
      await user.click(screen.getByTestId("run-rag-card-job"));
      await waitFor(() =>
        expect(screen.getByTestId("rag-card-job-status")).toHaveTextContent(
          "completed",
        ),
      );
      await waitFor(() =>
        expect(
          screen.getByTestId("continue-to-review-from-generation"),
        ).not.toBeDisabled(),
      );
      await user.click(screen.getByTestId("continue-to-review-from-generation"));

      // --- Step 5: review — approve the generated card
      await waitFor(() =>
        expect(screen.getByTestId("review-table")).toBeInTheDocument(),
      );
      await user.click(await screen.findByTestId("review-schema_card.x.v1"));
      await waitFor(() =>
        expect(screen.getByTestId("approve-btn")).toBeInTheDocument(),
      );
      await user.click(screen.getByTestId("approve-btn"));
      await waitFor(() =>
        expect(screen.getByTestId("pane-overview")).toHaveTextContent(
          "Status: approved",
        ),
      );
      await user.click(screen.getByTestId("close-drawer"));
      await user.click(screen.getByTestId("continue-to-validation"));

      // --- Step 6: validation (read-only панели, сразу идём дальше)
      await waitFor(() =>
        expect(screen.getByTestId("continue-to-chunking")).toBeInTheDocument(),
      );
      await user.click(screen.getByTestId("continue-to-chunking"));

      // --- Step 7: chunking + индексация
      await user.click(await screen.findByTestId("run-chunking"));
      await waitFor(() =>
        expect(screen.queryByTestId("no-manifest")).not.toBeInTheDocument(),
      );
      await user.click(screen.getByTestId("run-indexing"));
      await waitFor(() =>
        expect(screen.getByTestId("indexing-result")).toHaveTextContent(
          "Проиндексировано",
        ),
      );
      await user.click(screen.getByTestId("continue-to-tests-from-chunking"));

      // --- Step 8: retrieval-tests
      await user.type(screen.getByTestId("query-0"), "find x");
      await user.type(screen.getByTestId("expected-0"), "schema_card.x.v1");
      await user.click(screen.getByTestId("submit-eval"));
      await waitFor(() =>
        expect(screen.getByTestId("eval-banner")).toHaveTextContent("PASSED"),
      );
      await user.click(screen.getByTestId("continue-to-publish"));

      // --- Step 9: publish
      await user.click(await screen.findByTestId("submit-publish"));
      await waitFor(() =>
        expect(screen.getByTestId("published-status")).toHaveTextContent(
          "active",
        ),
      );
      await user.click(screen.getByTestId("continue-to-report"));

      // --- Step 10: report
      await waitFor(() =>
        expect(screen.getByTestId("report-banner")).toHaveTextContent(
          "Active KB",
        ),
      );
    },
    15000,
  );
});
