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

// ============================================================
// SETUP-03 / T-S03-023: Source Registry types
// ============================================================

export type SourceDocumentStatus =
  | "uploaded"
  | "parsed"
  | "converted"
  | "failed"
  | "failed_validation"
  | "archived"
  | "removed"
  | "registered"
  | "metadata_extracted"
  | "waiting_for_parsing"
  | "parsing"
  | "parse_failed"
  | "sections_extracted"
  | "rag_cards_generating"
  | "rag_cards_generated"
  | "review_required"
  | "processing_failed"
  | "ready_for_indexing"
  | "published"
  | "deprecated";

export type ChangedByType = "service" | "user" | "system";

export type LineageTargetType =
  | "parsed_section"
  | "rag_card"
  | "chunk"
  | "embedding"
  | "processing_report"
  | "knowledge_base_version";

export type LineageRelationType =
  | "parsed_from"
  | "generated_from"
  | "derived_from"
  | "included_in"
  | "referenced_by";

export type ProcessingLogLevel = "debug" | "info" | "warning" | "error";

export type ProcessingLogStep =
  | "upload"
  | "registration"
  | "metadata_extraction"
  | "parsing"
  | "section_extraction"
  | "rag_card_generation"
  | "chunking"
  | "embedding"
  | "indexing"
  | "review"
  | "publish"
  | "cleanup"
  | "retry";

export interface PaginationDTO {
  page: number;
  page_size: number;
  total: number;
}

export interface LineageCounters {
  parsed_sections_count: number;
  rag_cards_count: number;
  chunks_count: number;
  embeddings_count: number;
  processing_reports_count: number;
  knowledge_base_versions_count: number;
}

export interface SourceDocumentListItemDTO {
  source_document_id: string;
  setup_job_id: string;
  filename: string;
  document_kind: string | null;
  content_type: string;
  size_bytes: number;
  checksum_short: string;
  status: SourceDocumentStatus;
  uploaded_by: string;
  uploaded_at: string;
  parsed_sections_count: number;
  rag_cards_count: number;
  chunks_count: number;
  last_error: string | null;
}

export interface ListSourcesResponse {
  setup_job_id: string;
  items: SourceDocumentListItemDTO[];
  pagination: PaginationDTO;
}

export interface SourceDocumentDetailsDTO {
  source_document_id: string;
  setup_job_id: string;
  filename: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  checksum: string;
  checksum_algorithm: string;
  storage_path: string | null;
  status: SourceDocumentStatus;
  document_kind: string | null;
  detected_language: string | null;
  uploaded_by: string;
  uploaded_at: string;
  parsed_at: string | null;
  error_message: string | null;
  user_metadata: Record<string, unknown>;
  system_metadata: Record<string, unknown>;
  counters: LineageCounters;
  last_status_change: string | null;
}

export interface StatusHistoryEntryDTO {
  status_history_id: string;
  source_document_id: string;
  old_status: SourceDocumentStatus | null;
  new_status: SourceDocumentStatus;
  reason: string | null;
  event_id: string;
  changed_by_type: ChangedByType;
  changed_by_id: string;
  changed_at: string;
  metadata: Record<string, unknown>;
}

export interface StatusHistoryResponse {
  source_document_id: string;
  items: StatusHistoryEntryDTO[];
  pagination: PaginationDTO;
}

export interface ProcessingLogEntryDTO {
  processing_log_id: string;
  source_document_id: string;
  setup_job_id: string;
  step: ProcessingLogStep;
  level: ProcessingLogLevel;
  message: string;
  error_code: string | null;
  event_id: string;
  created_at: string;
  payload: Record<string, unknown>;
}

export interface ProcessingLogResponse {
  source_document_id: string;
  items: ProcessingLogEntryDTO[];
  pagination: PaginationDTO;
}

