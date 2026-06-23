import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../../../test/msw";
import { renderWithProviders } from "../../../../test/renderWithProviders";
import { RAGCardReviewTable } from "../RAGCardReviewTable";

const SID = "setup_test";

function makeListResponse(items: unknown[]) {
  return {
    setup_job_id: SID,
    items,
    total: items.length,
    page: 1,
    page_size: 20,
    summary: { total: items.length, by_status: {} },
  };
}

describe("RAGCardReviewTable", () => {
  it("показывает empty state, когда карточек нет", async () => {
    server.use(
      http.get(`/api/v1/setup/${SID}/rag-cards-review`, () =>
        HttpResponse.json(makeListResponse([])),
      ),
    );
    renderWithProviders(<RAGCardReviewTable setupJobId={SID} onSelect={() => {}} />);
    await waitFor(() =>
      expect(screen.getByTestId("empty-state")).toBeInTheDocument(),
    );
  });

  it("рендерит карточки из ответа API", async () => {
    server.use(
      http.get(`/api/v1/setup/${SID}/rag-cards-review`, () =>
        HttpResponse.json(
          makeListResponse([
            {
              doc_id: "schema.x.v1",
              card_version: "1.0",
              title: "Test card",
              doc_type: "schema_card",
              status: "review_required",
              confidence_level: "high",
              source_document_id: "src_1",
              source_section_id: "sec_1",
              validation_errors_count: 0,
              warnings_count: 0,
              review_required_reason: null,
              last_reviewed_by: null,
              updated_at: "2026-06-23T12:00:00Z",
            },
          ]),
        ),
      ),
    );
    renderWithProviders(<RAGCardReviewTable setupJobId={SID} onSelect={() => {}} />);
    await waitFor(() => expect(screen.getByText("Test card")).toBeInTheDocument());
    expect(screen.getByTestId("review-schema.x.v1")).toBeInTheDocument();
  });

  it("фильтр status передаётся в API", async () => {
    let lastUrl = "";
    server.use(
      http.get(`/api/v1/setup/${SID}/rag-cards-review`, ({ request }) => {
        lastUrl = request.url;
        return HttpResponse.json(makeListResponse([]));
      }),
    );
    renderWithProviders(<RAGCardReviewTable setupJobId={SID} onSelect={() => {}} />);
    await waitFor(() => expect(lastUrl).toContain("status=review_required"));

    const user = userEvent.setup();
    await user.selectOptions(screen.getByTestId("filter-status"), "approved");
    await waitFor(() => expect(lastUrl).toContain("status=approved"));
  });

  it("клик по 'Открыть' вызывает onSelect", async () => {
    server.use(
      http.get(`/api/v1/setup/${SID}/rag-cards-review`, () =>
        HttpResponse.json(
          makeListResponse([
            {
              doc_id: "schema.y.v1",
              card_version: "1.0",
              title: "Y",
              doc_type: "schema_card",
              status: "review_required",
              confidence_level: null,
              source_document_id: null,
              source_section_id: null,
              validation_errors_count: 0,
              warnings_count: 0,
              review_required_reason: null,
              last_reviewed_by: null,
              updated_at: "2026-06-23T12:00:00Z",
            },
          ]),
        ),
      ),
    );
    const onSelect = vi.fn();
    renderWithProviders(<RAGCardReviewTable setupJobId={SID} onSelect={onSelect} />);
    const user = userEvent.setup();
    const btn = await screen.findByTestId("review-schema.y.v1");
    await user.click(btn);
    expect(onSelect).toHaveBeenCalledWith("schema.y.v1");
  });
});
