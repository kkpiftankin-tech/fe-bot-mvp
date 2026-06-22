import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listRAGCards } from "../../../api/rag_cards";
import type { CardConfidenceLevel } from "../../../api/types";

const DOC_TYPE_OPTIONS = [
  "",
  "schema_card",
  "task_card",
  "analytics_card",
  "field_definition_card",
  "feature_pattern_card",
  "validation_rule_card",
  "question_template_card",
];

const STATUS_OPTIONS = [
  "",
  "generated",
  "generation_failed",
  "review_required",
  "low_confidence",
  "metadata_incomplete",
  "body_empty",
  "approved",
];

const CONFIDENCE_OPTIONS: ("" | CardConfidenceLevel)[] = [
  "",
  "high",
  "medium",
  "low",
];

interface Props {
  setupJobId: string;
  onSelect: (docId: string) => void;
}

export function RAGCardList({ setupJobId, onSelect }: Props): JSX.Element {
  const [docType, setDocType] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [confidenceLevel, setConfidenceLevel] = useState<
    "" | CardConfidenceLevel
  >("");
  const [page, setPage] = useState<number>(1);
  const pageSize = 20;

  const query = useQuery({
    queryKey: [
      "ragCardList",
      setupJobId,
      docType,
      status,
      confidenceLevel,
      page,
    ],
    queryFn: () =>
      listRAGCards(setupJobId, {
        docType: docType || undefined,
        status: status || undefined,
        confidenceLevel: confidenceLevel || undefined,
        page,
        pageSize,
      }),
    enabled: !!setupJobId,
  });

  const items = query.data?.items ?? [];
  const pagination = query.data?.pagination;

  return (
    <div style={{ marginTop: 24 }} data-testid="rag-card-list">
      <h3>RAG-карточки</h3>

      <div className="btn-row" style={{ gap: 12, flexWrap: "wrap" }}>
        <label>
          doc_type{" "}
          <select
            value={docType}
            onChange={(e) => {
              setDocType(e.target.value);
              setPage(1);
            }}
            data-testid="filter-doc-type"
          >
            {DOC_TYPE_OPTIONS.map((v) => (
              <option key={v} value={v}>
                {v || "— любой —"}
              </option>
            ))}
          </select>
        </label>
        <label>
          status{" "}
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
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
            value={confidenceLevel}
            onChange={(e) => {
              setConfidenceLevel(e.target.value as "" | CardConfidenceLevel);
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
      </div>

      {query.isLoading && <p>Загрузка…</p>}
      {query.error && (
        <div className="banner banner-error">
          {query.error instanceof Error ? query.error.message : "Ошибка"}
        </div>
      )}

      {!query.isLoading && items.length === 0 && (
        <p className="text-muted">Карточек пока нет.</p>
      )}

      {items.length > 0 && (
        <>
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
                      data-testid={`preview-${c.doc_id}`}
                    >
                      Просмотр
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {pagination && pagination.total > pageSize && (
            <div
              className="btn-row"
              style={{ marginTop: 12, alignItems: "center" }}
            >
              <button
                className="btn btn-secondary"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                ← Назад
              </button>
              <span className="text-muted">
                Страница {pagination.page} из{" "}
                {Math.max(1, Math.ceil(pagination.total / pagination.page_size))}
              </span>
              <button
                className="btn btn-secondary"
                onClick={() => setPage((p) => p + 1)}
                disabled={
                  page >=
                  Math.ceil(pagination.total / pagination.page_size)
                }
              >
                Вперёд →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
