/**
 * SETUP-03 / T-S03-023: API client для /sources endpoints.
 *
 * 8 functions matching backend sources_router.py:
 * - listSources, getSourceDetails
 * - getStatusHistory, getProcessingLog, getLineage
 * - patchSourceMetadata, deleteSource, retrySource
 */
import { apiRequest } from "./client";
import type {
  LineageResponse,
  ListSourcesResponse,
  LineageTargetType,
  PatchSourceMetadataResponse,
  ProcessingLogLevel,
  ProcessingLogResponse,
  ProcessingLogStep,
  RemoveSourceResponse,
  RetrySourceResponse,
  SourceDocumentDetailsDTO,
  SourceDocumentStatus,
  StatusHistoryResponse,
  UpdateSourceMetadataRequest,
} from "./types";

export interface ListSourcesParams {
  status?: SourceDocumentStatus[];
  document_kind?: string;
  content_type?: string;
  owner?: string;
  has_errors?: boolean;
  has_rag_cards?: boolean;
  include_removed?: boolean;
  page?: number;
  page_size?: number;
  sort?: string;
}

export function listSources(
  setupJobId: string,
  params: ListSourcesParams = {},
): Promise<ListSourcesResponse> {
  const query: Record<string, string | number | boolean | string[]> = {};
  if (params.status) query.status = params.status;
  if (params.document_kind) query.document_kind = params.document_kind;
  if (params.content_type) query.content_type = params.content_type;
  if (params.owner) query.owner = params.owner;
  if (params.has_errors !== undefined) query.has_errors = params.has_errors;
  if (params.has_rag_cards !== undefined) query.has_rag_cards = params.has_rag_cards;
  if (params.include_removed !== undefined)
    query.include_removed = params.include_removed;
  if (params.page) query.page = params.page;
  if (params.page_size) query.page_size = params.page_size;
  if (params.sort) query.sort = params.sort;

  return apiRequest(`/setup/${setupJobId}/sources`, { query });
}

export function getSourceDetails(
  setupJobId: string,
  sourceDocumentId: string,
): Promise<SourceDocumentDetailsDTO> {
  return apiRequest(
    `/setup/${setupJobId}/sources/${encodeURIComponent(sourceDocumentId)}`,
  );
}

export interface StatusHistoryParams {
  since?: string;
  page?: number;
  page_size?: number;
}

export function getStatusHistory(
  setupJobId: string,
  sourceDocumentId: string,
  params: StatusHistoryParams = {},
): Promise<StatusHistoryResponse> {
  return apiRequest(
    `/setup/${setupJobId}/sources/${encodeURIComponent(sourceDocumentId)}/status-history`,
    { query: params as Record<string, string | number> },
  );
}

export interface ProcessingLogParams {
  step?: ProcessingLogStep;
  level?: ProcessingLogLevel;
  page?: number;
  page_size?: number;
}

export function getProcessingLog(
  setupJobId: string,
  sourceDocumentId: string,
  params: ProcessingLogParams = {},
): Promise<ProcessingLogResponse> {
  return apiRequest(
    `/setup/${setupJobId}/sources/${encodeURIComponent(sourceDocumentId)}/processing-log`,
    { query: params as Record<string, string | number> },
  );
}

export interface LineageParams {
  target_type?: LineageTargetType;
}

export function getLineage(
  setupJobId: string,
  sourceDocumentId: string,
  params: LineageParams = {},
): Promise<LineageResponse> {
  return apiRequest(
    `/setup/${setupJobId}/sources/${encodeURIComponent(sourceDocumentId)}/lineage`,
    { query: params as Record<string, string> },
  );
}

export function patchSourceMetadata(
  setupJobId: string,
  sourceDocumentId: string,
  patch: UpdateSourceMetadataRequest,
  eventId?: string,
): Promise<PatchSourceMetadataResponse> {
  return apiRequest(
    `/setup/${setupJobId}/sources/${encodeURIComponent(sourceDocumentId)}/metadata`,
    {
      method: "PATCH",
      body: patch,
      query: eventId ? { event_id: eventId } : undefined,
    },
  );
}

export function deleteSource(
  setupJobId: string,
  sourceDocumentId: string,
  reason?: string,
): Promise<RemoveSourceResponse> {
  return apiRequest(
    `/setup/${setupJobId}/sources/${encodeURIComponent(sourceDocumentId)}`,
    {
      method: "DELETE",
      query: reason ? { reason } : undefined,
    },
  );
}

export interface RetrySourceParams {
  from_step?: ProcessingLogStep;
  event_id?: string;
  reason?: string;
}

export function retrySource(
  setupJobId: string,
  sourceDocumentId: string,
  params: RetrySourceParams = {},
): Promise<RetrySourceResponse> {
  return apiRequest(
    `/setup/${setupJobId}/sources/${encodeURIComponent(sourceDocumentId)}/retry`,
    {
      method: "POST",
      query: params as Record<string, string>,
    },
  );
}
