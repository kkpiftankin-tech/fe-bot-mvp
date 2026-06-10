// Типы, отражающие схемы из backend (schemas/ + api/setup/dto.py).
// При смене backend контракта обновлять здесь.

export type SetupJobStatus =
  | "draft"
  | "files_uploaded"
  | "parsing"
  | "sections_extracted"
  | "rag_cards_generating"
  | "metadata_validating"
  | "review_required"
  | "chunking"
  | "embedding"
  | "indexing"
  | "retrieval_testing"
  | "publishing"
  | "ready"
  | "failed"
  | "cancelled";

export interface SetupJobResponse {
  setup_job_id: string;
  user_id: string;
  project_name: string;
  status: SetupJobStatus;
  current_step: string | null;
  progress_percent: number;
  source_documents_count: number;
  error_count: number;
  warning_count: number;
  started_at: string | null;
  finished_at: string | null;
  knowledge_base_version: string | null;
  message?: string | null;
}

export interface SetupProgressResponse {
  setup_job_id: string;
  status: SetupJobStatus;
  current_step: string | null;
  progress_percent: number;
  error_count: number;
  warning_count: number;
}

export interface CreateSetupJobRequest {
  project_name: string;
  domain?: string | null;
  description?: string | null;
  tags?: string[];
  embedding_model?: string | null;
  review_policy?: "strict" | "allow_warnings";
  retrieval_test_profile?: "basic" | "domain" | "custom";
}

export interface SourceDocumentResponse {
  source_document_id: string;
  setup_job_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  checksum: string;
  status: string;
  uploaded_by: string;
  uploaded_at: string;
  storage_path?: string | null;
}

/**
 * UploadErrorCode (SETUP-02 / T-S02-002).
 * Зеркало schemas/setup/upload_errors.py:UploadErrorCode.
 * Стабильный machine-readable контракт между frontend и backend.
 */
export type UploadErrorCode =
  | "MISSING_FILES"
  | "UNSUPPORTED_FILE_TYPE"
  | "FILE_TOO_LARGE"
  | "BATCH_TOO_LARGE"
  | "EMPTY_FILE"
  | "INVALID_FILENAME"
  | "DUPLICATE_FILE"
  | "SETUP_JOB_NOT_FOUND"
  | "SETUP_JOB_NOT_UPLOADABLE"
  | "INSUFFICIENT_PERMISSIONS"
  | "OBJECT_STORAGE_UNAVAILABLE"
  | "OBJECT_STORAGE_WRITE_FAILED"
  | "SOURCE_REGISTRY_UNAVAILABLE"
  | "CHECKSUM_CALCULATION_FAILED"
  | "UPLOAD_STREAM_INTERRUPTED"
  | "INTERNAL_UPLOAD_ERROR";

export interface UploadFileError {
  filename: string;
  error_code: UploadErrorCode;
  message: string;
  details?: Record<string, unknown>;
}

export interface UploadSummary {
  files_total: number;
  files_uploaded: number;
  files_rejected: number;
  duplicates_detected: number;
}

export interface UploadDocumentsResponse {
  setup_job_id: string;
  /** SETUP-02 / T-S02-009: server-generated batch identifier. */
  upload_batch_id?: string | null;
  /** SETUP-02 / T-S02-003: aggregate counters. */
  summary?: UploadSummary | null;
  uploaded: SourceDocumentResponse[];
  skipped_duplicates: SourceDocumentResponse[];
  /** SETUP-02 / T-S02-006: per-file errors при partial success. */
  errors?: UploadFileError[];
  job_status: SetupJobStatus;
  message?: string | null;
}

export interface ListDocumentsResponse {
  setup_job_id: string;
  documents: SourceDocumentResponse[];
  count: number;
}

export interface RemoveDocumentResponse {
  setup_job_id: string;
  source_document_id: string;
  status: string;
  message?: string | null;
}

export interface VectorIndexSummary {
  index_version: string;
  status: string;
  embedding_model: string;
  chunks_count: number;
  indexed_chunks_count: number;
  failed_chunks_count: number;
  collection_names: string[];
}

