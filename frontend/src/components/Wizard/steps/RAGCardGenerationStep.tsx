import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  cancelRAGCardGenerationJob,
  createRAGCardGenerationJob,
  getRAGCardGenerationJob,
  getRAGCardGenerationReport,
  runRAGCardGenerationJob,
} from "../../../api/rag_cards";
import type {
  RAGCardGenerationJobResponse,
  RAGCardGenerationJobStatus,
} from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";
import { LowConfidenceCardsPanel } from "../rag/LowConfidenceCardsPanel";
import { RAGCardList } from "../rag/RAGCardList";
import { RAGCardPreviewDrawer } from "../rag/RAGCardPreviewDrawer";

const TERMINAL: RAGCardGenerationJobStatus[] = [
  "completed",
  "partial_success",
  "failed",
  "cancelled",
];

function statusBadge(status: RAGCardGenerationJobStatus): {
  label: string;
  cls: string;
} {
  switch (status) {
    case "completed":
      return { label: "✓ completed", cls: "banner-success" };
    case "partial_success":
      return { label: "⚠ partial_success", cls: "banner-warning" };
    case "failed":
      return { label: "✗ failed", cls: "banner-error" };
    case "cancelled":
      return { label: "cancelled", cls: "banner-warning" };
    case "running":
      return { label: "▶ running…", cls: "banner-info" };
    default:
      return { label: status, cls: "banner-info" };
  }
}

