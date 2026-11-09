import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type {
  ClassifierNodeDTO,
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
  // SETUP-04/05/08 granular flow (заменяет legacy /run в тестах).
  parseJobId: string | null;
  sections: {
    section_id: string;
    source_document_id: string;
    title: string;
  }[];
  ragCardGenerationJobId: string | null;
  chunkManifestCreated: boolean;
}

// SETUP-13 / ADR-HTC-09: mock-дерево классификаторов (маленькое — не
// весь реальный 906-узловой seed, только для проверки UI-флоу:
// корень → 2 ребёнка, один из них с собственным ребёнком).
interface MockClassifierNode {
  node_id: string;
  parent_id: string | null;
  level: number;
  name: string;
  description: string;
  children_ids: string[];
  prompt_override: string | null;
}

function makeClassifierTreeFixture(): Map<string, MockClassifierNode> {
  const nodes = new Map<string, MockClassifierNode>();
  nodes.set("root-asu", {
    node_id: "root-asu",
    parent_id: null,
    level: -1,
    name: "АСУ",
    description: "",
    children_ids: ["cls-a", "cls-b"],
    prompt_override: null,
  });
  nodes.set("cls-a", {
    node_id: "cls-a",
    parent_id: "root-asu",
    level: 0,
    name: "Класс A",
    description: "Первый класс верхнего уровня",
    children_ids: [],
    prompt_override: null,
  });
  nodes.set("cls-b", {
    node_id: "cls-b",
    parent_id: "root-asu",
    level: 0,
    name: "Класс B",
    description: "Второй класс верхнего уровня",
    children_ids: ["cls-b-1"],
    prompt_override: null,
  });
  nodes.set("cls-b-1", {
    node_id: "cls-b-1",
    parent_id: "cls-b",
    level: 1,
    name: "Подкласс B.1",
    description: "",
    children_ids: [],
    prompt_override: null,
  });
  return nodes;
}

const state: {
  jobs: Map<string, MockJob>;
  classifierNodes: Map<string, MockClassifierNode>;
} = { jobs: new Map(), classifierNodes: makeClassifierTreeFixture() };

function classifierPath(nodeId: string): string[] {
  const path: string[] = [];
  let current: MockClassifierNode | undefined = state.classifierNodes.get(nodeId);
  while (current) {
    path.unshift(current.name);
    current = current.parent_id ? state.classifierNodes.get(current.parent_id) : undefined;
  }
  return path;
}

function classifierNodeToDto(n: MockClassifierNode): ClassifierNodeDTO {
  return {
    node_id: n.node_id,
    parent_id: n.parent_id,
    level: n.level,
    name: n.name,
    description: n.description,
    children_ids: n.children_ids,
    prompt_override: n.prompt_override,
    is_leaf: n.children_ids.length === 0,
    path: classifierPath(n.node_id),
  };
}

export function resetMockState(): void {
  state.jobs.clear();
  state.classifierNodes = makeClassifierTreeFixture();
}

