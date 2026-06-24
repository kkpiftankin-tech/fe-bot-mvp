import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../../../test/msw";
import { renderWithProviders } from "../../../../test/renderWithProviders";
import { ChunkPreviewPanel } from "../ChunkPreviewPanel";

const SID = "setup_test";

describe("ChunkPreviewPanel", () => {
  it("показывает сообщение если manifest не создан", async () => {
    server.use(
      http.get(`/api/v1/setup/${SID}/chunking/manifest`, () =>
        HttpResponse.json({ detail: "no manifest" }, { status: 404 }),
      ),
    );
    renderWithProviders(<ChunkPreviewPanel setupJobId={SID} />);
    await waitFor(() =>
      expect(screen.getByTestId("no-manifest")).toBeInTheDocument(),
    );
  });

  it("показывает по-type разбивку из manifest API", async () => {
    server.use(
      http.get(`/api/v1/setup/${SID}/chunking/manifest`, () =>
        HttpResponse.json({
          manifest_id: "m_001",
          setup_job_id: SID,
          total_chunks: 6,
          by_type: { summary: 2, definition: 2, metadata_summary: 2 },
          chunks: [
            {
              chunk_id: "a#summary#0",
              doc_id: "a",
              chunk_type: "summary",
              section_title: null,
              chunk_text: "...",
              embedding_text: "...",
              metadata: {},
              priority: 80,
              source_section_id: null,
              token_count: null,
              created_at: "2026-06-24T12:00:00Z",
              status: "created",
            },
          ],
          created_at: "2026-06-24T12:00:00Z",
          created_by: "u1",
        }),
      ),
    );
    renderWithProviders(<ChunkPreviewPanel setupJobId={SID} />);
    await waitFor(() => {
      const panel = screen.getByTestId("chunk-preview-panel");
      expect(panel.textContent).toContain("6");
      expect(panel.textContent).toContain("summary");
      expect(panel.textContent).toContain("definition");
      expect(panel.textContent).toContain("metadata_summary");
    });
  });

  it("кнопка 'Сгенерировать chunks' вызывает POST run", async () => {
    let runCalls = 0;
    server.use(
      http.get(`/api/v1/setup/${SID}/chunking/manifest`, () =>
        HttpResponse.json({ detail: "no" }, { status: 404 }),
      ),
      http.post(`/api/v1/setup/${SID}/chunking/run`, () => {
        runCalls++;
        return HttpResponse.json({
          chunking_run_id: "cr_1",
          setup_job_id: SID,
          manifest_id: "m_1",
          triggered_by: "u1",
          total_cards: 3,
          chunks_created: 9,
          duration_ms: 50,
          started_at: "2026-06-24T12:00:00Z",
          finished_at: "2026-06-24T12:00:00Z",
        });
      }),
    );
    renderWithProviders(<ChunkPreviewPanel setupJobId={SID} />);
    const user = userEvent.setup();
    const btn = await screen.findByTestId("run-chunking");
    await user.click(btn);
    await waitFor(() => expect(runCalls).toBe(1));
  });
});