export function RAGCardGenerationStep(): JSX.Element {
  const {
    setupJobId,
    ragCardGenerationJobId,
    setRagCardGenerationJobId,
    setStep,
  } = useWizardStore();
  const qc = useQueryClient();
  const [lastError, setLastError] = useState<string | null>(null);
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);

  const statusQuery = useQuery({
    queryKey: ["ragCardJob", setupJobId, ragCardGenerationJobId],
    queryFn: () => {
      if (!setupJobId || !ragCardGenerationJobId)
        throw new Error("no generation_job_id");
      return getRAGCardGenerationJob(setupJobId, ragCardGenerationJobId);
    },
    enabled: !!setupJobId && !!ragCardGenerationJobId,
    refetchInterval: (q) => {
      const data = q.state.data as RAGCardGenerationJobResponse | undefined;
      if (!data) return 2000;
      return TERMINAL.includes(data.status) ? false : 2000;
    },
  });

  const reportQuery = useQuery({
    queryKey: ["ragCardReport", setupJobId, ragCardGenerationJobId],
    queryFn: () => {
      if (!setupJobId || !ragCardGenerationJobId)
        throw new Error("no generation_job_id");
      return getRAGCardGenerationReport(setupJobId, ragCardGenerationJobId);
    },
    enabled:
      !!setupJobId &&
      !!ragCardGenerationJobId &&
      TERMINAL.includes(statusQuery.data?.status ?? "created"),
  });

  const createMut = useMutation({
    mutationFn: () => {
      if (!setupJobId) throw new Error("no setup_job_id");
      return createRAGCardGenerationJob(setupJobId, {});
    },
    onSuccess: (job) => {
      setRagCardGenerationJobId(job.generation_job_id);
      setLastError(null);
    },
    onError: (err: Error) => setLastError(err.message),
  });

  const runMut = useMutation({
    mutationFn: () => {
      if (!setupJobId || !ragCardGenerationJobId)
        throw new Error("no generation_job_id");
      return runRAGCardGenerationJob(setupJobId, ragCardGenerationJobId);
    },
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ["ragCardJob", setupJobId, ragCardGenerationJobId],
      });
      qc.invalidateQueries({
        queryKey: ["ragCardReport", setupJobId, ragCardGenerationJobId],
      });
      qc.invalidateQueries({ queryKey: ["ragCardList", setupJobId] });
      setLastError(null);
    },
    onError: (err: Error) => setLastError(err.message),
  });

  const cancelMut = useMutation({
    mutationFn: () => {
      if (!setupJobId || !ragCardGenerationJobId)
        throw new Error("no generation_job_id");
      return cancelRAGCardGenerationJob(setupJobId, ragCardGenerationJobId);
    },
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ["ragCardJob", setupJobId, ragCardGenerationJobId],
      }),
    onError: (err: Error) => setLastError(err.message),
  });

  const status = statusQuery.data?.status;
  const isTerminal = status ? TERMINAL.includes(status) : false;
  const canCancel =
    status === "created" || status === "queued" || status === "running";

  if (!setupJobId) {
    return (
      <div>
        <h2>Шаг 4. Генерация RAG-карточек</h2>
        <div className="banner banner-warning">
          Сначала создайте setup_job на шаге 1.
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2>Шаг 4. Генерация RAG-карточек</h2>
      <p className="text-muted">
        Для каждой извлечённой секции LLM (или детерминированный fallback) формирует
        RAG-карточку с metadata (front matter) и Markdown-телом. Низкоуверенные
        карточки помечаются review_required.
      </p>

      <div className="btn-row">
        <button
          className="btn"
          onClick={() => createMut.mutate()}
          disabled={
            !setupJobId || createMut.isPending || !!ragCardGenerationJobId
          }
          data-testid="create-rag-card-job"
        >
          {createMut.isPending ? "Создаём…" : "1) Создать GenerationJob"}
        </button>
        <button
          className="btn"
          onClick={() => runMut.mutate()}
          disabled={!ragCardGenerationJobId || runMut.isPending || isTerminal}
          data-testid="run-rag-card-job"
        >
          {runMut.isPending ? "Генерируем…" : "2) Запустить генерацию"}
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => cancelMut.mutate()}
          disabled={
            !ragCardGenerationJobId || !canCancel || cancelMut.isPending
          }
          data-testid="cancel-rag-card-job"
        >
          Отменить
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => setStep("run")}
          disabled={!isTerminal || status === "failed"}
          data-testid="continue-to-run"
        >
          Далее →
        </button>
      </div>

      {lastError && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {lastError}
        </div>
      )}

      {statusQuery.data && (
        <div style={{ marginTop: 20 }} data-testid="rag-card-job-status">
          <h3>GenerationJob {statusQuery.data.generation_job_id}</h3>
          {(() => {
            const b = statusBadge(statusQuery.data.status);
            return <div className={`banner ${b.cls}`}>{b.label}</div>;
          })()}
          <table className="table" style={{ marginTop: 12 }}>
            <tbody>
              <tr>
                <td>Всего секций</td>
                <td>{statusQuery.data.total_sections}</td>
              </tr>
              <tr>
                <td>Обработано</td>
                <td>{statusQuery.data.processed_sections}</td>
              </tr>
              <tr>
                <td>Сгенерировано карточек</td>
                <td>{statusQuery.data.generated_cards}</td>
              </tr>
              <tr>
                <td>Ошибок секций</td>
                <td>{statusQuery.data.failed_sections}</td>
              </tr>
              <tr>
                <td>Review required</td>
                <td>{statusQuery.data.review_required_cards}</td>
              </tr>
              {statusQuery.data.error_code && (
                <tr>
                  <td>Error code</td>
                  <td>
                    <code>{statusQuery.data.error_code}</code>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {reportQuery.data && (
        <div style={{ marginTop: 24 }} data-testid="rag-card-report">
          <h3>Отчёт</h3>
          <p className="text-muted">
            Сгенерировано: {reportQuery.data.summary.generated_cards} ·
            ошибок: {reportQuery.data.errors.length} · предупреждений:{" "}
            {reportQuery.data.warnings.length}
          </p>
        </div>
      )}

      <LowConfidenceCardsPanel
        setupJobId={setupJobId}
        onSelect={(docId) => setPreviewDocId(docId)}
      />

      <RAGCardList
        setupJobId={setupJobId}
        onSelect={(docId) => setPreviewDocId(docId)}
      />

      {previewDocId && (
        <RAGCardPreviewDrawer
          setupJobId={setupJobId}
          docId={previewDocId}
          onClose={() => setPreviewDocId(null)}
        />
      )}
    </div>
  );
}
