import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../../../test/msw";
import { renderWithProviders } from "../../../../test/renderWithProviders";
import { ValidationSummaryCard } from "../ValidationSummaryCard";

const SID = "setup_test";

function summaryResponse(overrides: Partial<{
  total: number;
  passed: number;
  warnings: number;
  failed: number;
  review_required: number;
  last_run_id: string | null;
}> = {}) {
  return {
    setup_job_id: SID,
    total: 0,
    passed: 0,
    warnings: 0,
    failed: 0,
    review_required: 0,
    by_code: {},
    last_run_id: null,
    ...overrides,
  };
}

describe("ValidationSummaryCard", () => {
  it("показывает счётчики из summary API", async () => {
    server.use(
      http.get(`/api/v1/setup/${SID}/validation/summary`, () =>
        HttpResponse.json(
          summaryResponse({
            total: 5,
            passed: 4,
            warnings: 1,
            last_run_id: "run_001",
          }),
        ),
      ),
    );
    renderWithProviders(<ValidationSummaryCard setupJobId={SID} />);
    await waitFor(() =>
      expect(screen.getByTestId("validation-summary")).toBeInTheDocument(),
    );
    // Summary line содержит strong с "5" внутри текста "Всего: 5 · ...".
    await waitFor(() => {
      const summaryEl = screen.getByTestId("validation-summary");
      expect(summaryEl.textContent).toContain("Всего:");
      expect(summaryEl.textContent).toContain("5");
      expect(summaryEl.textContent).toContain("run_001");
    });
  });

  it("кнопка 'Запустить валидацию' вызывает POST run", async () => {
    let runCalls = 0;
    server.use(
      http.get(`/api/v1/setup/${SID}/validation/summary`, () =>
        HttpResponse.json(summaryResponse()),
      ),
      http.post(`/api/v1/setup/${SID}/validation/run`, () => {
        runCalls++;
        return HttpResponse.json({
          validation_run_id: "run_abc",
          setup_job_id: SID,
          status: "completed",
          triggered_by: "u1",
          policy: "strict",
          total: 3,
          passed: 3,
          warnings: 0,
          failed: 0,
          review_required: 0,
          started_at: "2026-06-23T12:00:00Z",
          finished_at: "2026-06-23T12:00:01Z",
          duration_ms: 1000,
        });
      }),
    );
    renderWithProviders(<ValidationSummaryCard setupJobId={SID} />);
    const user = userEvent.setup();
    const runBtn = await screen.findByTestId("run-validation");
    await user.click(runBtn);
    await waitFor(() => expect(runCalls).toBe(1));
  });

  it("обрабатывает ошибку API", async () => {
    server.use(
      http.get(`/api/v1/setup/${SID}/validation/summary`, () =>
        HttpResponse.json({ detail: "server error" }, { status: 500 }),
      ),
    );
    renderWithProviders(<ValidationSummaryCard setupJobId={SID} />);
    await waitFor(() => {
      const banner = screen.queryByText(/server error|Ошибка/);
      expect(banner).toBeInTheDocument();
    });
  });
});
