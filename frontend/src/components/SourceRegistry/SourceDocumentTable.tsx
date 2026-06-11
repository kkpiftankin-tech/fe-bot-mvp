/**
 * SourceDocumentTable (SETUP-03 / T-S03-024).
 *
 * Таблица source documents с status badges, counters, actions:
 * - Details — открывает SourceDocumentDetailsDrawer
 * - Retry — для PARSE_FAILED/PROCESSING_FAILED
 * - Delete — soft-delete (для всех кроме published без admin)
 */
import type {
  SourceDocumentListItemDTO,
  SourceDocumentStatus,
} from "../../api/types";

interface SourceDocumentTableProps {
  items: SourceDocumentListItemDTO[];
  onDetails: (doc_id: string) => void;
  onRetry?: (doc_id: string) => void;
  onDelete?: (doc_id: string) => void;
  loading?: boolean;
}

const STATUS_BADGE: Record<string, string> = {
  registered: "badge-uploaded",
  uploaded: "badge-uploaded",
  parsed: "badge-uploaded",
  parsing: "badge-uploading",
  sections_extracted: "badge-uploaded",
  rag_cards_generating: "badge-uploading",
  rag_cards_generated: "badge-uploaded",
  review_required: "badge-duplicate",
  ready_for_indexing: "badge-uploaded",
  published: "badge-uploaded",
  parse_failed: "badge-rejected",
  processing_failed: "badge-rejected",
  failed: "badge-rejected",
  failed_validation: "badge-rejected",
  archived: "badge-pending",
  removed: "badge-pending",
  deprecated: "badge-pending",
};

const RETRYABLE: Set<SourceDocumentStatus> = new Set([
  "parse_failed",
  "processing_failed",
]);

const DELETABLE_BLOCKED: Set<SourceDocumentStatus> = new Set([
  "published",
  "removed",
]);

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("ru-RU", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function SourceDocumentTable({
  items,
  onDetails,
  onRetry,
  onDelete,
  loading = false,
}: SourceDocumentTableProps): JSX.Element {
  if (loading) {
    return (
      <p className="text-muted" data-testid="sources-loading">
        Загружаем реестр источников…
      </p>
    );
  }
  if (items.length === 0) {
    return (
      <p className="text-muted" data-testid="sources-empty">
        В этом setup-job нет документов.
      </p>
    );
  }
  return (
    <table className="docs-table" data-testid="sources-table">
      <thead>
        <tr>
          <th>Имя</th>
          <th>Тип</th>
          <th>Размер</th>
          <th>Статус</th>
          <th>Секции</th>
          <th>Карточки</th>
          <th>Загружен</th>
          <th>Действия</th>
        </tr>
      </thead>
      <tbody>
        {items.map((d) => {
          const retryable = onRetry && RETRYABLE.has(d.status);
          const deletable = onDelete && !DELETABLE_BLOCKED.has(d.status);
          return (
            <tr
              key={d.source_document_id}
              data-testid={`source-row-${d.source_document_id}`}
            >
              <td className="filename">{d.filename}</td>
              <td className="text-muted">{d.document_kind ?? "—"}</td>
              <td className="text-muted">{formatBytes(d.size_bytes)}</td>
              <td>
                <span
                  className={`badge ${STATUS_BADGE[d.status] ?? "badge-pending"}`}
                  data-testid={`source-status-${d.source_document_id}`}
                >
                  {d.status}
                </span>
                {d.last_error && (
                  <div
                    className="error-text"
                    data-testid={`source-error-${d.source_document_id}`}
                  >
                    {d.last_error}
                  </div>
                )}
              </td>
              <td className="text-muted">{d.parsed_sections_count}</td>
              <td className="text-muted">{d.rag_cards_count}</td>
              <td className="text-muted">{formatDate(d.uploaded_at)}</td>
              <td>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => onDetails(d.source_document_id)}
                  data-testid={`source-details-${d.source_document_id}`}
                >
                  Подробно
                </button>
                {retryable && (
                  <>
                    {" "}
                    <button
                      type="button"
                      className="btn"
                      onClick={() => onRetry?.(d.source_document_id)}
                      data-testid={`source-retry-${d.source_document_id}`}
                    >
                      Retry
                    </button>
                  </>
                )}
                {deletable && (
                  <>
                    {" "}
                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={() => onDelete?.(d.source_document_id)}
                      data-testid={`source-delete-${d.source_document_id}`}
                    >
                      Удалить
                    </button>
                  </>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
