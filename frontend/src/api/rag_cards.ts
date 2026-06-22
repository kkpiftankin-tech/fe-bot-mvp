import { apiRequest } from "./client";
import type {
  CancelRAGCardJobResponse,
  GenerateRAGCardsRequest,
  RAGCardDetails,
  RAGCardGenerationJobResponse,
  RAGCardGenerationReportResponse,
  RAGCardListResponse,
  RAGCardPreview,
  RegenerateRAGCardRequest,
  RegenerateRAGCardResponse,
} from "./types";

/** SETUP-05 / T-S05-028: создать generation job. */
export function createRAGCardGenerationJob(
  setupJobId: string,
  body: GenerateRAGCardsRequest = {},
): Promise<RAGCardGenerationJobResponse> {
  return apiRequest(`/setup/${setupJobId}/rag-cards/generate`, {
    method: "POST",
    body,
  });
}

/** SETUP-05: синхронный запуск generation job. */
export function runRAGCardGenerationJob(
  setupJobId: string,
  generationJobId: string,
): Promise<RAGCardGenerationJobResponse> {
  return apiRequest(
    `/setup/${setupJobId}/rag-card-generation-jobs/${encodeURIComponent(
      generationJobId,
    )}/run`,
    { method: "POST" },
  );
}

/** SETUP-05: статус generation job. */
export function getRAGCardGenerationJob(
  setupJobId: string,
  generationJobId: string,
): Promise<RAGCardGenerationJobResponse> {
  return apiRequest(
    `/setup/${setupJobId}/rag-card-generation-jobs/${encodeURIComponent(
      generationJobId,
    )}`,
  );
}

/** SETUP-05: отчёт по generation job. */
export function getRAGCardGenerationReport(
  setupJobId: string,
  generationJobId: string,
): Promise<RAGCardGenerationReportResponse> {
  return apiRequest(
    `/setup/${setupJobId}/rag-card-generation-jobs/${encodeURIComponent(
      generationJobId,
    )}/report`,
  );
}

interface ListRAGCardsOptions {
  docType?: string;
  status?: string;
  confidenceLevel?: "high" | "medium" | "low";
  sourceDocumentId?: string;
  page?: number;
  pageSize?: number;
}

/** SETUP-05 / T-S05-029: list карточек с фильтрами и pagination. */
export function listRAGCards(
  setupJobId: string,
  options: ListRAGCardsOptions = {},
): Promise<RAGCardListResponse> {
  return apiRequest(`/setup/${setupJobId}/rag-cards-catalog`, {
    query: {
      doc_type: options.docType,
      status: options.status,
      confidence_level: options.confidenceLevel,
      source_document_id: options.sourceDocumentId,
      page: options.page,
      page_size: options.pageSize,
    },
  });
}

/** SETUP-05: детали карточки (по latest или конкретной version). */
export function getRAGCard(
  setupJobId: string,
  docId: string,
  version?: string,
): Promise<RAGCardDetails> {
  return apiRequest(
    `/setup/${setupJobId}/rag-cards/${encodeURIComponent(docId)}`,
    { query: version ? { version } : undefined },
  );
}

/** SETUP-05: preview карточки + source trace. */
export function getRAGCardPreview(
  setupJobId: string,
  docId: string,
  version?: string,
): Promise<RAGCardPreview> {
  return apiRequest(
    `/setup/${setupJobId}/rag-cards/${encodeURIComponent(docId)}/preview`,
    { query: version ? { version } : undefined },
  );
}

/** SETUP-05 / T-S05-030: регенерация карточки. */
export function regenerateRAGCard(
  setupJobId: string,
  docId: string,
  body: RegenerateRAGCardRequest,
): Promise<RegenerateRAGCardResponse> {
  return apiRequest(
    `/setup/${setupJobId}/rag-cards/${encodeURIComponent(docId)}/regenerate`,
    { method: "POST", body },
  );
}

/** SETUP-05 / T-S05-031: отмена generation job. */
export function cancelRAGCardGenerationJob(
  setupJobId: string,
  generationJobId: string,
): Promise<CancelRAGCardJobResponse> {
  return apiRequest(
    `/setup/${setupJobId}/rag-card-generation-jobs/${encodeURIComponent(
      generationJobId,
    )}/cancel`,
    { method: "POST" },
  );
}
