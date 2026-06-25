import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { getLLMStats } from "../../../api/llm_stats";
import { getSetupProgress, runPipeline } from "../../../api/setup";
import { ApiError } from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";
import { LLMProgressBar } from "../../observability/LLMProgressBar";

// Шаги pipeline которые активно используют LLM (rag-card generation +
// metadata validation). На этих этапах показываем частный LLM progress bar.
const LLM_STEPS = new Set([
  "rag_cards_generating",
  "metadata_validating",
  "embedding",
]);

export function RunPipelineStep(): JSX.Element {
  const { setupJobId, setStep } = useWizardStore();

  const progressQuery = useQuery({
    queryKey: ["progress", setupJobId],
    queryFn: () => {
      if (!setupJobId) throw new Error("no setup_job_id");
      return getSetupProgress(setupJobId);
    },
    enabled: !!setupJobId,
    refetchInterval: (q) => {
      const data = q.state.data;
      if (!data) return 500;
      const terminal = ["ready", "failed", "cancelled", "review_required"];
      // Уменьшено с 2000ms → 500ms чтобы UI показывал шаги pipeline
      // и LLM-вызовы в почти-реальном времени.
      return terminal.includes(data.status) ? false : 500;
    },
  });

  const runMutation = useMutation({
    mutationFn: () => {
      if (!setupJobId) throw new Error("no setup_job_id");
      return runPipeline(setupJobId);
    },
  });

  // Poll LLM stats и фиксируем "увеличился ли total_calls" — индикатор
  // живости pipeline на backend (если general progress_percent застрял).
  const llmStatsQuery = useQuery({
    queryKey: ["llmStatsForPipeline"],
    queryFn: getLLMStats,
    refetchInterval: 1000,
  });
  const totalCalls = llmStatsQuery.data?.total_calls ?? 0;
  const lastTotalCallsRef = useRef<number>(totalCalls);
  const [lastCallChangeAt, setLastCallChangeAt] = useState<number>(Date.now());
  useEffect(() => {
    if (totalCalls !== lastTotalCallsRef.current) {
      lastTotalCallsRef.current = totalCalls;
      setLastCallChangeAt(Date.now());
    }
  }, [totalCalls]);
  const secondsSinceLastCall = Math.floor((Date.now() - lastCallChangeAt) / 1000);

  const result = runMutation.data;
  const errorMessage =
    runMutation.error instanceof ApiError
      ? runMutation.error.message
      : runMutation.error?.message;

  return (
    <div>
      <h2>Шаг 5. Запустить pipeline</h2>
      <p className="text-muted">
        Pipeline проходит: parsing → sections_extracted → rag_cards_generating →
        metadata_validating → (review_required ИЛИ chunking → embedding →
        indexing).
      </p>

      <div className="btn-row">
        <button
          className="btn"
          onClick={() => runMutation.mutate()}
          disabled={runMutation.isPending}
          data-testid="submit-run"
        >
          {runMutation.isPending ? "Запускаем…" : "Запустить pipeline"}
        </button>
      </div>

      {errorMessage && (
        <div className="error-text" data-testid="run-error">
          {errorMessage}
        </div>
      )}

      {progressQuery.data && (
        <div style={{ marginTop: 24 }} data-testid="pipeline-progress">
          {/* Общий прогресс — все этапы pipeline. */}
          <div style={{ marginBottom: 4, fontSize: 13, fontWeight: 600 }}>
            Общий прогресс pipeline
          </div>
          <div className="progress-bar">
            <div style={{ width: `${progressQuery.data.progress_percent}%` }} />
          </div>
          <div className="text-muted" data-testid="progress-status">
            Статус: <strong>{progressQuery.data.status}</strong> ·{" "}
            {progressQuery.data.progress_percent.toFixed(0)}%
            {progressQuery.data.current_step && (
              <> · шаг: {progressQuery.data.current_step}</>
            )}
            · ошибок: {progressQuery.data.error_count}, предупреждений:{" "}
            {progressQuery.data.warning_count}
          </div>
          {/* Live activity indicator — total LLM calls растёт = pipeline жив,
              даже если progress_percent застрял на одной фазе. */}
          {(() => {
            const TERMINAL = ["ready", "failed", "cancelled", "review_required"];
            const running = !TERMINAL.includes(progressQuery.data.status);
            if (!running) return null;
            const alive = secondsSinceLastCall < 30;
            return (
              <div
                style={{
                  marginTop: 6,
                  fontSize: 12,
                  color: alive ? "#2e7d32" : "#c0392b",
                }}
                data-testid="llm-activity-indicator"
              >
                {alive ? "🟢" : "🔴"} LLM-вызовов всего: <strong>{totalCalls}</strong>
                {secondsSinceLastCall === 0
                  ? " · только что"
                  : ` · последний вызов ${secondsSinceLastCall}s назад`}
                {!alive && totalCalls > 0 && (
                  <> — возможно, pipeline застрял или ждёт ответ Ollama</>
                )}
              </div>
            );
          })()}

          {/* Частный прогресс — текущее обращение к LLM. Активен пока
              pipeline на LLM-нагруженных шагах и НЕ в terminal-статусе.
              Условие НЕ зависит от runMutation.isPending — пользователь
              может refreshнуть страницу пока pipeline ещё бежит на backend. */}
          {(() => {
            const TERMINAL = ["ready", "failed", "cancelled", "review_required"];
            const isRunning = !TERMINAL.includes(progressQuery.data.status);
            const step = progressQuery.data.current_step;
            const isLLMStep = step ? LLM_STEPS.has(step) : false;
            const active = isRunning && isLLMStep;
            return (
              <div style={{ marginTop: 12 }}>
                <div style={{ marginBottom: 4, fontSize: 13, fontWeight: 600 }}>
                  Прогресс текущего LLM-вызова{" "}
                  {active && (
                    <span style={{ color: "#666", fontWeight: 400 }}>
                      · шаг pipeline: <code>{step}</code>
                    </span>
                  )}
                </div>
                <LLMProgressBar
                  active={active}
                  model={step === "embedding" ? "nomic-embed-text" : "llama3.2"}
                  label={
                    step === "embedding"
                      ? "Embedding (nomic-embed-text)"
                      : `LLM вызов${step ? ` (${step})` : ""}`
                  }
                />
                {!active && isRunning && (
                  <div
                    className="text-muted"
                    style={{ fontSize: 12, marginTop: 4 }}
                  >
                    Pipeline на не-LLM шаге (
                    {step ?? "ожидание"}) — LLM не используется сейчас.
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 24 }}>
          <h3>Сводка pipeline</h3>
          <div className="kv-grid">
            <div className="key">Финальный статус</div>
            <div data-testid="result-final-status">{result.final_status}</div>
            <div className="key">Документы</div>
            <div>
              {result.documents_parsed}/{result.documents_total} распарсено,{" "}
              {result.documents_failed} с ошибкой
            </div>
            <div className="key">Секции</div>
            <div>{result.sections_extracted}</div>
            <div className="key">Сгенерировано карточек</div>
            <div>{result.cards_generated}</div>
            <div className="key">Требуют review</div>
            <div>{result.cards_review_required}</div>
            <div className="key">Auto-approved</div>
            <div>{result.cards_approved_auto}</div>
            <div className="key">Chunks</div>
            <div>
              {result.chunks_indexed}/{result.chunks_total} проиндексировано
            </div>
            {result.vector_index && (
              <>
                <div className="key">Vector index</div>
                <div>
                  {result.vector_index.index_version} ·{" "}
                  {result.vector_index.status}
                </div>
              </>
            )}
            {result.errors.length > 0 && (
              <>
                <div className="key">Ошибки</div>
                <div>
                  <ul style={{ margin: 0, paddingLeft: 16 }}>
                    {result.errors.map((e) => (
                      <li key={e}>{e}</li>
                    ))}
                  </ul>
                </div>
              </>
            )}
          </div>

          <div className="btn-row">
            {result.cards_review_required > 0 ? (
              <button
                className="btn"
                onClick={() => setStep("review")}
                data-testid="continue-to-review"
              >
                К проверке карточек →
              </button>
            ) : (
              <button
                className="btn"
                onClick={() => setStep("tests")}
                data-testid="continue-to-tests"
              >
                К retrieval-tests →
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
