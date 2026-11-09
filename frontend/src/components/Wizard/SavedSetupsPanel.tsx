// SETUP-01 UX: список сохранённых setup_jobs пользователя.
// Отображается на шаге 1 «Создать setup job» — пользователь может
// либо создать новый job, либо возобновить один из существующих
// (в том числе с прерванным парсингом — resume-логика сама доклассифицирует
// оставшиеся секции, см. parser/orchestrator.py).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  cancelSetupJob,
  listSetupJobs,
  type SetupJobListItem,
  type SetupJobListResponse,
} from "../../api/setup";
import { useWizardStore, type WizardStep } from "../../store/wizardStore";

const TERMINAL_STATUSES = new Set([
  "ready",
  "failed",
  "cancelled",
]);

function _stepFromStatus(status: string): WizardStep {
  // Best-effort: подхватить wizard-step, где юзер остановился.
  switch (status) {
    case "draft":
      return "upload";
    case "files_uploaded":
    case "parsing":
    case "sections_extracted":
      return "parse";
    case "rag_cards_generating":
      return "rag_card_generation";
    case "metadata_validating":
      return "validation";
    case "review_required":
      return "review";
    case "chunking":
    // "embedding"/"indexing" — статусы legacy-пайплайна (SETUP-01 /run,
    // убран из мастера); в гранулярном флоу индексация теперь часть
    // шага "chunking" (см. IndexingPanel).
    case "embedding":
    case "indexing":
      return "chunking";
    case "retrieval_testing":
      return "tests";
    case "publishing":
      return "publish";
    case "ready":
    case "failed":
      return "report";
    default:
      return "upload";
  }
}

function _statusColor(status: string): string {
  if (status === "ready") return "#2fbf71";
  if (status === "failed" || status === "cancelled") return "#e05555";
  if (status.endsWith("ing")) return "#4c9aff";
  return "#888";
}

