import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type {
  EvalReportResponse,
  ListCardsResponse,
  ListDocumentsResponse,
  ProcessingReportResponse,
  PublishKBResponse,
  ReviewRAGCardResponse,
  RunPipelineResponse,
  SetupJobResponse,
  SetupProgressResponse,
  SourceDocumentResponse,
  UploadDocumentsResponse,
} from "../api/types";

interface MockJob {
  setup_job_id: string;
  project_name: string;
  status: SetupJobResponse["status"];
  documents: SourceDocumentResponse[];
  cards: { doc_id: string; title: string; status: string }[];
  kb_version: string | null;
}

const state: { jobs: Map<string, MockJob> } = { jobs: new Map() };

export function resetMockState(): void {
  state.jobs.clear();
}

function makeJob(setupJobId: string, projectName: string): MockJob {
  return {
    setup_job_id: setupJobId,
    project_name: projectName,
    status: "draft",
    documents: [],
    cards: [],
    kb_version: null,
  };
}

function jobResponse(job: MockJob): SetupJobResponse {
  return {
    setup_job_id: job.setup_job_id,
    user_id: "u1",
    project_name: job.project_name,
    status: job.status,
    current_step: job.status,
    progress_percent: 0,
    source_documents_count: job.documents.length,
    error_count: 0,
    warning_count: 0,
    started_at: "2026-06-10T10:00:00Z",
    finished_at: null,
    knowledge_base_version: job.kb_version,
    message: null,
  };
}