export interface LineageRelationDTO {
  lineage_id: string;
  source_document_id: string;
  target_type: string;
  target_id: string;
  relation_type: string;
  created_by_service: string;
  event_id: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface LineageResponse {
  source_document_id: string;
  relations: LineageRelationDTO[];
  counters: LineageCounters;
}

export interface UpdateSourceMetadataRequest {
  tags?: string[];
  description?: string | null;
  owner_note?: string | null;
  custom_labels?: Record<string, string>;
}

export interface PatchSourceMetadataResponse {
  source_document_id: string;
  setup_job_id: string;
  user_metadata: Record<string, unknown>;
  updated_at: string;
  message?: string | null;
}

export interface RemoveSourceResponse {
  source_document_id: string;
  setup_job_id: string;
  status: string;
  message?: string | null;
}

export interface RetrySourceResponse {
  source_document_id: string;
  setup_job_id: string;
  status: string;
  from_step: string;
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

// ============================================================
// SETUP-04 / T-S04-023..026: Document parsing types
// ============================================================

export type ParseJobStatus =
  | "created"
  | "queued"
  | "running"
  | "completed"
  | "partial_success"
  | "failed"
  | "cancelled";

export type ParseJobDocumentStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed"
  | "skipped";

export type ParserStrategy =
  | "markdown"
  | "text"
  | "csv"
  | "json"
  | "pdf_text"
  | "docx"
  | "xlsx";

export type ParseErrorCode =
  | "UNSUPPORTED_PARSE_FORMAT"
  | "RAW_FILE_NOT_FOUND"
  | "TEXT_EXTRACTION_FAILED"
  | "PDF_TEXT_LAYER_NOT_FOUND"
  | "DOCX_EXTRACTION_FAILED"
  | "TABLE_EXTRACTION_FAILED"
  | "JSON_PARSE_FAILED"
  | "SECTION_DETECTION_FAILED"
  | "SECTION_SAVE_FAILED"
  | "PARSE_TIMEOUT"
  | "NO_PARSEABLE_DOCUMENTS"
  | "DOCUMENT_NOT_PARSEABLE_STATUS"
  | "PARSE_JOB_ALREADY_RUNNING";

export type SectionType =
  | "task"
  | "schema"
  | "analytics"
  | "glossary"
  | "validation_rule"
  | "question_template"
  | "other"
  | "unknown";

export type ParsedSectionStatus =
  | "extracted"
  | "classified"
  | "low_confidence"
  | "failed";

export interface CreateParseJobRequest {
  config?: Record<string, unknown> | null;
}

export interface ParseJobResponse {
  parse_job_id: string;
  setup_job_id: string;
  status: ParseJobStatus;
  total_documents: number;
  processed_documents: number;
  failed_documents: number;
  total_sections: number;
  low_confidence_sections: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
  error_code: ParseErrorCode | null;
  error_message: string | null;
}

export interface DocumentParseReportDTO {
  source_document_id: string;
  status: ParseJobDocumentStatus;
  parser_strategy: ParserStrategy | null;
  sections_count: number;
  sections_by_type: Record<string, number>;
  low_confidence_sections: number;
  errors: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown>>;
  created_at: string;
}

export interface ParseJobReportResponse {
  parse_job_id: string;
  setup_job_id: string;
  status: ParseJobStatus;
  documents: DocumentParseReportDTO[];
}

export interface ParsedSectionListItemDTO {
  section_id: string;
  source_document_id: string;
  title: string;
  section_type: SectionType;
  section_status: ParsedSectionStatus;
  confidence: number | null;
  heading_path: string[];
  section_index: number;
  parent_section_id: string | null;
  content_hash: string;
}

export interface ParsedSectionsResponse {
  parse_job_id: string;
  items: ParsedSectionListItemDTO[];
  pagination: PaginationDTO;
}

export interface CancelParseJobResponse {
  parse_job_id: string;
  status: ParseJobStatus;
  message: string;
}

export interface RetryParseDocumentResponse {
  parse_job_id: string;
  source_document_id: string;
  status: ParseJobDocumentStatus;
  message: string;
  new_parse_job_id: string | null;
}

// ============================================================
// SETUP-05 RAG cards generation (T-S05-033)
// ============================================================

export type RAGCardGenerationJobStatus =
  | "created"
  | "queued"
  | "running"
  | "partial_success"
  | "completed"
  | "failed"
  | "cancelled";

export type CardConfidenceLevel = "high" | "medium" | "low";

export type DocType =
  | "schema_card"
  | "task_card"
  | "analytics_card"
  | "field_definition_card"
  | "feature_pattern_card"
  | "validation_rule_card"
  | "question_template_card";

export type CardStatus =
  | "draft"
  | "generated"
  | "generation_failed"
  | "metadata_incomplete"
  | "body_empty"
  | "low_confidence"
  | "review_required"
  | "ready_for_metadata_validation"
  | "metadata_validated"
  | "approved"
  | "rejected"
  | "chunked"
  | "embedded"
  | "indexed"
  | "published"
  | "deprecated";

export interface GenerateRAGCardsOptions {
  confidence_threshold?: number | null;
  allow_multiple_cards_per_section?: boolean;
  mark_low_confidence_as_review_required?: boolean;
  save_llm_trace?: boolean;
}

export interface GenerateRAGCardsRequest {
  section_ids?: string[] | null;
  source_document_ids?: string[] | null;
  generation_mode?: "llm" | "template" | "hybrid";
  ontology_version?: string;
  metadata_schema_version?: string;
  prompt_template_version?: string;
  llm_model?: string;
  options?: GenerateRAGCardsOptions;
  generation_request_id?: string | null;
}

export interface RAGCardGenerationJobResponse {
  generation_job_id: string;
  setup_job_id: string;
  requested_by: string;
  status: RAGCardGenerationJobStatus;
  total_sections: number;
  processed_sections: number;
  generated_cards: number;
  failed_sections: number;
  review_required_cards: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
  error_code: string | null;
  error_message: string | null;
  config: Record<string, unknown>;
}

export interface CardGenerationSummaryDTO {
  total_sections: number;
  processed_sections: number;
  generated_cards: number;
  failed_sections: number;
  review_required_cards: number;
  cards_by_type: Record<string, number>;
}

export interface RAGCardGenerationReportResponse {
  generation_report_id: string;
  generation_job_id: string;
  status: RAGCardGenerationJobStatus;
  summary: CardGenerationSummaryDTO;
  errors: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown>>;
  created_at: string;
}

export interface RAGCardListItem {
  doc_id: string;
  setup_job_id: string;
  card_version: string;
  doc_type: string;
  title: string;
  status: string;
  confidence_level: string | null;
  primary_source_section_id: string | null;
  source_document_ids: string[];
  retrieval_tags: string[];
  created_at: string;
  updated_at: string;
  review_required_reason: string | null;
}

export interface RAGCardListResponse {
  setup_job_id: string;
  items: RAGCardListItem[];
  pagination: PaginationDTO;
}

export interface RAGCardSourceTraceDTO {
  source_link_id: string;
  source_document_id: string;
  source_section_id: string;
  relation_type: string;
}

export interface RAGCardDetails {
  doc_id: string;
  setup_job_id: string;
  card_version: string;
  doc_type: string;
  title: string;
  status: string;
  confidence_level: string | null;
  front_matter: Record<string, unknown>;
  body_markdown: string;
  source_document_ids: string[];
  source_section_ids: string[];
  review_required_reason: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  markdown_artifact_id: string | null;
  available_versions: string[];
}

export interface RAGCardPreview {
  doc_id: string;
  card_version: string;
  doc_type: string;
  title: string;
  status: string;
  confidence_level: string | null;
  front_matter: Record<string, unknown>;
  body_markdown: string;
  source_trace: RAGCardSourceTraceDTO[];
}

export interface RegenerateRAGCardRequest {
  reason: string;
  override_doc_type?: string | null;
  regenerate_request_id?: string | null;
}

export interface RegenerateRAGCardResponse {
  doc_id: string;
  new_card_version: string;
  generation_job_id: string;
  status: RAGCardGenerationJobStatus;
  message: string;
}

export interface CancelRAGCardJobResponse {
  generation_job_id: string;
  status: RAGCardGenerationJobStatus;
  message: string;
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

// ============================================================
// SETUP-06 RAG card review (T-S06-029)
// ============================================================

export type ReviewDecisionStr = "approve" | "reject";

export interface ReviewRAGCardDecisionRequest {
  review_decision_id?: string | null;
  card_version?: string | null;
  decision: ReviewDecisionStr;
  reason?: string | null;
  comment?: string | null;
}

export interface EditRAGCardRequest {
  expected_version: string;
  metadata_patch?: Record<string, unknown> | null;
  body_markdown?: string | null;
  change_reason?: string | null;
}

export interface RegenerateRAGCardReviewRequest {
  reason: string;
  instruction?: string | null;
  regenerate_request_id?: string | null;
}

export interface BulkReviewItem {
  doc_id: string;
  card_version: string;
}

export interface BulkReviewRequest {
  bulk_review_id?: string | null;
  decision: "approve";
  items: BulkReviewItem[];
  comment?: string | null;
}

export interface RAGCardReviewListItem {
  doc_id: string;
  card_version: string;
  title: string;
  doc_type: string;
  status: string;
  confidence_level: string | null;
  source_document_id: string | null;
  source_section_id: string | null;
  validation_errors_count: number;
  warnings_count: number;
  review_required_reason: string | null;
  last_reviewed_by: string | null;
  updated_at: string;
}

export interface ReviewSummary {
  total: number;
  by_status: Record<string, number>;
}

export interface RAGCardReviewListResponse {
  setup_job_id: string;
  items: RAGCardReviewListItem[];
  total: number;
  page: number;
  page_size: number;
  summary: ReviewSummary;
}

export interface ValidationItemDTO {
  code: string;
  message: string;
}

export interface ValidationReportDTO {
  critical_errors: ValidationItemDTO[];
  warnings: ValidationItemDTO[];
}

export interface ReviewPermissionsDTO {
  can_approve: boolean;
  can_reject: boolean;
  can_edit: boolean;
  can_regenerate: boolean;
}

export interface RAGCardReviewDetailsDTO {
  doc_id: string;
  card_version: string;
  title: string;
  doc_type: string;
  status: string;
  confidence_level: string | null;
  metadata: Record<string, unknown>;
  body_markdown: string;
  source_trace: Record<string, unknown>;
  validation: ValidationReportDTO;
  review_log_count: number;
  permissions: ReviewPermissionsDTO;
}

export interface ApproveResponse {
  doc_id: string;
  card_version: string;
  status: string;
  review_decision_id: string;
  reviewed_by: string;
  reviewed_at: string;
}

export interface RejectResponse {
  doc_id: string;
  card_version: string;
  status: string;
  review_decision_id: string;
  reason: string;
  reviewed_by: string;
  reviewed_at: string;
}

export interface EditResponse {
  doc_id: string;
  previous_version: string;
  new_version: string;
  status: string;
  diff_available: boolean;
  edited_by: string;
  edited_at: string;
}

export interface RegenerateReviewResponse {
  doc_id: string;
  card_version: string;
  status: string;
  regenerate_request_id: string;
  generation_job_id: string | null;
  message: string;
}

export interface BulkReviewItemResult {
  doc_id: string;
  status: string;
  card_version: string | null;
  error: string | null;
}

export interface BulkReviewResponse {
  bulk_review_id: string;
  total: number;
  approved: number;
  errors: number;
  results: BulkReviewItemResult[];
}

export interface CardVersionItemDTO {
  doc_id: string;
  card_version: string;
  parent_card_version: string | null;
  status: string;
  markdown_artifact_id: string;
  body_hash: string;
  created_by: string;
  created_at: string;
  change_reason: string | null;
  is_current: boolean;
}

export interface RAGCardVersionsResponse {
  doc_id: string;
  versions: CardVersionItemDTO[];
}

export interface CardDiffResponse {
  doc_id: string;
  from_version: string;
  to_version: string;
  body_changed: boolean;
  metadata_from: Record<string, unknown>;
  metadata_to: Record<string, unknown>;
}

export interface ReviewLogItemDTO {
  review_log_id: string;
  setup_job_id: string;
  doc_id: string;
  card_version: string;
  event_type: string;
  actor_id: string;
  actor_role: string;
  message: string;
  before_status: string | null;
  after_status: string | null;
  created_at: string;
  payload: Record<string, unknown>;
}

export interface ReviewLogResponse {
  doc_id: string;
  items: ReviewLogItemDTO[];
}

// ============================================================
// SETUP-07 validation (T-S07-014)
// ============================================================

export interface ValidationIssueItem {
  code: string;
  field: string | null;
  message: string;
  severity: string;
  details: Record<string, unknown>;
}

export interface ValidationCheckItem {
  name: string;
  passed: boolean;
}

export interface ValidationReportItem {
  validation_report_id: string;
  setup_job_id: string | null;
  doc_id: string;
  card_version: string | null;
  status: string;
  errors: ValidationIssueItem[];
  warnings: ValidationIssueItem[];
  checks: ValidationCheckItem[];
  policy_used: string | null;
  validation_run_id: string | null;
  validator_name: string;
  created_at: string;
}

export interface ValidationReportListResponse {
  setup_job_id: string;
  items: ValidationReportItem[];
  total: number;
}

export interface ValidationRunResponse {
  validation_run_id: string;
  setup_job_id: string;
  status: string;
  triggered_by: string;
  policy: string;
  total: number;
  passed: number;
  warnings: number;
  failed: number;
  review_required: number;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
}

export interface ValidationSummaryResponse {
  setup_job_id: string;
  total: number;
  passed: number;
  warnings: number;
  failed: number;
  review_required: number;
  by_code: Record<string, number>;
  last_run_id: string | null;
}

// ============================================================
// SETUP-08 chunking (T-S08-014)
// ============================================================

export interface ChunkItem {
  chunk_id: string;
  doc_id: string;
  chunk_type: string;
  section_title: string | null;
  chunk_text: string;
  embedding_text: string;
  metadata: Record<string, unknown>;
  priority: number;
  source_section_id: string | null;
  token_count: number | null;
  created_at: string;
  status: string;
}

export interface ChunkManifestResponse {
  manifest_id: string;
  setup_job_id: string;
  total_chunks: number;
  by_type: Record<string, number>;
  chunks: ChunkItem[];
  created_at: string;
  created_by: string;
}

export interface ChunkPreviewResponse {
  doc_id: string;
  chunks: ChunkItem[];
}

export interface ChunkingRunResponse {
  chunking_run_id: string;
  setup_job_id: string;
  manifest_id: string;
  triggered_by: string;
  total_cards: number;
  chunks_created: number;
  duration_ms: number;
  started_at: string;
  finished_at: string;
}

// ============================================================
// OBS-LLM-01: LLM call stats
// ============================================================

export interface LLMModelStats {
  model: string;
  count: number;
  avg_ms: number;
  p50_ms: number;
  p95_ms: number;
  last_ms: number | null;
}

export interface LLMStatsResponse {
  models: LLMModelStats[];
  total_calls: number;
}