export function SavedSetupsPanel(): JSX.Element {
  const setSetupJobId = useWizardStore((s) => s.setSetupJobId);
  const setParseJobId = useWizardStore((s) => s.setParseJobId);
  const setStep = useWizardStore((s) => s.setStep);
  const qc = useQueryClient();
  const [showAll, setShowAll] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const query = useQuery<SetupJobListResponse>({
    queryKey: ["listSetupJobs"],
    queryFn: listSetupJobs,
    staleTime: 5_000,
  });

  const cancelMut = useMutation({
    mutationFn: (setupJobId: string) => cancelSetupJob(setupJobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["listSetupJobs"] }),
  });

  const handleOpen = (job: SetupJobListItem) => {
    setSetupJobId(job.setup_job_id, job.project_name);
    // Передаём parse_job в wizardStore независимо от его статуса (в т.ч.
    // уже завершённый), чтобы ParsingStep мог показать сохранённые секции
    // вместо пустого экрана — до T-S04 fix здесь брался только
    // active_parse_job_id, который null для завершённого парсинга.
    setParseJobId(job.latest_parse_job_id ?? job.active_parse_job_id);

    // Выбор шага: приоритет — статус setup_job, но с учётом реального
    // parsing-состояния.
    // - active_parse_job (running/created/queued) → всегда parse.
    // - parse_job.status=completed + status = files_uploaded (не advanced
    //   исторически) → parse (пусть увидит завершённое состояние и продвинется дальше).
    // - иначе — по setup_job.status.
    let step: WizardStep;
    if (job.active_parse_job_id) {
      step = "parse";
    } else if (
      job.parse_job_status === "completed" &&
      job.status === "files_uploaded"
    ) {
      step = "parse";
    } else {
      step = _stepFromStatus(job.status);
    }
    setStep(step);
  };

  if (query.isLoading) {
    return <p className="text-muted">Загружаем сохранённые setup'ы…</p>;
  }
  if (query.error) {
    return (
      <div className="banner banner-warning" data-testid="saved-setups-error">
        Не удалось загрузить список сохранённых setup'ов:{" "}
        {query.error instanceof Error ? query.error.message : "unknown"}
      </div>
    );
  }
  if (!query.data || query.data.total === 0) {
    return (
      <p className="text-muted" data-testid="saved-setups-empty">
        Сохранённых setup'ов пока нет. Создайте первый ниже.
      </p>
    );
  }

  const items = query.data.items;
  const activeItems = items.filter((j) => !TERMINAL_STATUSES.has(j.status));
  const terminalItems = items.filter((j) => TERMINAL_STATUSES.has(j.status));
  const visible = showAll
    ? items
    : activeItems.length > 0
      ? activeItems
      : items.slice(0, 5);

  return (
    <div data-testid="saved-setups-panel" style={{ marginBottom: 24 }}>
      <h3>Сохранённые setup'ы ({query.data.total})</h3>
      <p className="text-muted" style={{ fontSize: 13 }}>
        Продолжите с прерванной сессии: нажмите «Открыть» — wizard восстановит
        state и перейдёт на нужный шаг. Парсинг умеет возобновляться
        по content_hash (уже классифицированные секции пропускаются).
      </p>
      <table className="table">
        <thead>
          <tr>
            <th>Проект</th>
            <th>Статус</th>
            <th>Документы</th>
            <th>Парсинг</th>
            <th>Секций сохранено</th>
            <th>Прогресс</th>
            <th>Started</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {visible.map((job) => (
            <tr key={job.setup_job_id} data-testid={`saved-setup-${job.setup_job_id}`}>
              <td>
                <strong>{job.project_name}</strong>
                <div style={{ fontSize: 11, color: "#888" }}>
                  <code>{job.setup_job_id.slice(0, 22)}</code>
                </div>
              </td>
              <td>
                <span
                  className="badge"
                  style={{
                    background: _statusColor(job.status),
                    color: "white",
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 11,
                  }}
                >
                  {job.status}
                </span>
              </td>
              <td>{job.source_documents_count}</td>
              <td>
                {job.parse_job_status ? (
                  <span
                    className="badge"
                    style={{
                      background:
                        job.parse_job_status === "completed"
                          ? "#2fbf71"
                          : job.parse_job_status === "running"
                            ? "#4c9aff"
                            : "#888",
                      color: "white",
                      padding: "2px 6px",
                      borderRadius: 4,
                      fontSize: 11,
                    }}
                  >
                    {job.parse_job_status}
                  </span>
                ) : (
                  <span className="text-muted" style={{ fontSize: 11 }}>—</span>
                )}
              </td>
              <td>
                {job.parsed_sections_count > 0 ? (
                  <strong style={{ color: "#2fbf71" }}>
                    {job.parsed_sections_count}
                  </strong>
                ) : (
                  <span className="text-muted">0</span>
                )}
              </td>
              <td>{Math.round(job.progress_percent)}%</td>
              <td style={{ fontSize: 12 }}>
                {job.started_at
                  ? new Date(job.started_at).toLocaleString("ru-RU", {
                      dateStyle: "short",
                      timeStyle: "short",
                    })
                  : "—"}
              </td>
              <td>
                <div style={{ display: "flex", gap: 4 }}>
                  <button
                    className="btn"
                    style={{ padding: "2px 12px", fontSize: 12 }}
                    onClick={() => handleOpen(job)}
                    data-testid={`open-${job.setup_job_id}`}
                  >
                    Открыть
                  </button>
                  {confirmDeleteId === job.setup_job_id ? (
                    <>
                      <button
                        className="btn"
                        style={{
                          padding: "2px 8px",
                          fontSize: 12,
                          background: "#e05555",
                          color: "white",
                        }}
                        onClick={() => {
                          cancelMut.mutate(job.setup_job_id);
                          setConfirmDeleteId(null);
                        }}
                      >
                        удалить?
                      </button>
                      <button
                        className="btn btn-secondary"
                        style={{ padding: "2px 8px", fontSize: 12 }}
                        onClick={() => setConfirmDeleteId(null)}
                      >
                        нет
                      </button>
                    </>
                  ) : (
                    <button
                      className="btn btn-secondary"
                      style={{ padding: "2px 8px", fontSize: 12 }}
                      onClick={() => setConfirmDeleteId(job.setup_job_id)}
                      title="Отменить job (soft-delete)"
                    >
                      ×
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {terminalItems.length > 0 && !showAll && activeItems.length > 0 && (
        <button
          type="button"
          className="btn btn-secondary"
          style={{ fontSize: 12, marginTop: 8 }}
          onClick={() => setShowAll(true)}
          data-testid="show-terminal"
        >
          Показать все, включая завершённые ({terminalItems.length})
        </button>
      )}
      {showAll && (
        <button
          type="button"
          className="btn btn-secondary"
          style={{ fontSize: 12, marginTop: 8 }}
          onClick={() => setShowAll(false)}
        >
          Скрыть завершённые
        </button>
      )}
    </div>
  );
}
