/**
 * SourceDocumentDetailsDrawer (SETUP-03 / T-S03-025).
 *
 * Modal с 5 табами (lazy load per tab):
 *   Overview / Metadata / StatusHistory / ProcessingLog / Lineage
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  getLineage,
  getProcessingLog,
  getSourceDetails,
  getStatusHistory,
} from "../../api/sources";
import { MetadataEditor } from "./MetadataEditor";

type DrawerTab = "overview" | "metadata" | "history" | "log" | "lineage";

const TAB_LABELS: Record<DrawerTab, string> = {
  overview: "Обзор",
  metadata: "Metadata",
  history: "Статусы",
  log: "Лог",
  lineage: "Lineage",
};

interface SourceDocumentDetailsDrawerProps {
  setupJobId: string;
  sourceDocumentId: string;
  onClose: () => void;
}

export function SourceDocumentDetailsDrawer({
  setupJobId,
  sourceDocumentId,
  onClose,
}: SourceDocumentDetailsDrawerProps): JSX.Element {
  const [activeTab, setActiveTab] = useState<DrawerTab>("overview");

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="source-details-title"
      className="modal-backdrop"
      data-testid="source-details-drawer"
      onClick={onClose}
    >
      <div
        className="modal"
        style={{ maxWidth: 720, maxHeight: "90vh" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="source-details-title">Source Document</h3>
        <div
          role="tablist"
          className="row"
          style={{ gap: 4, marginBottom: 16, flexWrap: "wrap" }}
        >
          {(Object.keys(TAB_LABELS) as DrawerTab[]).map((tab) => (
            <button
              key={tab}
              role="tab"
              aria-selected={activeTab === tab}
              type="button"
              className={
                activeTab === tab ? "btn" : "btn btn-secondary"
              }
              onClick={() => setActiveTab(tab)}
              data-testid={`tab-${tab}`}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </div>

        <div data-testid={`tab-panel-${activeTab}`}>
          {activeTab === "overview" && (
            <OverviewTab
              setupJobId={setupJobId}
              sourceDocumentId={sourceDocumentId}
            />
          )}
          {activeTab === "metadata" && (
            <MetadataEditor
              setupJobId={setupJobId}
              sourceDocumentId={sourceDocumentId}
            />
          )}
          {activeTab === "history" && (
            <StatusHistoryTab
              setupJobId={setupJobId}
              sourceDocumentId={sourceDocumentId}
            />
          )}
          {activeTab === "log" && (
            <ProcessingLogTab
              setupJobId={setupJobId}
              sourceDocumentId={sourceDocumentId}
            />
          )}
          {activeTab === "lineage" && (
            <LineageTab
              setupJobId={setupJobId}
              sourceDocumentId={sourceDocumentId}
            />
          )}
        </div>

        <div className="btn-row" style={{ marginTop: 16 }}>
          <button
            type="button"
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

// ============================================================
// Overview
// ============================================================

function OverviewTab({
  setupJobId,
  sourceDocumentId,
}: {
  setupJobId: string;
  sourceDocumentId: string;
}): JSX.Element {
  const query = useQuery({
    queryKey: ["source-details", setupJobId, sourceDocumentId],
    queryFn: () => getSourceDetails(setupJobId, sourceDocumentId),
  });
  if (query.isLoading) return <p className="text-muted">Загружаем…</p>;
  if (query.error) return <p className="error-text">Ошибка загрузки</p>;
  const d = query.data;
  if (!d) return <p className="text-muted">Нет данных</p>;
  return (
    <dl className="kv-grid" data-testid="overview-content">
      <dt className="key">filename</dt>
      <dd>{d.filename}</dd>
      <dt className="key">status</dt>
      <dd>
        <code>{d.status}</code>
      </dd>
      <dt className="key">content_type</dt>
      <dd>{d.content_type}</dd>
      <dt className="key">size_bytes</dt>
      <dd>{d.size_bytes}</dd>
      <dt className="key">checksum</dt>
      <dd>
        <code>{d.checksum}</code>
      </dd>
      <dt className="key">uploaded_by</dt>
      <dd>{d.uploaded_by}</dd>
      <dt className="key">uploaded_at</dt>
      <dd>{d.uploaded_at}</dd>
      <dt className="key">parsed_sections</dt>
      <dd>{d.counters.parsed_sections_count}</dd>
      <dt className="key">rag_cards</dt>
      <dd>{d.counters.rag_cards_count}</dd>
      <dt className="key">chunks</dt>
      <dd>{d.counters.chunks_count}</dd>
      {d.error_message && (
        <>
          <dt className="key">error</dt>
          <dd className="error-text">{d.error_message}</dd>
        </>
      )}
    </dl>
  );
}

// ============================================================
// Status History
// ============================================================

function StatusHistoryTab({
  setupJobId,
  sourceDocumentId,
}: {
  setupJobId: string;
  sourceDocumentId: string;
}): JSX.Element {
  const query = useQuery({
    queryKey: ["source-history", setupJobId, sourceDocumentId],
    queryFn: () => getStatusHistory(setupJobId, sourceDocumentId, {}),
  });
  if (query.isLoading) return <p className="text-muted">Загружаем…</p>;
  if (query.error) return <p className="error-text">Ошибка загрузки</p>;
  const items = query.data?.items ?? [];
  if (items.length === 0)
    return (
      <p className="text-muted" data-testid="history-empty">
        История пуста.
      </p>
    );
  return (
    <ul data-testid="history-list">
      {items.map((entry) => (
        <li key={entry.status_history_id}>
          <strong>{entry.changed_at}</strong>:{" "}
          <code>{entry.old_status ?? "none"}</code> →{" "}
          <code>{entry.new_status}</code>
          <div className="text-muted">
            {entry.changed_by_type}:{entry.changed_by_id}
            {entry.reason && ` · ${entry.reason}`}
          </div>
        </li>
      ))}
    </ul>
  );
}

// ============================================================
// Processing Log
// ============================================================

function ProcessingLogTab({
  setupJobId,
  sourceDocumentId,
}: {
  setupJobId: string;
  sourceDocumentId: string;
}): JSX.Element {
  const query = useQuery({
    queryKey: ["source-log", setupJobId, sourceDocumentId],
    queryFn: () => getProcessingLog(setupJobId, sourceDocumentId, {}),
  });
  if (query.isLoading) return <p className="text-muted">Загружаем…</p>;
  if (query.error) return <p className="error-text">Ошибка загрузки</p>;
  const items = query.data?.items ?? [];
  if (items.length === 0)
    return (
      <p className="text-muted" data-testid="log-empty">
        Лог пуст.
      </p>
    );
  return (
    <ul data-testid="log-list">
      {items.map((entry) => (
        <li
          key={entry.processing_log_id}
          className={entry.level === "error" ? "error-text" : undefined}
        >
          <code>{entry.step}</code> · {entry.level} · {entry.created_at}
          <div>{entry.message}</div>
          {entry.error_code && (
            <div className="text-muted">code: {entry.error_code}</div>
          )}
        </li>
      ))}
    </ul>
  );
}

// ============================================================
// Lineage
// ============================================================

function LineageTab({
  setupJobId,
  sourceDocumentId,
}: {
  setupJobId: string;
  sourceDocumentId: string;
}): JSX.Element {
  const query = useQuery({
    queryKey: ["source-lineage", setupJobId, sourceDocumentId],
    queryFn: () => getLineage(setupJobId, sourceDocumentId, {}),
  });
  if (query.isLoading) return <p className="text-muted">Загружаем…</p>;
  if (query.error) return <p className="error-text">Ошибка загрузки</p>;
  const d = query.data;
  if (!d) return <p className="text-muted">Нет данных</p>;
  return (
    <div data-testid="lineage-content">
      <h4>Counters</h4>
      <ul>
        <li>parsed sections: {d.counters.parsed_sections_count}</li>
        <li>RAG cards: {d.counters.rag_cards_count}</li>
        <li>chunks: {d.counters.chunks_count}</li>
        <li>
          KB versions: {d.counters.knowledge_base_versions_count}
        </li>
      </ul>
      <h4>Relations ({d.relations.length})</h4>
      {d.relations.length === 0 ? (
        <p className="text-muted">Пока нет downstream artifacts.</p>
      ) : (
        <ul data-testid="lineage-list">
          {d.relations.map((r) => (
            <li key={r.lineage_id}>
              <code>{r.target_type}</code>:<strong>{r.target_id}</strong> (
              {r.relation_type}, by {r.created_by_service})
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
