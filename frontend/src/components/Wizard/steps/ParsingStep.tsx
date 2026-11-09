import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  cancelParseJob,
  createParseJob,
  getParseJobReport,
  getParseJobStatus,
  listParsedSections,
  retryParseDocument,
  runParseJob,
} from "../../../api/parse";
import type {
  ParseJobStatus as PJStatus,
  ParseJobResponse,
} from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";
import { SectionDetailDrawer } from "../sections/SectionDetailDrawer";
import { ClassifierResultBadge } from "../../Classifier/ClassifierResultBadge";

const TERMINAL: PJStatus[] = ["completed", "partial_success", "failed", "cancelled"];

function statusBadge(status: PJStatus): { label: string; cls: string } {
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

export function ParsingStep(): JSX.Element {
  const { setupJobId, parseJobId, setParseJobId, setStep } = useWizardStore();
  const qc = useQueryClient();
  const [lastError, setLastError] = useState<string | null>(null);
  const [detailSectionId, setDetailSectionId] = useState<string | null>(null);
  const [sectionsPage, setSectionsPage] = useState<number>(1);
  const [sectionsPageSize, setSectionsPageSize] = useState<number>(100);

  const statusQuery = useQuery({
    queryKey: ["parseJobStatus", setupJobId, parseJobId],
    queryFn: () => {
      if (!setupJobId || !parseJobId) throw new Error("no parse_job_id");
      return getParseJobStatus(setupJobId, parseJobId);
    },
    enabled: !!setupJobId && !!parseJobId,
    refetchInterval: (q) => {
      const data = q.state.data as ParseJobResponse | undefined;
      if (!data) return 500;
      // Быстрый poll (500ms) в любых non-terminal состояниях.
      // Backend orchestrator обновляет processed_documents/total_sections
      // incrementally per-doc (см. parser/orchestrator.py step 245).
      if (TERMINAL.includes(data.status)) return false;
      return 500;
    },
    // staleTime=0 гарантирует что refetchInterval polling всегда
    // возвращает свежие данные, не подставляет stale-cache.
    staleTime: 0,
  });

  const reportQuery = useQuery({
    queryKey: ["parseJobReport", setupJobId, parseJobId],
    queryFn: () => {
      if (!setupJobId || !parseJobId) throw new Error("no parse_job_id");
      return getParseJobReport(setupJobId, parseJobId);
    },
    enabled:
      !!setupJobId &&
      !!parseJobId &&
      TERMINAL.includes(statusQuery.data?.status ?? "created"),
  });

  const sectionsQuery = useQuery({
    queryKey: [
      "parsedSections",
      setupJobId,
      parseJobId,
      sectionsPage,
      sectionsPageSize,
    ],
    queryFn: () => {
      if (!setupJobId || !parseJobId) throw new Error("no parse_job_id");
      return listParsedSections(setupJobId, parseJobId, {
        page: sectionsPage,
        pageSize: sectionsPageSize,
      });
    },
    enabled:
      !!setupJobId &&
      !!parseJobId &&
      TERMINAL.includes(statusQuery.data?.status ?? "created"),
    placeholderData: (prev) => prev,
  });

  const createMut = useMutation({
    mutationFn: () => {
      if (!setupJobId) throw new Error("no setup_job_id");
      return createParseJob(setupJobId);
    },
    onSuccess: (job) => {
      setParseJobId(job.parse_job_id);
      setLastError(null);
    },
    onError: (err: Error) => setLastError(err.message),
  });

  const runMut = useMutation({
    mutationFn: () => {
      if (!setupJobId || !parseJobId) throw new Error("no parse_job_id");
      return runParseJob(setupJobId, parseJobId);
    },
    onMutate: () => {
      // SETUP-04 UX: сразу инвалидируем статус, чтобы progress-bar
      // начал polling с первого cycle'а, а не ждал первый natural refetch.
      qc.invalidateQueries({
        queryKey: ["parseJobStatus", setupJobId, parseJobId],
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["parseJobStatus", setupJobId, parseJobId] });
      qc.invalidateQueries({ queryKey: ["parseJobReport", setupJobId, parseJobId] });
      qc.invalidateQueries({ queryKey: ["parsedSections", setupJobId, parseJobId] });
      setLastError(null);
    },
    onError: (err: Error) => setLastError(err.message),
  });

  const cancelMut = useMutation({
    mutationFn: () => {
      if (!setupJobId || !parseJobId) throw new Error("no parse_job_id");
      return cancelParseJob(setupJobId, parseJobId);
    },
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["parseJobStatus", setupJobId, parseJobId] }),
    onError: (err: Error) => setLastError(err.message),
  });

  const retryMut = useMutation({
    mutationFn: (sourceDocumentId: string) => {
      if (!setupJobId || !parseJobId) throw new Error("no parse_job_id");
      return retryParseDocument(setupJobId, parseJobId, sourceDocumentId);
    },
    onSuccess: (resp) => {
      if (resp.new_parse_job_id) setParseJobId(resp.new_parse_job_id);
      qc.invalidateQueries({ queryKey: ["parseJobStatus"] });
    },
    onError: (err: Error) => setLastError(err.message),
  });

  const status = statusQuery.data?.status;
  const isTerminal = status ? TERMINAL.includes(status) : false;
  const canCancel = status === "created" || status === "queued" || status === "running";

  return (
    <div>
      <h2>Шаг 3. Парсинг документов</h2>
      <p className="text-muted">
        Извлекаем секции из загруженных документов (Markdown, Text, CSV, JSON, PDF, DOCX, XLSX).
        По умолчанию каждая секция классифицируется простыми правилами по
        типам (task / schema / analytics / glossary / validation_rule /
        question_template). Если backend запущен с{" "}
        <code>FE_BOT_TAXONOMY_MODE=llm</code>, вместо этого используется
        многоуровневая классификация по дереву из «Библиотеки
        классификаторов» — колонка «taxonomy» ниже покажет путь по дереву
        для каждой секции.
      </p>

      <div className="btn-row">
        <button
          className="btn"
          onClick={() => createMut.mutate()}
          disabled={!setupJobId || createMut.isPending || !!parseJobId}
          data-testid="create-parse-job"
        >
          {createMut.isPending ? "Создаём…" : "1) Создать ParseJob"}
        </button>
        <button
          className="btn"
          onClick={() => runMut.mutate()}
          disabled={!parseJobId || runMut.isPending || isTerminal}
          data-testid="run-parse-job"
        >
          {runMut.isPending ? "Парсим…" : "2) Запустить парсинг"}
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => cancelMut.mutate()}
          disabled={!parseJobId || !canCancel || cancelMut.isPending}
          data-testid="cancel-parse-job"
        >
          Отменить
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => setStep("rag_card_generation")}
          disabled={!isTerminal || status === "failed"}
          data-testid="continue-to-rag-card-generation"
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
        <div style={{ marginTop: 20 }} data-testid="parse-job-status">
          <h3>ParseJob {statusQuery.data.parse_job_id}</h3>
          {(() => {
            const b = statusBadge(statusQuery.data.status);
            return <div className={`banner ${b.cls}`}>{b.label}</div>;
          })()}
          {(() => {
            const totalDocs = statusQuery.data.total_documents;
            const processedDocs =
              statusQuery.data.processed_documents +
              statusQuery.data.failed_documents;
            const totalSecs = statusQuery.data.total_sections;
            const running = statusQuery.data.status === "running";

            const docPercent =
              totalDocs > 0
                ? Math.min(100, Math.round((processedDocs / totalDocs) * 100))
                : 0;
            // Soft per-section прогресс: если doc всё ещё крутится, но
            // секции добавляются — показываем это отдельным индикатором
            // с эвристикой ~15% за секцию (визуальная динамика вместо
            // застывшего 0%). Для PDF с 20 секциями это даёт плавный рост.
            const sectionSoftPercent = Math.min(
              95,
              Math.max(docPercent, totalSecs * 15),
            );
            const displayPercent = running ? sectionSoftPercent : docPercent;

            return (
              <div
                style={{ marginTop: 12 }}
                data-testid="parse-progress-bar"
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 12,
                    marginBottom: 4,
                  }}
                >
                  <span>
                    Документы: {processedDocs}/{totalDocs}
                    {totalSecs > 0 && (
                      <>
                        {" · "}
                        <strong data-testid="live-section-count">
                          секций обработано: {totalSecs}
                        </strong>
                      </>
                    )}
                    {running && (
                      <span
                        style={{ marginLeft: 8, color: "#666" }}
                        data-testid="live-pulse"
                      >
                        ▶ идёт классификация…
                      </span>
                    )}
                  </span>
                  <span data-testid="parse-progress-percent">
                    {displayPercent}%
                  </span>
                </div>
                <div
                  style={{
                    background: "#eef",
                    borderRadius: 6,
                    height: 12,
                    overflow: "hidden",
                    border: "1px solid #ccd",
                  }}
                >
                  <div
                    style={{
                      background: running
                        ? "repeating-linear-gradient(45deg, #4c9aff, #4c9aff 8px, #6faaff 8px, #6faaff 16px)"
                        : displayPercent === 100
                          ? "#2fbf71"
                          : "#4c9aff",
                      width: `${displayPercent}%`,
                      height: "100%",
                      transition: "width 400ms ease",
                    }}
                    data-testid="parse-progress-fill"
                  />
                </div>
              </div>
            );
          })()}
          <table className="table" style={{ marginTop: 12 }}>
            <tbody>
              <tr>
                <td>Всего документов</td>
                <td>{statusQuery.data.total_documents}</td>
              </tr>
              <tr>
                <td>Обработано</td>
                <td>{statusQuery.data.processed_documents}</td>
              </tr>
              <tr>
                <td>Ошибок</td>
                <td>{statusQuery.data.failed_documents}</td>
              </tr>
              <tr>
                <td>Извлечено секций</td>
                <td>{statusQuery.data.total_sections}</td>
              </tr>
              <tr>
                <td>Low-confidence</td>
                <td>{statusQuery.data.low_confidence_sections}</td>
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

      {reportQuery.data && reportQuery.data.documents.length > 0 && (
        <div style={{ marginTop: 24 }} data-testid="parse-report">
          <h3>Отчёт по документам ({reportQuery.data.documents.length})</h3>
          <table className="table">
            <thead>
              <tr>
                <th>source_document_id</th>
                <th>status</th>
                <th>strategy</th>
                <th>sections</th>
                <th>low_conf</th>
                <th>errors</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {reportQuery.data.documents.map((d) => (
                <tr key={d.source_document_id}>
                  <td>
                    <code>{d.source_document_id.slice(0, 18)}…</code>
                  </td>
                  <td>{d.status}</td>
                  <td>{d.parser_strategy ?? "—"}</td>
                  <td>{d.sections_count}</td>
                  <td>{d.low_confidence_sections}</td>
                  <td>{d.errors.length}</td>
                  <td>
                    {d.status === "failed" && parseJobId && (
                      <button
                        className="btn btn-secondary"
                        onClick={() => retryMut.mutate(d.source_document_id)}
                        disabled={retryMut.isPending}
                      >
                        Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {sectionsQuery.data && sectionsQuery.data.items.length > 0 && (
        <div style={{ marginTop: 24 }} data-testid="parsed-sections">
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 8,
            }}
          >
            <h3 style={{ margin: 0 }}>
              Извлечённые секции ({sectionsQuery.data.pagination.total})
            </h3>
            <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12 }}>
              <label>
                На странице:{" "}
                <select
                  value={sectionsPageSize}
                  onChange={(e) => {
                    setSectionsPageSize(Number(e.target.value));
                    setSectionsPage(1);
                  }}
                  data-testid="sections-page-size"
                >
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                  <option value={200}>200</option>
                </select>
              </label>
            </div>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>title</th>
                <th>taxonomy</th>
                <th>status</th>
                <th>confidence</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sectionsQuery.data.items.map((s) => {
                const classifiedByTree = s.classifier_result != null;
                return (
                  <tr
                    key={s.section_id}
                    data-testid={
                      classifiedByTree ? `section-row-llm-${s.section_id}` : undefined
                    }
                    style={
                      classifiedByTree
                        ? {
                            background: "#f3faf0",
                            borderLeft: "3px solid #2fbf71",
                          }
                        : undefined
                    }
                  >
                    <td>
                      {classifiedByTree && (
                        <span
                          title="Классифицировано деревом классификаторов (LLM)"
                          style={{ marginRight: 6 }}
                          aria-hidden="true"
                        >
                          🌳
                        </span>
                      )}
                      {s.title}
                    </td>
                    <td>
                      <ClassifierResultBadge result={s.classifier_result} />
                    </td>
                    <td>{s.section_status}</td>
                    <td>
                      {s.confidence !== null ? s.confidence.toFixed(2) : "—"}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: "2px 10px", fontSize: 12 }}
                        onClick={() => setDetailSectionId(s.section_id)}
                        data-testid={`section-detail-${s.section_id}`}
                      >
                        Подробно
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {(() => {
            const pag = sectionsQuery.data.pagination;
            const totalPages = Math.max(
              1,
              Math.ceil(pag.total / pag.page_size),
            );
            if (totalPages <= 1) return null;
            const goto = (p: number) =>
              setSectionsPage(Math.min(totalPages, Math.max(1, p)));
            return (
              <div
                className="btn-row"
                style={{
                  marginTop: 12,
                  alignItems: "center",
                  fontSize: 13,
                  gap: 8,
                }}
                data-testid="sections-pagination"
              >
                <button
                  className="btn btn-secondary"
                  onClick={() => goto(1)}
                  disabled={pag.page <= 1}
                >
                  «
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => goto(pag.page - 1)}
                  disabled={pag.page <= 1}
                >
                  ←
                </button>
                <span className="text-muted">
                  Страница{" "}
                  <input
                    type="number"
                    value={pag.page}
                    min={1}
                    max={totalPages}
                    style={{ width: 60, textAlign: "center" }}
                    onChange={(e) => goto(Number(e.target.value))}
                    data-testid="sections-page-input"
                  />{" "}
                  из <strong>{totalPages}</strong> · показано{" "}
                  {sectionsQuery.data.items.length} из {pag.total}
                </span>
                <button
                  className="btn btn-secondary"
                  onClick={() => goto(pag.page + 1)}
                  disabled={pag.page >= totalPages}
                >
                  →
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => goto(totalPages)}
                  disabled={pag.page >= totalPages}
                >
                  »
                </button>
              </div>
            );
          })()}
        </div>
      )}

      {detailSectionId && setupJobId && parseJobId && (
        <SectionDetailDrawer
          setupJobId={setupJobId}
          parseJobId={parseJobId}
          sectionId={detailSectionId}
          onClose={() => setDetailSectionId(null)}
        />
      )}
    </div>
  );
}
