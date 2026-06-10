/**
 * UploadedFilesTable (SETUP-02 / T-S02-020).
 *
 * Таблица загруженных документов с:
 * - sortable колонками (filename, size, uploaded_at, status)
 * - фильтром по status (uploaded / failed_validation / removed / archived)
 * - actions: Delete (DELETE /documents/{id}), Details (modal)
 * - empty state
 *
 * Подключается к API через React Query: лист берётся из listDocuments,
 * delete вызывает deleteDocument и invalidate'ит кеш.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { deleteDocument } from "../../api/setup";
import { ApiError, type SourceDocumentResponse } from "../../api/types";

interface UploadedFilesTableProps {
  setupJobId: string;
  documents: SourceDocumentResponse[];
  /** Optional: показать ошибку загрузки списка (от listDocuments). */
  loading?: boolean;
}

type SortKey = "filename" | "size" | "uploaded_at" | "status";
type SortDir = "asc" | "desc";

const STATUS_BADGE: Record<string, string> = {
  uploaded: "badge-uploaded",
  parsed: "badge-uploaded",
  converted: "badge-uploaded",
  failed: "badge-rejected",
  failed_validation: "badge-rejected",
  archived: "badge-pending",
  removed: "badge-pending",
};

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

export function UploadedFilesTable({
  setupJobId,
  documents,
  loading = false,
}: UploadedFilesTableProps): JSX.Element {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sortKey, setSortKey] = useState<SortKey>("uploaded_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [detailsDocId, setDetailsDocId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (sourceDocumentId: string) =>
      deleteDocument(setupJobId, sourceDocumentId),
    onSuccess: async () => {
      setConfirmDeleteId(null);
      await qc.invalidateQueries({ queryKey: ["docs", setupJobId] });
    },
  });

  const visible = useMemo(() => {
    const filtered = statusFilter
      ? documents.filter((d) => d.status === statusFilter)
      : documents;
    const sorted = [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "filename":
          cmp = a.filename.localeCompare(b.filename);
          break;
        case "size":
          cmp = a.size_bytes - b.size_bytes;
          break;
        case "uploaded_at":
          cmp = a.uploaded_at.localeCompare(b.uploaded_at);
          break;
        case "status":
          cmp = a.status.localeCompare(b.status);
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return sorted;
  }, [documents, sortDir, sortKey, statusFilter]);

  const allStatuses = useMemo(
    () => Array.from(new Set(documents.map((d) => d.status))).sort(),
    [documents],
  );

  const headerProps = (key: SortKey) => ({
    "data-testid": `sort-${key}`,
    onClick: () => {
      if (sortKey === key) {
        setSortDir(sortDir === "asc" ? "desc" : "asc");
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    style: { cursor: "pointer" as const },
  });

  const sortIndicator = (key: SortKey) =>
    sortKey === key ? (sortDir === "asc" ? " ▲" : " ▼") : "";

  const deleteError =
    deleteMutation.error instanceof ApiError
      ? deleteMutation.error.message
      : deleteMutation.error?.message;

  const detailsDoc = detailsDocId
    ? documents.find((d) => d.source_document_id === detailsDocId) ?? null
    : null;

  return (
    <div className="uploaded-files-table" data-testid="uploaded-files-table">
      <div className="row" style={{ marginBottom: 12 }}>
        <label>
          Фильтр статус:{" "}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            data-testid="status-filter"
          >
            <option value="">Все</option>
            {allStatuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <span className="text-muted">Найдено: {visible.length}</span>
      </div>

      {loading ? (
        <p className="text-muted">Загружаем список…</p>
      ) : visible.length === 0 ? (
        <p className="text-muted" data-testid="empty-state">
          {statusFilter
            ? `Нет документов в статусе "${statusFilter}".`
            : "Документов пока нет."}
        </p>
      ) : (
        <table className="docs-table">
          <thead>
            <tr>
              <th {...headerProps("filename")}>
                Имя{sortIndicator("filename")}
              </th>
              <th {...headerProps("size")}>Размер{sortIndicator("size")}</th>
              <th>checksum</th>
              <th {...headerProps("status")}>Статус{sortIndicator("status")}</th>
              <th {...headerProps("uploaded_at")}>
                Загружен{sortIndicator("uploaded_at")}
              </th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((d) => {
              const isRemoved = d.status === "removed";
              return (
                <tr
                  key={d.source_document_id}
                  className={isRemoved ? "row-removed" : ""}
                  data-testid={`doc-row-${d.source_document_id}`}
                >
                  <td className="filename">{d.filename}</td>
                  <td className="text-muted">{formatBytes(d.size_bytes)}</td>
                  <td className="text-muted">
                    <code>{d.checksum.slice(0, 12)}…</code>
                  </td>
                  <td>
                    <span
                      className={`badge ${STATUS_BADGE[d.status] ?? "badge-pending"}`}
                      data-testid={`status-${d.source_document_id}`}
                    >
                      {d.status}
                    </span>
                  </td>
                  <td className="text-muted">{formatDate(d.uploaded_at)}</td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setDetailsDocId(d.source_document_id)}
                      data-testid={`details-${d.source_document_id}`}
                    >
                      Подробно
                    </button>{" "}
                    {!isRemoved && (
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={() =>
                          setConfirmDeleteId(d.source_document_id)
                        }
                        disabled={deleteMutation.isPending}
                        data-testid={`delete-${d.source_document_id}`}
                      >
                        Удалить
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {deleteError && (
        <div className="error-text" data-testid="delete-error">
          {deleteError}
        </div>
      )}

      {confirmDeleteId && (
        <ConfirmDeleteDialog
          docId={confirmDeleteId}
          docName={
            documents.find((d) => d.source_document_id === confirmDeleteId)
              ?.filename ?? confirmDeleteId
          }
          onConfirm={() => deleteMutation.mutate(confirmDeleteId)}
          onCancel={() => setConfirmDeleteId(null)}
          pending={deleteMutation.isPending}
        />
      )}

      {detailsDoc && (
        <DocumentDetailsDialog
          document={detailsDoc}
          onClose={() => setDetailsDocId(null)}
        />
      )}
    </div>
  );
}

interface ConfirmDeleteDialogProps {
  docId: string;
  docName: string;
  onConfirm: () => void;
  onCancel: () => void;
  pending: boolean;
}

function ConfirmDeleteDialog({
  docName,
  onConfirm,
  onCancel,
  pending,
}: ConfirmDeleteDialogProps): JSX.Element {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
      className="modal-backdrop"
      data-testid="confirm-delete-dialog"
      onClick={onCancel}
    >
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3 id="delete-dialog-title">Удалить документ?</h3>
        <p>
          Документ <strong>{docName}</strong> будет помечен как удалённый.
          Файл больше не будет участвовать в RAG pipeline.
        </p>
        <div className="btn-row">
          <button
            className="btn btn-danger"
            onClick={onConfirm}
            disabled={pending}
            data-testid="confirm-delete-yes"
          >
            {pending ? "Удаляем…" : "Удалить"}
          </button>
          <button
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={pending}
            data-testid="confirm-delete-no"
          >
            Отмена
          </button>
        </div>
      </div>
    </div>
  );
}

interface DocumentDetailsDialogProps {
  document: SourceDocumentResponse;
  onClose: () => void;
}

function DocumentDetailsDialog({
  document: doc,
  onClose,
}: DocumentDetailsDialogProps): JSX.Element {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="details-dialog-title"
      className="modal-backdrop"
      data-testid="document-details-dialog"
      onClick={onClose}
    >
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3 id="details-dialog-title">Документ</h3>
        <dl className="kv-grid">
          <dt className="key">source_document_id</dt>
          <dd>
            <code>{doc.source_document_id}</code>
          </dd>
          <dt className="key">filename</dt>
          <dd>{doc.filename}</dd>
          <dt className="key">content_type</dt>
          <dd>{doc.content_type}</dd>
          <dt className="key">size_bytes</dt>
          <dd>{doc.size_bytes}</dd>
          <dt className="key">checksum</dt>
          <dd>
            <code>{doc.checksum}</code>
          </dd>
          <dt className="key">status</dt>
          <dd>{doc.status}</dd>
          <dt className="key">uploaded_by</dt>
          <dd>{doc.uploaded_by}</dd>
          <dt className="key">uploaded_at</dt>
          <dd>{doc.uploaded_at}</dd>
          {doc.storage_path && (
            <>
              <dt className="key">storage_path</dt>
              <dd>
                <code>{doc.storage_path}</code>
              </dd>
            </>
          )}
        </dl>
        <div className="btn-row">
          <button
            className="btn btn-secondary"
            onClick={onClose}
            data-testid="details-close"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
