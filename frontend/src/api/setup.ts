import { apiRequest } from "./client";
import type {
  CreateSetupJobRequest,
  EvalReportResponse,
  ListCardsResponse,
  ListDocumentsResponse,
  ProcessingReportResponse,
  PublishKBRequest,
  PublishKBResponse,
  ReindexResponse,
  RemoveDocumentResponse,
  ReviewRAGCardRequest,
  ReviewRAGCardResponse,
  RunPipelineResponse,
  RunRetrievalTestsRequest,
  SetupJobResponse,
  SetupProgressResponse,
  SourceDocumentResponse,
  UploadDocumentsResponse,
} from "./types";

// ----- Jobs -----

export function createSetupJob(
  request: CreateSetupJobRequest,
): Promise<SetupJobResponse> {
  return apiRequest("/setup/jobs", { method: "POST", body: request });
}

export interface SetupJobListItem extends SetupJobResponse {
  active_parse_job_id: string | null;
  // SETUP-04 UX: последний parse_job независимо от статуса (в отличие от
  // active_parse_job_id, который null, если парсинг уже завершён).
  latest_parse_job_id: string | null;
  parsed_sections_count: number;
  parse_job_status: string | null;
}

export interface SetupJobListResponse {
  items: SetupJobListItem[];
  total: number;
}

export function listSetupJobs(): Promise<SetupJobListResponse> {
  return apiRequest("/setup/jobs");
}

export function getSetupJob(setupJobId: string): Promise<SetupJobResponse> {
  return apiRequest(`/setup/${setupJobId}`);
}

export function getSetupProgress(
  setupJobId: string,
): Promise<SetupProgressResponse> {
  return apiRequest(`/setup/${setupJobId}/progress`);
}

export function cancelSetupJob(
  setupJobId: string,
): Promise<SetupJobResponse> {
  return apiRequest(`/setup/${setupJobId}/cancel`, { method: "POST" });
}

// ----- Documents -----

export function uploadDocuments(
  setupJobId: string,
  files: File[],
  duplicateStrategy: "skip" | "version" = "skip",
): Promise<UploadDocumentsResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  return apiRequest(`/setup/${setupJobId}/documents`, {
    method: "POST",
    formData,
    query: { duplicate_strategy: duplicateStrategy },
  });
}

export function listDocuments(
  setupJobId: string,
): Promise<ListDocumentsResponse> {
  return apiRequest(`/setup/${setupJobId}/documents`);
}

/** SETUP-02 / T-S02-015: GET single document metadata. */
export function getDocumentMetadata(
  setupJobId: string,
  sourceDocumentId: string,
): Promise<SourceDocumentResponse> {
  return apiRequest(
    `/setup/${setupJobId}/documents/${encodeURIComponent(sourceDocumentId)}`,
  );
}

/** SETUP-02 / T-S02-014: soft-delete документа. */
export function deleteDocument(
  setupJobId: string,
  sourceDocumentId: string,
  reason?: string,
): Promise<RemoveDocumentResponse> {
  return apiRequest(
    `/setup/${setupJobId}/documents/${encodeURIComponent(sourceDocumentId)}`,
    {
      method: "DELETE",
      query: reason ? { reason } : undefined,
    },
  );
}

// ----- Pipeline -----

export function runPipeline(
  setupJobId: string,
): Promise<RunPipelineResponse> {
  return apiRequest(`/setup/${setupJobId}/run`, { method: "POST" });
}

export function reindexCards(
  setupJobId: string,
): Promise<ReindexResponse> {
  return apiRequest(`/setup/${setupJobId}/reindex`, { method: "POST" });
}

// ----- Cards / Review -----

interface ListCardsOptions {
  cardStatus?: string;
  docType?: string;
  confidenceLevel?: string;
  includeBody?: boolean;
}

export function listRAGCards(
  setupJobId: string,
  options: ListCardsOptions = {},
): Promise<ListCardsResponse> {
  return apiRequest(`/setup/${setupJobId}/rag-cards`, {
    query: {
      card_status: options.cardStatus,
      doc_type: options.docType,
      confidence_level: options.confidenceLevel,
      include: options.includeBody ? "body" : undefined,
    },
  });
}

export function reviewRAGCard(
  setupJobId: string,
  docId: string,
  request: ReviewRAGCardRequest,
): Promise<ReviewRAGCardResponse> {
  return apiRequest(
    `/setup/${setupJobId}/rag-cards/${encodeURIComponent(docId)}/review`,
    { method: "POST", body: request },
  );
}

// ----- Retrieval tests / Publish / Report -----

export function runRetrievalTests(
  setupJobId: string,
  request: RunRetrievalTestsRequest,
): Promise<EvalReportResponse> {
  return apiRequest(`/setup/${setupJobId}/retrieval-tests`, {
    method: "POST",
    body: request,
  });
}

export function publishKB(
  setupJobId: string,
  request: PublishKBRequest,
): Promise<PublishKBResponse> {
  return apiRequest(`/setup/${setupJobId}/publish`, {
    method: "POST",
    body: request,
  });
}

export function getReport(
  setupJobId: string,
): Promise<ProcessingReportResponse> {
  return apiRequest(`/setup/${setupJobId}/report`);
}
