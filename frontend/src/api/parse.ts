import { apiRequest } from "./client";
import type {
  CancelParseJobResponse,
  ClassificationPromptDTO,
  CreateParseJobRequest,
  ParsedSectionDetailDTO,
  ParsedSectionsResponse,
  ParseJobReportResponse,
  ParseJobResponse,
  ParsedSectionStatus,
  RetryParseDocumentResponse,
  SectionType,
} from "./types";

/** SETUP-04 / T-S04-023: создать ParseJob. */
export function createParseJob(
  setupJobId: string,
  body: CreateParseJobRequest = {},
): Promise<ParseJobResponse> {
  return apiRequest(`/setup/${setupJobId}/parse-jobs`, {
    method: "POST",
    body,
  });
}

/** SETUP-04: синхронный запуск ParseJob. */
export function runParseJob(
  setupJobId: string,
  parseJobId: string,
): Promise<ParseJobResponse> {
  return apiRequest(
    `/setup/${setupJobId}/parse-jobs/${encodeURIComponent(parseJobId)}/run`,
    { method: "POST" },
  );
}

/** SETUP-04 / T-S04-024: статус ParseJob. */
export function getParseJobStatus(
  setupJobId: string,
  parseJobId: string,
): Promise<ParseJobResponse> {
  return apiRequest(
    `/setup/${setupJobId}/parse-jobs/${encodeURIComponent(parseJobId)}`,
  );
}

/** SETUP-04 / T-S04-024: отчёт по документам. */
export function getParseJobReport(
  setupJobId: string,
  parseJobId: string,
): Promise<ParseJobReportResponse> {
  return apiRequest(
    `/setup/${setupJobId}/parse-jobs/${encodeURIComponent(parseJobId)}/report`,
  );
}

interface ListSectionsOptions {
  sourceDocumentId?: string;
  sectionType?: SectionType;
  status?: ParsedSectionStatus;
  page?: number;
  pageSize?: number;
}

/** SETUP-04 / T-S04-025: список извлечённых секций. */
export function listParsedSections(
  setupJobId: string,
  parseJobId: string,
  options: ListSectionsOptions = {},
): Promise<ParsedSectionsResponse> {
  return apiRequest(
    `/setup/${setupJobId}/parse-jobs/${encodeURIComponent(parseJobId)}/sections`,
    {
      query: {
        source_document_id: options.sourceDocumentId,
        section_type: options.sectionType,
        status: options.status,
        page: options.page,
        page_size: options.pageSize,
      },
    },
  );
}

/** SETUP-04 / T-S04-025: отменить ParseJob. */
export function cancelParseJob(
  setupJobId: string,
  parseJobId: string,
): Promise<CancelParseJobResponse> {
  return apiRequest(
    `/setup/${setupJobId}/parse-jobs/${encodeURIComponent(parseJobId)}/cancel`,
    { method: "POST" },
  );
}

/** SETUP-04 / T-S04-026: ретрай упавшего документа в ParseJob. */
export function retryParseDocument(
  setupJobId: string,
  parseJobId: string,
  sourceDocumentId: string,
): Promise<RetryParseDocumentResponse> {
  return apiRequest(
    `/setup/${setupJobId}/parse-jobs/${encodeURIComponent(parseJobId)}/documents/${encodeURIComponent(sourceDocumentId)}/retry`,
    { method: "POST" },
  );
}

/** SETUP-04 UX: детализация одной секции (raw + normalized + classification). */
export function getSectionDetail(
  setupJobId: string,
  parseJobId: string,
  sectionId: string,
): Promise<ParsedSectionDetailDTO> {
  return apiRequest(
    `/setup/${setupJobId}/parse-jobs/${encodeURIComponent(parseJobId)}/sections/${encodeURIComponent(sectionId)}`,
  );
}

/** SETUP-12: preview LLM-prompts для L0/L1/L2 классификации секции. */
export function getSectionPrompts(
  setupJobId: string,
  parseJobId: string,
  sectionId: string,
): Promise<ClassificationPromptDTO[]> {
  return apiRequest(
    `/setup/${setupJobId}/parse-jobs/${encodeURIComponent(parseJobId)}/sections/${encodeURIComponent(sectionId)}/prompts`,
  );
}
