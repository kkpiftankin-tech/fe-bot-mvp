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
  ReviewRAGCardRequest,
  ReviewRAGCardResponse,
  RunPipelineResponse,
  RunRetrievalTestsRequest,
  SetupJobResponse,
  SetupProgressResponse,
  UploadDocumentsResponse,
} from "./types";

// ----- Jobs -----

export function createSetupJob(
  request: CreateSetupJobRequest,
): Promise<SetupJobResponse> {
  return apiRequest("/setup/jobs", { method: "POST", body: request });
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