export interface RunPipelineResponse {
  setup_job_id: string;
  final_status: SetupJobStatus;
  documents_total: number;
  documents_parsed: number;
  documents_failed: number;
  sections_extracted: number;
  cards_generated: number;
  cards_review_required: number;
  cards_used_fallback: number;
  cards_metadata_validated: number;
  validation_warnings: number;
  validation_failed: number;
  cards_approved_auto: number;
  chunks_total: number;
  chunks_indexed: number;
  chunks_failed: number;
  vector_index: VectorIndexSummary | null;
  errors: string[];
  message?: string | null;
}

export interface RAGCardSummary {
  doc_id: string;
  doc_type: string;
  title: string;
  version: string;
  status: string;
  confidence_level: string | null;
  domain: string[];
  phase: string[];
  retrieval_tags: string[];
  source_document_ids: string[];
  created_at: string;
  updated_at: string;
  body_preview?: string | null;
  body_markdown?: string | null;
  history: string[];
}

export interface ListCardsResponse {
  setup_job_id: string;
  cards: RAGCardSummary[];
  count: number;
  filters: Record<string, string | null>;
}

export type ReviewDecision = "approve" | "reject" | "edit" | "regenerate";

export interface ReviewRAGCardRequest {
  decision: ReviewDecision;
  comment?: string | null;
  updated_title?: string | null;
  updated_body_markdown?: string | null;
}

export interface ReviewRAGCardResponse {
  setup_job_id: string;
  decision: string;
  affected_doc_id: string;
  new_doc_id?: string | null;
  new_status: string;
  message?: string | null;
}

export interface GoldenQueryDTO {
  query: string;
  expected_doc_ids: string[];
  doc_types?: string[] | null;
  description?: string | null;
}

export interface RunRetrievalTestsRequest {
  golden_queries: GoldenQueryDTO[];
  top_k?: number;
  threshold_recall_at_5?: number | null;
}

export interface PerQueryEvalDTO {
  query: string;
  expected_doc_ids: string[];
  retrieved_doc_ids: string[];
  recall_at_k: number;
  precision_at_k: number;
  reciprocal_rank: number;
  is_no_context: boolean;
  error_message?: string | null;
}

export interface EvalReportResponse {
  setup_job_id: string;
  queries_total: number;
  queries_errored: number;
  top_k: number;
  threshold_recall_at_5: number;
  mean_recall_at_k: number;
  mean_precision_at_k: number;
  mean_reciprocal_rank: number;
  no_context_rate: number;
  passed: boolean;
  per_query: PerQueryEvalDTO[];
  message?: string | null;
}

export interface PublishKBRequest {
  eval_report?: EvalReportResponse | null;
  comment?: string | null;
}

export interface PublishKBResponse {
  setup_job_id: string;
  knowledge_base_version: string;
  status: string;
  is_active: boolean;
  published_by: string | null;
  published_at: string | null;
  index_version: string | null;
  rag_card_count: number;
  chunk_count: number;
  message?: string | null;
}

export interface ProcessingReportResponse {
  setup_job_id: string;
  status: SetupJobStatus;
  project_name: string;
  user_id: string;
  progress_percent: number;
  error_count: number;
  warning_count: number;
  documents_count: number;
  cards_count: number;
  cards_approved: number;
  cards_review_required: number;
  cards_deprecated: number;
  knowledge_base_version: string | null;
  knowledge_base_status: string | null;
  knowledge_base_is_active: boolean;
  chunks_indexed: number;
  index_version: string | null;
  eval_passed: boolean | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface ReindexResponse {
  setup_job_id: string;
  index_version: string;
  chunks_total: number;
  chunks_indexed: number;
  chunks_failed: number;
  vector_index: VectorIndexSummary;
  errors: string[];
  message?: string | null;
}

export interface ApiErrorDetail {
  detail: string;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly body: ApiErrorDetail | unknown;

  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}