export const handlers = [
  http.post("/api/v1/setup/jobs", async ({ request }) => {
    const body = (await request.json()) as { project_name: string };
    const sid = `setup_${Math.random().toString(36).slice(2, 10)}`;
    const job = makeJob(sid, body.project_name);
    state.jobs.set(sid, job);
    return HttpResponse.json(jobResponse(job), { status: 201 });
  }),

  http.get("/api/v1/setup/:sid", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json(jobResponse(job));
  }),

  http.get("/api/v1/setup/:sid/progress", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const body: SetupProgressResponse = {
      setup_job_id: job.setup_job_id,
      status: job.status,
      current_step: job.status,
      progress_percent:
        job.status === "ready" ? 100 : job.status === "draft" ? 0 : 50,
      error_count: 0,
      warning_count: 0,
    };
    return HttpResponse.json(body);
  }),

  http.post("/api/v1/setup/:sid/documents", ({ params }) => {
    // jsdom + msw не парсит multipart FormData стабильно — используем
    // фиксированный mock-document. Имя файла в тестах не критично.
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const doc: SourceDocumentResponse = {
      source_document_id: `src_${Math.random().toString(36).slice(2, 8)}`,
      setup_job_id: job.setup_job_id,
      filename: "doc.md",
      content_type: "text/markdown",
      size_bytes: 100,
      checksum: "fake",
      status: "uploaded",
      uploaded_by: "u1",
      uploaded_at: "2026-06-10T10:00:00Z",
    };
    job.documents.push(doc);
    job.status = "files_uploaded";
    const resp: UploadDocumentsResponse = {
      setup_job_id: job.setup_job_id,
      uploaded: [doc],
      skipped_duplicates: [],
      job_status: job.status,
      message: "Uploaded 1",
    };
    return HttpResponse.json(resp, { status: 201 });
  }),

  http.get("/api/v1/setup/:sid/documents", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const resp: ListDocumentsResponse = {
      setup_job_id: job.setup_job_id,
      documents: job.documents,
      count: job.documents.length,
    };
    return HttpResponse.json(resp);
  }),

  // SETUP-02 / T-S02-014: DELETE document.
  http.delete("/api/v1/setup/:sid/documents/:docId", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const docId = params.docId as string;
    const doc = job.documents.find((d) => d.source_document_id === docId);
    if (!doc) return HttpResponse.json({ detail: "doc not found" }, { status: 404 });
    job.documents = job.documents.map((d) =>
      d.source_document_id === docId ? { ...d, status: "removed" } : d,
    );
    return HttpResponse.json({
      setup_job_id: job.setup_job_id,
      source_document_id: docId,
      status: "removed",
      message: "Document removed",
    });
  }),

  // SETUP-02 / T-S02-015: GET single document metadata.
  http.get("/api/v1/setup/:sid/documents/:docId", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const doc = job.documents.find(
      (d) => d.source_document_id === (params.docId as string),
    );
    if (!doc) return HttpResponse.json({ detail: "doc not found" }, { status: 404 });
    return HttpResponse.json(doc);
  }),

  // SETUP-03 / T-S03-023: source registry endpoints.
  http.get("/api/v1/setup/:sid/sources", ({ params }) => {
    // Возвращаем мокированные данные без проверки state.jobs.
    const job = state.jobs.get(params.sid as string);
    const items = (job?.documents ?? []).map((d) => ({
      source_document_id: d.source_document_id,
      setup_job_id: d.setup_job_id,
      filename: d.filename,
      document_kind: null,
      content_type: d.content_type,
      size_bytes: d.size_bytes,
      checksum_short: d.checksum.slice(0, 12),
      status: d.status,
      uploaded_by: d.uploaded_by,
      uploaded_at: d.uploaded_at,
      parsed_sections_count: 0,
      rag_cards_count: 0,
      chunks_count: 0,
      last_error: null,
    }));
    return HttpResponse.json({
      setup_job_id: params.sid as string,
      items,
      pagination: { page: 1, page_size: 20, total: items.length },
    });
  }),

  http.get("/api/v1/setup/:sid/sources/:docId", ({ params }) => {
    // Не зависим от state.jobs — drawer всегда вызывается после listSources.
    return HttpResponse.json({
      source_document_id: params.docId as string,
      setup_job_id: params.sid as string,
      filename: "doc.md",
      original_filename: "doc.md",
      content_type: "text/markdown",
      size_bytes: 1024,
      checksum: "a".repeat(64),
      checksum_algorithm: "sha256",
      storage_path: null,
      status: "registered",
      document_kind: null,
      detected_language: null,
      uploaded_by: "u1",
      uploaded_at: "2026-06-11T10:00:00Z",
      parsed_at: null,
      error_message: null,
      user_metadata: {},
      system_metadata: {},
      counters: {
        parsed_sections_count: 0,
        rag_cards_count: 0,
        chunks_count: 0,
        embeddings_count: 0,
        processing_reports_count: 0,
        knowledge_base_versions_count: 0,
      },
      last_status_change: null,
    });
  }),

  http.get("/api/v1/setup/:sid/sources/:docId/status-history", ({ params }) => {
    return HttpResponse.json({
      source_document_id: params.docId as string,
      items: [
        {
          status_history_id: "hist_001",
          source_document_id: params.docId as string,
          old_status: "uploaded",
          new_status: "registered",
          reason: "Document registered after upload",
          event_id: "evt_001",
          changed_by_type: "service",
          changed_by_id: "document-upload-service",
          changed_at: "2026-06-11T10:00:00Z",
          metadata: {},
        },
      ],
      pagination: { page: 1, page_size: 50, total: 1 },
    });
  }),

  http.get(
    "/api/v1/setup/:sid/sources/:docId/processing-log",
    ({ params }) => {
      return HttpResponse.json({
        source_document_id: params.docId as string,
        items: [
          {
            processing_log_id: "log_001",
            source_document_id: params.docId as string,
            setup_job_id: params.sid as string,
            step: "upload",
            level: "info",
            message: "Document uploaded",
            error_code: null,
            event_id: "evt_log",
            created_at: "2026-06-11T10:00:00Z",
            payload: {},
          },
        ],
        pagination: { page: 1, page_size: 50, total: 1 },
      });
    },
  ),

  http.get("/api/v1/setup/:sid/sources/:docId/lineage", ({ params }) => {
    return HttpResponse.json({
      source_document_id: params.docId as string,
      relations: [],
      counters: {
        parsed_sections_count: 0,
        rag_cards_count: 0,
        chunks_count: 0,
        embeddings_count: 0,
        processing_reports_count: 0,
        knowledge_base_versions_count: 0,
      },
    });
  }),

  http.patch(
    "/api/v1/setup/:sid/sources/:docId/metadata",
    async ({ params, request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({
        source_document_id: params.docId as string,
        setup_job_id: params.sid as string,
        user_metadata: body,
        updated_at: "2026-06-11T10:00:00Z",
        message: "ok",
      });
    },
  ),

  http.delete("/api/v1/setup/:sid/sources/:docId", ({ params }) => {
    return HttpResponse.json({
      source_document_id: params.docId as string,
      setup_job_id: params.sid as string,
      status: "removed",
      message: "Document removed",
    });
  }),

  http.post("/api/v1/setup/:sid/sources/:docId/retry", ({ params, request }) => {
    const url = new URL(request.url);
    return HttpResponse.json({
      source_document_id: params.docId as string,
      setup_job_id: params.sid as string,
      status: "waiting_for_parsing",
      from_step: url.searchParams.get("from_step") ?? "parsing",
      message: "Retry triggered",
    });
  }),

  http.post("/api/v1/setup/:sid/run", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    job.status = "review_required";
    job.cards = [
      {
        doc_id: "schema_card.x.v1",
        title: "Schema X",
        status: "review_required",
      },
    ];
    const resp: RunPipelineResponse = {
      setup_job_id: job.setup_job_id,
      final_status: job.status,
      documents_total: job.documents.length,
      documents_parsed: job.documents.length,
      documents_failed: 0,
      sections_extracted: 1,
      cards_generated: 1,
      cards_review_required: 1,
      cards_used_fallback: 1,
      cards_metadata_validated: 0,
      validation_warnings: 1,
      validation_failed: 0,
      cards_approved_auto: 0,
      chunks_total: 0,
      chunks_indexed: 0,
      chunks_failed: 0,
      vector_index: null,
      errors: [],
      message: "Pipeline completed; 1 card(s) require human review",
    };
    return HttpResponse.json(resp);
  }),

  http.get("/api/v1/setup/:sid/rag-cards", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const resp: ListCardsResponse = {
      setup_job_id: job.setup_job_id,
      cards: job.cards.map((c) => ({
        doc_id: c.doc_id,
        doc_type: "schema_card",
        title: c.title,
        version: "1.0",
        status: c.status,
        confidence_level: "low",
        domain: [],
        phase: ["data_profiling"],
        retrieval_tags: ["t"],
        source_document_ids: ["src_1"],
        created_at: "2026-06-10T10:00:00Z",
        updated_at: "2026-06-10T10:00:00Z",
        body_preview: null,
        body_markdown: "# Schema\nbody",
        history: ["created"],
      })),
      count: job.cards.length,
      filters: {},
    };
    return HttpResponse.json(resp);
  }),

  http.post(
    "/api/v1/setup/:sid/rag-cards/:doc/review",
    async ({ params, request }) => {
      const job = state.jobs.get(params.sid as string);
      if (!job)
        return HttpResponse.json({ detail: "not found" }, { status: 404 });
      const body = (await request.json()) as { decision: string };
      const card = job.cards.find((c) => c.doc_id === params.doc);
      if (!card)
        return HttpResponse.json({ detail: "card not found" }, { status: 404 });
      let newStatus = card.status;
      if (body.decision === "approve") newStatus = "approved";
      else if (body.decision === "reject") newStatus = "deprecated";
      else if (body.decision === "edit") newStatus = "approved";
      else if (body.decision === "regenerate") newStatus = "draft";
      card.status = newStatus;
      const resp: ReviewRAGCardResponse = {
        setup_job_id: job.setup_job_id,
        decision: body.decision,
        affected_doc_id: card.doc_id,
        new_doc_id: body.decision === "edit" ? `${card.doc_id}.1` : null,
        new_status: newStatus,
        message: null,
      };
      return HttpResponse.json(resp);
    },
  ),

  http.post(
    "/api/v1/setup/:sid/retrieval-tests",
    async ({ params, request }) => {
      const job = state.jobs.get(params.sid as string);
      if (!job)
        return HttpResponse.json({ detail: "not found" }, { status: 404 });
      const body = (await request.json()) as {
        golden_queries: { query: string; expected_doc_ids: string[] }[];
      };
      const resp: EvalReportResponse = {
        setup_job_id: job.setup_job_id,
        queries_total: body.golden_queries.length,
        queries_errored: 0,
        top_k: 5,
        threshold_recall_at_5: 0.85,
        mean_recall_at_k: 0.9,
        mean_precision_at_k: 0.5,
        mean_reciprocal_rank: 1.0,
        no_context_rate: 0.0,
        passed: true,
        per_query: body.golden_queries.map((g) => ({
          query: g.query,
          expected_doc_ids: g.expected_doc_ids,
          retrieved_doc_ids: g.expected_doc_ids,
          recall_at_k: 1.0,
          precision_at_k: 1.0,
          reciprocal_rank: 1.0,
          is_no_context: false,
          error_message: null,
        })),
        message: "passed",
      };
      return HttpResponse.json(resp);
    },
  ),

  http.post("/api/v1/setup/:sid/publish", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    job.kb_version = "kb_20260610_120000_a1b2c3";
    job.status = "ready";
    const resp: PublishKBResponse = {
      setup_job_id: job.setup_job_id,
      knowledge_base_version: job.kb_version,
      status: "active",
      is_active: true,
      published_by: "admin1",
      published_at: "2026-06-10T12:00:00Z",
      index_version: "idx_test",
      rag_card_count: 1,
      chunk_count: 3,
      message: "activated",
    };
    return HttpResponse.json(resp);
  }),

  http.get("/api/v1/setup/:sid/report", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const resp: ProcessingReportResponse = {
      setup_job_id: job.setup_job_id,
      status: job.status,
      project_name: job.project_name,
      user_id: "u1",
      progress_percent: job.status === "ready" ? 100 : 0,
      error_count: 0,
      warning_count: 0,
      documents_count: job.documents.length,
      cards_count: job.cards.length,
      cards_approved: 1,
      cards_review_required: 0,
      cards_deprecated: 0,
      knowledge_base_version: job.kb_version,
      knowledge_base_status: job.kb_version ? "active" : null,
      knowledge_base_is_active: !!job.kb_version,
      chunks_indexed: 3,
      index_version: "idx_test",
      eval_passed: true,
      started_at: "2026-06-10T10:00:00Z",
      finished_at: "2026-06-10T12:00:00Z",
    };
    return HttpResponse.json(resp);
  }),
];

export const server = setupServer(...handlers);
