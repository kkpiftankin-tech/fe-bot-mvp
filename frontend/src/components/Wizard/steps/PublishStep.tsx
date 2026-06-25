import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { publishKB } from "../../../api/setup";
import { ApiError } from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";

export function PublishStep(): JSX.Element {
  const { setupJobId, setStep, evalReport } = useWizardStore();
  const [comment, setComment] = useState("");

  const mutation = useMutation({
    mutationFn: () => {
      if (!setupJobId) throw new Error("no setup_job_id");
      return publishKB(setupJobId, {
        eval_report: evalReport,
        comment: comment || undefined,
      });
    },
  });

  const errorMessage =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error?.message;

  const result = mutation.data;

  return (
    <div>
      <h2>Шаг 10. Публикация Knowledge Base</h2>
      <p className="text-muted">
        Создаёт новую <code>KnowledgeBaseVersion</code> и активирует её. Предыдущая
        ACTIVE KB автоматически деpresetтется.
        <br />
        Требуется роль <code>admin</code> или <code>rag_admin</code> (permission
        <code>kb.publish</code>).
      </p>

      {!evalReport && (
        <div className="banner banner-warning" data-testid="no-eval-warning">
          Eval-отчёт отсутствует. Публикация пройдёт без gate-проверки. Рекомендуем
          сначала пройти retrieval-tests.
        </div>
      )}

      {evalReport && (
        <div
          className={
            evalReport.passed ? "banner banner-success" : "banner banner-error"
          }
        >
          Eval: {evalReport.passed ? "passed" : "FAILED"} · recall@
          {evalReport.top_k}={evalReport.mean_recall_at_k.toFixed(3)}
        </div>
      )}

      <div className="form-group">
        <label htmlFor="comment">Комментарий (опционально)</label>
        <input
          id="comment"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          data-testid="publish-comment"
        />
      </div>

      <div className="btn-row">
        <button
          className="btn"
          disabled={mutation.isPending || evalReport?.passed === false}
          onClick={() => mutation.mutate()}
          data-testid="submit-publish"
        >
          {mutation.isPending ? "Публикуем…" : "Опубликовать KB"}
        </button>
      </div>

      {errorMessage && (
        <div className="error-text" data-testid="publish-error">
          {errorMessage}
        </div>
      )}

      {result && (
        <div className="banner banner-success" style={{ marginTop: 16 }}>
          KB <strong>{result.knowledge_base_version}</strong> активирована.
          <div className="kv-grid" style={{ marginTop: 8 }}>
            <div className="key">Status</div>
            <div data-testid="published-status">{result.status}</div>
            <div className="key">is_active</div>
            <div>{String(result.is_active)}</div>
            <div className="key">Published by</div>
            <div>{result.published_by ?? "—"}</div>
            <div className="key">Published at</div>
            <div>{result.published_at ?? "—"}</div>
            <div className="key">index_version</div>
            <div>{result.index_version ?? "—"}</div>
            <div className="key">Карточек</div>
            <div>{result.rag_card_count}</div>
            <div className="key">Chunks</div>
            <div>{result.chunk_count}</div>
          </div>
          <div className="btn-row">
            <button
              className="btn"
              onClick={() => setStep("report")}
              data-testid="continue-to-report"
            >
              К итоговому отчёту →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
