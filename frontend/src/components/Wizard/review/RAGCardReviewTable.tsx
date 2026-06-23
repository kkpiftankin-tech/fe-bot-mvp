import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listReviewCards } from "../../../api/review";

interface Props {
  setupJobId: string;
  onSelect: (docId: string) => void;
}

const STATUS_OPTIONS = [
  "",
  "review_required",
  "generated",
  "approved",
  "rejected",
  "edited",
  "regenerate_requested",
  "validation_failed",
  "metadata_incomplete",
  "low_confidence",
];

const CONFIDENCE_OPTIONS: ("" | "high" | "medium" | "low")[] = [
  "",
  "high",
  "medium",
  "low",
];

export function RAGCardReviewTable({ setupJobId, onSelect }: Props): JSX.Element {
  const [statusFilter, setStatusFilter] = useState<string>("review_required");
  const [confidenceFilter, setConfidenceFilter] = useState<
    "" | "high" | "medium" | "low"
  >("");
  const [hasErrors, setHasErrors] = useState<boolean>(false);
  const [page, setPage] = useState<number>(1);
  const pageSize = 20;

  const query = useQuery({
    queryKey: [
      "reviewCards",
      setupJobId,
      statusFilter,
      confidenceFilter,
      hasErrors,
      page,
    ],
    queryFn: () =>
      listReviewCards(setupJobId, {
        status: statusFilter || undefined,
        confidenceLevel: confidenceFilter || undefined,
        hasValidationErrors: hasErrors || undefined,
        page,
        pageSize,
      }),
    enabled: !!setupJobId,
  });

  const items = query.data?.items ?? [];
  const summary = query.data?.summary;

  return (
    <div data-testid="review-table">
      <div className="btn-row" style={{ gap: 12, flexWrap: "wrap" }}>
        <label>
          status{" "}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            data-testid="filter-status"
          >
            {STATUS_OPTIONS.map((v) => (
              <option key={v} value={v}>
                {v || "— любой —"}
              </option>
            ))}
          </select>
        </label>
        <label>
          confidence{" "}
          <select
            value={confidenceFilter}
            onChange={(e) => {
              setConfidenceFilter(e.target.value as "" | "high" | "medium" | "low");
              setPage(1);
            }}
            data-testid="filter-confidence"
          >
            {CONFIDENCE_OPTIONS.map((v) => (
              <option key={v} value={v}>
                {v || "— любой —"}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={hasErrors}
            onChange={(e) => setHasErrors(e.target.checked)}
            data-testid="filter-errors"
          />{" "}
          только с ошибками
        </label>
      </div>

      {summary && (
        <p className="text-muted" data-testid="review-summary">
          Всего: {summary.total} ·{" "}
          {Object.entries(summary.by_status)
            .map(([k, v]) => `${k}: ${v}`)
            .join(" · ")}
        </p>
      )}

      {query.isLoading && <p>Загрузка…</p>}
      {query.error && (
        <div className="banner banner-error">
          {query.error instanceof Error ? query.error.message : "Ошибка"}
        </div>
      )}

      {!query.isLoading && items.length === 0 && (
        <p className="text-muted" data-testid="empty-state">
          Карточек по фильтрам не найдено.
        </p>
      )}

      {items.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>doc_id</th>
              <th>title</th>
              <th>type</th>
              <th>status</th>
              <th>confidence</th>
              <th>version</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={`${c.doc_id}.${c.card_version}`}>
                <td>
                  <code>{c.doc_id}</code>
                </td>
                <td>{c.title}</td>
                <td>{c.doc_type}</td>
                <td>{c.status}</td>
                <td>{c.confidence_level ?? "—"}</td>
                <td>{c.card_version}</td>
                <td>
                  <button
                    className="btn btn-secondary"
                    onClick={() => onSelect(c.doc_id)}
                    data-testid={`review-${c.doc_id}`}
                  >
                    Открыть
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {query.data && query.data.total > pageSize && (
        <div className="btn-row" style={{ marginTop: 12 }}>
          <button
            className="btn btn-secondary"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            ← Назад
          </button>
          <span className="text-muted">
            Страница {page} из {Math.max(1, Math.ceil(query.data.total / pageSize))}
          </span>
          <button
            className="btn btn-secondary"
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= Math.ceil(query.data.total / pageSize)}
          >
            Вперёд →
          </button>
        </div>
      )}
    </div>
  );
}
