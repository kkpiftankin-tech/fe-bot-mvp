import { apiRequest } from "./client";
import type {
  ApproveResponse,
  BulkReviewRequest,
  BulkReviewResponse,
  CardDiffResponse,
  EditRAGCardRequest,
  EditResponse,
  RAGCardReviewDetailsDTO,
  RAGCardReviewListResponse,
  RAGCardVersionsResponse,
  RegenerateRAGCardReviewRequest,
  RegenerateReviewResponse,
  RejectResponse,
  ReviewLogResponse,
  ReviewRAGCardDecisionRequest,
} from "./types";

interface ListReviewCardsOptions {
  docType?: string;
  status?: string;
  confidenceLevel?: "high" | "medium" | "low";
  sourceDocumentId?: string;
  hasValidationErrors?: boolean;
  reviewRequired?: boolean;
  page?: number;
  pageSize?: number;
}

/** SETUP-06 / T-S06-026: list cards для review. */
export function listReviewCards(
  setupJobId: string,
  options: ListReviewCardsOptions = {},
): Promise<RAGCardReviewListResponse> {
  return apiRequest(`/setup/${setupJobId}/rag-cards-review`, {
    query: {
      doc_type: options.docType,
      status: options.status,
      confidence_level: options.confidenceLevel,
      source_document_id: options.sourceDocumentId,
      has_validation_errors: options.hasValidationErrors,
      review_required: options.reviewRequired,
      page: options.page,
      page_size: options.pageSize,
    },
  });
}

export function getReviewCard(
  setupJobId: string,
  docId: string,
): Promise<RAGCardReviewDetailsDTO> {
  return apiRequest(
    `/setup/${setupJobId}/rag-cards-review/${encodeURIComponent(docId)}`,
  );
}

export function getReviewVersions(
  setupJobId: string,
  docId: string,
): Promise<RAGCardVersionsResponse> {
  return apiRequest(
    `/setup/${setupJobId}/rag-cards-review/${encodeURIComponent(docId)}/versions`,
  );
}

export function getReviewDiff(
  setupJobId: string,
  docId: string,
  fromVersion: string,
  toVersion: string,
): Promise<CardDiffResponse> {
  return apiRequest(
    `/setup/${setupJobId}/rag-cards-review/${encodeURIComponent(docId)}/diff`,
    { query: { from_version: fromVersion, to_version: toVersion } },
  );
}

export function getReviewLog(
  setupJobId: string,
  docId: string,
  limit = 50,
): Promise<ReviewLogResponse> {
  return apiRequest(
    `/setup/${setupJobId}/rag-cards-review/${encodeURIComponent(docId)}/review-log`,
    { query: { limit } },
  );
}

export function reviewCard(
  setupJobId: string,
  docId: string,
  body: ReviewRAGCardDecisionRequest,
): Promise<ApproveResponse | RejectResponse> {  // eslint-disable-line @typescript-eslint/no-unused-vars
  return apiRequest(
    `/setup/${setupJobId}/rag-cards-review/${encodeURIComponent(docId)}/review`,
    { method: "POST", body },
  );
}

export function editReviewCard(
  setupJobId: string,
  docId: string,
  body: EditRAGCardRequest,
): Promise<EditResponse> {
  return apiRequest(
    `/setup/${setupJobId}/rag-cards-review/${encodeURIComponent(docId)}`,
    { method: "PATCH", body },
  );
}

export function regenerateReviewCard(
  setupJobId: string,
  docId: string,
  body: RegenerateRAGCardReviewRequest,
): Promise<RegenerateReviewResponse> {
  return apiRequest(
    `/setup/${setupJobId}/rag-cards-review/${encodeURIComponent(docId)}/regenerate`,
    { method: "POST", body },
  );
}

export function bulkReview(
  setupJobId: string,
  body: BulkReviewRequest,
): Promise<BulkReviewResponse> {
  return apiRequest(`/setup/${setupJobId}/rag-cards-review/bulk-review`, {
    method: "POST",
    body,
  });
}
