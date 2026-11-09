import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { server } from "../../../../test/msw";
import { renderWithProviders } from "../../../../test/renderWithProviders";
import { RAGCardReviewDrawer } from "../RAGCardReviewDrawer";

const SID = "setup_test";
const DOC = "task.x.v1";

function _details(metadata: Record<string, unknown>) {
  return {
    doc_id: DOC,
    card_version: "1.0",
    title: "X",
    doc_type: "task_card",
    status: "review_required",
    confidence_level: "high",
    metadata,
    body_markdown: "# X\nbody",
    source_trace: {},
    validation: { critical_errors: [], warnings: [] },
    review_log_count: 0,
    permissions: {
      can_approve: true,
      can_reject: true,
      can_edit: true,
      can_regenerate: true,
    },
  };
}

describe("RAGCardReviewDrawer structural summary", () => {
  it("shows heading_path + section title when present in metadata", async () => {
    server.use(
      http.get(`/api/v1/setup/${SID}/rag-cards-review/${DOC}`, () =>
        HttpResponse.json(
          _details({
            source_heading_path: ["CONTENTS"],
            source_section_title: "Multisensor Advantages",
          }),
        ),
      ),
    );
    renderWithProviders(
      <RAGCardReviewDrawer setupJobId={SID} docId={DOC} onClose={() => {}} />,
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("source-structure-summary"),
      ).toHaveTextContent('CONTENTS → "Multisensor Advantages"'),
    );
  });

  it("shows nothing when structure metadata is absent (older/legacy cards)", async () => {
    server.use(
      http.get(`/api/v1/setup/${SID}/rag-cards-review/${DOC}`, () =>
        HttpResponse.json(_details({})),
      ),
    );
    renderWithProviders(
      <RAGCardReviewDrawer setupJobId={SID} docId={DOC} onClose={() => {}} />,
    );
    await waitFor(() =>
      expect(screen.getByTestId("pane-overview")).toBeInTheDocument(),
    );
    expect(
      screen.queryByTestId("source-structure-summary"),
    ).not.toBeInTheDocument();
  });
});
