/**
 * SourceRegistryTab (SETUP-03 / T-S03-024).
 *
 * Orchestrator-компонент:
 * - useQuery → listSources (с фильтрами status + include_removed)
 * - useMutation → deleteSource / retrySource
 * - открывает SourceDocumentDetailsDrawer для details/PATCH/lineage
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  deleteSource,
  listSources,
  retrySource,
  type ListSourcesParams,
} from "../../api/sources";
import type { SourceDocumentStatus } from "../../api/types";
import { SourceDocumentDetailsDrawer } from "./SourceDocumentDetailsDrawer";
import { SourceDocumentTable } from "./SourceDocumentTable";

interface SourceRegistryTabProps {
  setupJobId: string;
}

const STATUS_FILTER_OPTIONS: { value: SourceDocumentStatus; label: string }[] = [
  { value: "registered", label: "registered" },
  { value: "parsing", label: "parsing" },
  { value: "parsed", label: "parsed" },
  { value: "rag_cards_generated", label: "rag_cards_generated" },
  { value: "review_required", label: "review_required" },
  { value: "published", label: "published" },
  { value: "parse_failed", label: "parse_failed" },
  { value: "processing_failed", label: "processing_failed" },
];

export function SourceRegistryTab({
  setupJobId,
}: SourceRegistryTabProps): JSX.Element {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<SourceDocumentStatus | "">("");
  const [includeRemoved, setIncludeRemoved] = useState(false);
  const [detailsId, setDetailsId] = useState<string | null>(null);

  const params: ListSourcesParams = {
    status: statusFilter ? [statusFilter] : undefined,
    include_removed: includeRemoved,
  };

  const sourcesQuery = useQuery({
    queryKey: ["sources", setupJobId, statusFilter, includeRemoved],
    queryFn: () => listSources(setupJobId, params),
  });

  const deleteMutation = useMutation({
    mutationFn: (doc_id: string) => deleteSource(setupJobId, doc_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources", setupJobId] }),
  });

  const retryMutation = useMutation({
    mutationFn: (doc_id: string) => retrySource(setupJobId, doc_id, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources", setupJobId] }),
  });

  return (
    <div data-testid="source-registry-tab">
      <h2>Source Registry</h2>
      <p className="text-muted">
        Реестр загруженных источников: статусы, processing log, lineage.
      </p>

      <div className="row" style={{ marginBottom: 12, gap: 16 }}>
        <label>
          Статус:{" "}
          <select
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(e.target.value as SourceDocumentStatus | "")
            }
            data-testid="source-status-filter"
          >
            <option value="">Все</option>
            {STATUS_FILTER_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={includeRemoved}
            onChange={(e) => setIncludeRemoved(e.target.checked)}
            data-testid="include-removed-toggle"
          />{" "}
          показать удалённые
        </label>
        <span className="text-muted">
          Всего: {sourcesQuery.data?.pagination.total ?? 0}
        </span>
      </div>

      {(deleteMutation.error || retryMutation.error) && (
        <div className="error-text" data-testid="action-error">
          {String(
            (deleteMutation.error as Error | undefined)?.message ??
              (retryMutation.error as Error | undefined)?.message ??
              "",
          )}
        </div>
      )}

      <SourceDocumentTable
        items={sourcesQuery.data?.items ?? []}
        loading={sourcesQuery.isLoading}
        onDetails={(id) => setDetailsId(id)}
        onDelete={(id) => deleteMutation.mutate(id)}
        onRetry={(id) => retryMutation.mutate(id)}
      />

      {detailsId && (
        <SourceDocumentDetailsDrawer
          setupJobId={setupJobId}
          sourceDocumentId={detailsId}
          onClose={() => setDetailsId(null)}
        />
      )}
    </div>
  );
}
