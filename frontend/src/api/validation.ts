import { apiRequest } from "./client";
import type {
  ValidationReportItem,
  ValidationReportListResponse,
  ValidationRunResponse,
  ValidationSummaryResponse,
} from "./types";

/** SETUP-07 / T-S07-014: запуск batch validation. */
export function runValidation(setupJobId: string): Promise<ValidationRunResponse> {
  return apiRequest(`/setup/${setupJobId}/validation/run`, {
    method: "POST",
    body: {},
  });
}

interface ListReportsOptions {
  status?: string;
  code?: string;
}

export function listValidationReports(
  setupJobId: string,
  options: ListReportsOptions = {},
): Promise<ValidationReportListResponse> {
  return apiRequest(`/setup/${setupJobId}/validation/reports`, {
    query: { status: options.status, code: options.code },
  });
}

export function getValidationReport(
  setupJobId: string,
  docId: string,
): Promise<ValidationReportItem> {
  return apiRequest(
    `/setup/${setupJobId}/validation/reports/${encodeURIComponent(docId)}`,
  );
}

export function refreshValidationReport(
  setupJobId: string,
  docId: string,
): Promise<ValidationReportItem> {
  return apiRequest(
    `/setup/${setupJobId}/validation/reports/${encodeURIComponent(docId)}/refresh`,
    { method: "POST", body: {} },
  );
}

export function getValidationSummary(
  setupJobId: string,
): Promise<ValidationSummaryResponse> {
  return apiRequest(`/setup/${setupJobId}/validation/summary`);
}