function makeJob(setupJobId: string, projectName: string): MockJob {
  return {
    setup_job_id: setupJobId,
    project_name: projectName,
    status: "draft",
    documents: [],
    cards: [],
    kb_version: null,
    parseJobId: null,
    sections: [],
    ragCardGenerationJobId: null,
    chunkManifestCreated: false,
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

  // SETUP-06 / T-S06-026..029: review flow (RAGCardReviewTable + Drawer).
  http.get("/api/v1/setup/:sid/rag-cards-review", ({ params, request }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const url = new URL(request.url);
    const statusFilter = url.searchParams.get("status");
    const items = job.cards
      .filter((c) => !statusFilter || c.status === statusFilter)
      .map((c) => ({
        doc_id: c.doc_id,
        card_version: "1.0",
        title: c.title,
        doc_type: "schema_card",
        status: c.status,
        confidence_level: "low",
        source_document_id: "src_1",
        source_section_id: "sec_1",
        validation_errors_count: 0,
        warnings_count: 0,
        review_required_reason: null,
        last_reviewed_by: null,
        updated_at: "2026-06-10T10:00:00Z",
      }));
    return HttpResponse.json({
      setup_job_id: job.setup_job_id,
      items,
      total: items.length,
      page: 1,
      page_size: 20,
      summary: { total: job.cards.length, by_status: {} },
    });
  }),

  http.get("/api/v1/setup/:sid/rag-cards-review/:doc", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const card = job.cards.find((c) => c.doc_id === params.doc);
    if (!card) return HttpResponse.json({ detail: "card not found" }, { status: 404 });
    return HttpResponse.json({
      doc_id: card.doc_id,
      card_version: "1.0",
      title: card.title,
      doc_type: "schema_card",
      status: card.status,
      confidence_level: "low",
      metadata: {},
      body_markdown: "# Schema\nbody",
      source_trace: {},
      validation: { critical_errors: [], warnings: [] },
      review_log_count: 0,
      permissions: {
        can_approve: card.status === "review_required",
        can_reject: card.status === "review_required",
        can_edit: true,
        can_regenerate: true,
      },
    });
  }),

  http.post(
    "/api/v1/setup/:sid/rag-cards-review/:doc/review",
    async ({ params, request }) => {
      const job = state.jobs.get(params.sid as string);
      if (!job)
        return HttpResponse.json({ detail: "not found" }, { status: 404 });
      const card = job.cards.find((c) => c.doc_id === params.doc);
      if (!card)
        return HttpResponse.json({ detail: "card not found" }, { status: 404 });
      const body = (await request.json()) as { decision: "approve" | "reject" };
      card.status = body.decision === "approve" ? "approved" : "rejected";
      return HttpResponse.json({
        doc_id: card.doc_id,
        card_version: "1.0",
        status: card.status,
        review_decision_id: "rd_1",
        reviewed_by: "u1",
        reviewed_at: "2026-06-10T10:05:00Z",
      });
    },
  ),

  // OBS-LLM-01: LLM latency stats для progress bar.
  http.get("/api/v1/observability/llm-stats", () => {
    return HttpResponse.json({ models: [] });
  }),

  // SETUP-12: активное дерево таксономии (фоновый запрос ClassificationBadge).
  http.get("/api/v1/taxonomy/tree", () => {
    return HttpResponse.json({
      version: {
        version_id: "v1.0.0",
        created_at: "2026-06-01T00:00:00Z",
        description: "seed",
        is_active: true,
      },
      roots: [],
      total_classes: 0,
      auto_created_count: 0,
    });
  }),

  // ========================================================
  // SETUP-04: parse-jobs (гранулярный флоу, заменяет legacy /run).
  // ========================================================

  http.post("/api/v1/setup/:sid/parse-jobs", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    job.parseJobId = `pj_${Math.random().toString(36).slice(2, 10)}`;
    return HttpResponse.json(
      {
        parse_job_id: job.parseJobId,
        setup_job_id: job.setup_job_id,
        status: "created",
        total_documents: job.documents.length,
        processed_documents: 0,
        failed_documents: 0,
        total_sections: 0,
        low_confidence_sections: 0,
        started_at: null,
        finished_at: null,
        created_at: "2026-06-10T10:00:00Z",
        updated_at: "2026-06-10T10:00:00Z",
        error_code: null,
        error_message: null,
      },
      { status: 201 },
    );
  }),

  http.post(
    "/api/v1/setup/:sid/parse-jobs/:pjid/run",
    ({ params }) => {
      const job = state.jobs.get(params.sid as string);
      if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
      job.sections = job.documents
        .filter((d) => d.status !== "removed")
        .map((d, i) => ({
          section_id: `sec_${i.toString().padStart(3, "0")}`,
          source_document_id: d.source_document_id,
          title: "Schema",
        }));
      return HttpResponse.json({
        parse_job_id: params.pjid as string,
        setup_job_id: job.setup_job_id,
        status: "completed",
        total_documents: job.documents.length,
        processed_documents: job.documents.length,
        failed_documents: 0,
        total_sections: job.sections.length,
        low_confidence_sections: 0,
        started_at: "2026-06-10T10:00:00Z",
        finished_at: "2026-06-10T10:00:01Z",
        created_at: "2026-06-10T10:00:00Z",
        updated_at: "2026-06-10T10:00:01Z",
        error_code: null,
        error_message: null,
      });
    },
  ),

  http.get("/api/v1/setup/:sid/parse-jobs/:pjid", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json({
      parse_job_id: params.pjid as string,
      setup_job_id: job.setup_job_id,
      status: job.sections.length > 0 ? "completed" : "created",
      total_documents: job.documents.length,
      processed_documents: job.sections.length > 0 ? job.documents.length : 0,
      failed_documents: 0,
      total_sections: job.sections.length,
      low_confidence_sections: 0,
      started_at: "2026-06-10T10:00:00Z",
      finished_at: job.sections.length > 0 ? "2026-06-10T10:00:01Z" : null,
      created_at: "2026-06-10T10:00:00Z",
      updated_at: "2026-06-10T10:00:01Z",
      error_code: null,
      error_message: null,
    });
  }),

  http.get("/api/v1/setup/:sid/parse-jobs/:pjid/report", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json({
      parse_job_id: params.pjid as string,
      setup_job_id: job.setup_job_id,
      status: "completed",
      documents: job.documents.map((d) => ({
        source_document_id: d.source_document_id,
        status: "completed",
        parser_strategy: "markdown",
        sections_count: job.sections.length,
        sections_by_type: { schema: job.sections.length },
        low_confidence_sections: 0,
        errors: [],
        warnings: [],
        created_at: "2026-06-10T10:00:01Z",
      })),
    });
  }),

  http.get("/api/v1/setup/:sid/parse-jobs/:pjid/sections", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json({
      parse_job_id: params.pjid as string,
      items: job.sections.map((s, i) => ({
        section_id: s.section_id,
        source_document_id: s.source_document_id,
        title: s.title,
        section_type: "schema",
        section_status: "classified",
        confidence: 0.9,
        heading_path: [s.title],
        section_index: i,
        parent_section_id: null,
        content_hash: `hash_${s.section_id}`,
        classification_method: null,
        classification_state: null,
      })),
      pagination: { page: 1, page_size: 100, total: job.sections.length },
    });
  }),

  // T-S05-029: каталог карточек (RAGCardList + LowConfidenceCardsPanel,
  // вкладка "Генерация RAG-карточек" — без дефолтного фильтра по статусу).
  http.get("/api/v1/setup/:sid/rag-cards-catalog", ({ params, request }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const url = new URL(request.url);
    const statusFilter = url.searchParams.get("status");
    const confidenceFilter = url.searchParams.get("confidence_level");
    const items = job.cards
      .filter((c) => !statusFilter || c.status === statusFilter)
      .filter(() => !confidenceFilter || confidenceFilter === "low")
      .map((c) => ({
        doc_id: c.doc_id,
        setup_job_id: job.setup_job_id,
        card_version: "1.0",
        doc_type: "schema_card",
        title: c.title,
        status: c.status,
        confidence_level: "low",
        primary_source_section_id: job.sections[0]?.section_id ?? null,
        source_document_ids: job.documents.map((d) => d.source_document_id),
        retrieval_tags: [],
        created_at: "2026-06-10T10:01:01Z",
        updated_at: "2026-06-10T10:01:01Z",
        review_required_reason: null,
      }));
    return HttpResponse.json({
      setup_job_id: job.setup_job_id,
      items,
      pagination: { page: 1, page_size: 20, total: items.length },
    });
  }),

  // ========================================================
  // SETUP-05: rag-card-generation-jobs (гранулярный флоу).
  // ========================================================

  http.post("/api/v1/setup/:sid/rag-cards/generate", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    job.ragCardGenerationJobId = `gj_${Math.random().toString(36).slice(2, 10)}`;
    return HttpResponse.json(
      {
        generation_job_id: job.ragCardGenerationJobId,
        setup_job_id: job.setup_job_id,
        requested_by: "u1",
        status: "created",
        total_sections: job.sections.length,
        processed_sections: 0,
        generated_cards: 0,
        failed_sections: 0,
        review_required_cards: 0,
        started_at: null,
        finished_at: null,
        created_at: "2026-06-10T10:01:00Z",
        updated_at: "2026-06-10T10:01:00Z",
        error_code: null,
        error_message: null,
        config: {},
      },
      { status: 201 },
    );
  }),

  http.post(
    "/api/v1/setup/:sid/rag-card-generation-jobs/:gjid/run",
    ({ params }) => {
      const job = state.jobs.get(params.sid as string);
      if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
      job.cards = [
        {
          doc_id: "schema_card.x.v1",
          title: "Schema X",
          status: "review_required",
        },
      ];
      return HttpResponse.json({
        generation_job_id: params.gjid as string,
        setup_job_id: job.setup_job_id,
        requested_by: "u1",
        status: "completed",
        total_sections: job.sections.length,
        processed_sections: job.sections.length,
        generated_cards: job.cards.length,
        failed_sections: 0,
        review_required_cards: job.cards.length,
        started_at: "2026-06-10T10:01:00Z",
        finished_at: "2026-06-10T10:01:01Z",
        created_at: "2026-06-10T10:01:00Z",
        updated_at: "2026-06-10T10:01:01Z",
        error_code: null,
        error_message: null,
        config: {},
      });
    },
  ),

  http.get(
    "/api/v1/setup/:sid/rag-card-generation-jobs/:gjid",
    ({ params }) => {
      const job = state.jobs.get(params.sid as string);
      if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
      const done = job.cards.length > 0;
      return HttpResponse.json({
        generation_job_id: params.gjid as string,
        setup_job_id: job.setup_job_id,
        requested_by: "u1",
        status: done ? "completed" : "created",
        total_sections: job.sections.length,
        processed_sections: done ? job.sections.length : 0,
        generated_cards: job.cards.length,
        failed_sections: 0,
        review_required_cards: job.cards.length,
        started_at: "2026-06-10T10:01:00Z",
        finished_at: done ? "2026-06-10T10:01:01Z" : null,
        created_at: "2026-06-10T10:01:00Z",
        updated_at: "2026-06-10T10:01:01Z",
        error_code: null,
        error_message: null,
        config: {},
      });
    },
  ),

  http.get(
    "/api/v1/setup/:sid/rag-card-generation-jobs/:gjid/report",
    ({ params }) => {
      const job = state.jobs.get(params.sid as string);
      if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
      return HttpResponse.json({
        generation_report_id: `rep_${params.gjid as string}`,
        generation_job_id: params.gjid as string,
        status: "completed",
        summary: {
          total_sections: job.sections.length,
          processed_sections: job.sections.length,
          generated_cards: job.cards.length,
          failed_sections: 0,
          review_required_cards: job.cards.length,
          cards_by_type: { schema_card: job.cards.length },
        },
        errors: [],
        warnings: [],
        created_at: "2026-06-10T10:01:01Z",
      });
    },
  ),

  // ========================================================
  // SETUP-07: metadata validation (read-only панели ValidationStep).
  // ========================================================

  http.get("/api/v1/setup/:sid/validation/summary", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json({
      setup_job_id: job.setup_job_id,
      total: 0,
      passed: 0,
      warnings: 0,
      failed: 0,
      review_required: 0,
      by_code: {},
      last_run_id: null,
    });
  }),

  http.get("/api/v1/setup/:sid/validation/reports", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json({
      setup_job_id: job.setup_job_id,
      items: [],
      total: 0,
    });
  }),

  // ========================================================
  // SETUP-08: chunking (ChunkPreviewPanel).
  // ========================================================

  http.post("/api/v1/setup/:sid/chunking/run", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    job.chunkManifestCreated = true;
    return HttpResponse.json({
      chunking_run_id: `cr_${Math.random().toString(36).slice(2, 8)}`,
      setup_job_id: job.setup_job_id,
      manifest_id: `man_${job.setup_job_id}`,
      triggered_by: "u1",
      total_cards: job.cards.length,
      chunks_created: job.cards.length * 3,
      duration_ms: 12,
      started_at: "2026-06-10T10:02:00Z",
      finished_at: "2026-06-10T10:02:01Z",
    });
  }),

  http.get("/api/v1/setup/:sid/chunking/manifest", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    if (!job.chunkManifestCreated) {
      return HttpResponse.json({ detail: "no manifest" }, { status: 404 });
    }
    return HttpResponse.json({
      manifest_id: `man_${job.setup_job_id}`,
      setup_job_id: job.setup_job_id,
      total_chunks: job.cards.length * 3,
      by_type: {
        summary: job.cards.length,
        definition: job.cards.length,
        metadata_summary: job.cards.length,
      },
      chunks: [],
      created_at: "2026-06-10T10:02:01Z",
      created_by: "u1",
    });
  }),

  // SETUP-01 / T-S01-034: reindex — единственный путь заполнить vector
  // index в гранулярном флоу (legacy /run убран из мастера).
  http.post("/api/v1/setup/:sid/reindex", ({ params }) => {
    const job = state.jobs.get(params.sid as string);
    if (!job) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const chunks = job.cards.length * 3;
    return HttpResponse.json({
      setup_job_id: job.setup_job_id,
      index_version: `idx_${Math.random().toString(36).slice(2, 8)}`,
      chunks_total: chunks,
      chunks_indexed: chunks,
      chunks_failed: 0,
      vector_index: {
        index_version: "idx_test",
        status: "ready",
        embedding_model: "nomic-embed-text",
        chunks_count: chunks,
        indexed_chunks_count: chunks,
        failed_chunks_count: 0,
        collection_names: ["schema_card"],
      },
      errors: [],
      message: `Reindexed ${chunks}/${chunks} chunks`,
    });
  }),

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

  // ========================================================
  // SETUP-13 / ADR-HTC-09: Classifier Library.
  // ========================================================

  http.get("/api/v1/classifier/tree", () => {
    const root = state.classifierNodes.get("root-asu");
    if (!root) return HttpResponse.json({ detail: "no active tree" }, { status: 404 });
    return HttpResponse.json({
      tree_id: "asu_v1",
      version: "1.0.0",
      description: "mock",
      total_nodes: state.classifierNodes.size,
      roots: [classifierNodeToDto(root)],
    });
  }),

  http.get("/api/v1/classifier/tree/nodes/:nodeId", ({ params }) => {
    const node = state.classifierNodes.get(params.nodeId as string);
    if (!node) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const children = node.children_ids
      .map((cid) => state.classifierNodes.get(cid))
      .filter((c): c is MockClassifierNode => !!c)
      .map(classifierNodeToDto);
    // Как реальный ClassifierPromptRenderer: секция с фрагментом текста —
    // техническая обвязка реального вызова классификации, не показывается
    // при редактировании промпта (fragment_text не передан).
    const renderedPrompt =
      node.children_ids.length > 0
        ? node.prompt_override ??
          `Определи подкласс для «${node.name}»${node.description ? ` — ${node.description}` : ""}` +
            ` среди: ${children.map((c) => c.name).join(", ")}`
        : null;
    return HttpResponse.json({
      node: classifierNodeToDto(node),
      children,
      rendered_prompt: renderedPrompt,
    });
  }),

  http.post(
    "/api/v1/classifier/tree/nodes/:nodeId/children",
    async ({ params, request }) => {
      const parent = state.classifierNodes.get(params.nodeId as string);
      if (!parent) return HttpResponse.json({ detail: "not found" }, { status: 404 });
      const body = (await request.json()) as { name: string; description?: string };
      const newId = `cls-${Math.random().toString(36).slice(2, 8)}`;
      const newNode: MockClassifierNode = {
        node_id: newId,
        parent_id: parent.node_id,
        level: parent.level + 1,
        name: body.name,
        description: body.description ?? "",
        children_ids: [],
        prompt_override: null,
      };
      state.classifierNodes.set(newId, newNode);
      parent.children_ids.push(newId);
      return HttpResponse.json(classifierNodeToDto(newNode), { status: 201 });
    },
  ),

  http.patch(
    "/api/v1/classifier/tree/nodes/:nodeId",
    async ({ params, request }) => {
      const node = state.classifierNodes.get(params.nodeId as string);
      if (!node) return HttpResponse.json({ detail: "not found" }, { status: 404 });
      const body = (await request.json()) as {
        name?: string;
        description?: string;
        prompt_override?: string;
        clear_prompt_override?: boolean;
      };
      if (body.name !== undefined) node.name = body.name;
      if (body.description !== undefined) node.description = body.description;
      if (body.clear_prompt_override) {
        node.prompt_override = null;
      } else if (body.prompt_override !== undefined) {
        node.prompt_override = body.prompt_override;
      }
      return HttpResponse.json(classifierNodeToDto(node));
    },
  ),

  http.post(
    "/api/v1/classifier/tree/nodes/:nodeId/generate-description",
    ({ params }) => {
      const node = state.classifierNodes.get(params.nodeId as string);
      if (!node) return HttpResponse.json({ detail: "not found" }, { status: 404 });
      return HttpResponse.json({
        description: `Черновик описания для «${node.name}» (сгенерировано LLM).`,
      });
    },
  ),

  http.delete("/api/v1/classifier/tree/nodes/:nodeId", ({ params }) => {
    const nodeId = params.nodeId as string;
    const node = state.classifierNodes.get(nodeId);
    if (!node) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    if (node.parent_id === null) {
      return HttpResponse.json({ detail: "cannot delete root" }, { status: 409 });
    }
    const toRemove = new Set<string>();
    const stack = [nodeId];
    while (stack.length > 0) {
      const current = stack.pop() as string;
      if (toRemove.has(current)) continue;
      toRemove.add(current);
      const currentNode = state.classifierNodes.get(current);
      if (currentNode) stack.push(...currentNode.children_ids);
    }
    for (const id of toRemove) state.classifierNodes.delete(id);
    const parent = state.classifierNodes.get(node.parent_id);
    if (parent) {
      parent.children_ids = parent.children_ids.filter((cid) => cid !== nodeId);
    }
    return HttpResponse.json({
      node_id: nodeId,
      deleted_count: toRemove.size,
      message: `Deleted ${nodeId} and ${toRemove.size - 1} descendant(s)`,
    });
  }),
];

export const server = setupServer(...handlers);
