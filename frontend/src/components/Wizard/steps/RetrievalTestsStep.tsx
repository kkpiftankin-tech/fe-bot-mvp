import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { runRetrievalTests } from "../../../api/setup";
import { ApiError, type GoldenQueryDTO } from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";

interface QueryEditorRow {
  id: string;
  query: string;
  expected: string; // запятые → split
}

let nextId = 1;
const newRow = (): QueryEditorRow => ({
  id: `gq_${nextId++}`,
  query: "",
  expected: "",
});

export function RetrievalTestsStep(): JSX.Element {
  const { setupJobId, setStep, setEvalReport } = useWizardStore();
  const [rows, setRows] = useState<QueryEditorRow[]>([newRow()]);
  const [topK, setTopK] = useState(5);
  const [threshold, setThreshold] = useState<string>("");

  const mutation = useMutation({
    mutationFn: () => {
      if (!setupJobId) throw new Error("no setup_job_id");
      const golden: GoldenQueryDTO[] = rows
        .filter((r) => r.query.trim() && r.expected.trim())
        .map((r) => ({
          query: r.query.trim(),
          expected_doc_ids: r.expected
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        }));
      const thresholdNum = threshold ? Number.parseFloat(threshold) : undefined;
      return runRetrievalTests(setupJobId, {
        golden_queries: golden,
        top_k: topK,
        threshold_recall_at_5: thresholdNum,
      });
    },
    onSuccess: (report) => setEvalReport(report),
  });

  const errorMessage =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error?.message;

  const validRows = rows.filter((r) => r.query.trim() && r.expected.trim());
  const report = mutation.data;

  return (
    <div>
      <h2>Шаг 5. Retrieval-tests</h2>
      <p className="text-muted">
        Опишите golden-set из (query, expected_doc_ids), чтобы измерить качество
        retrieval перед публикацией. Gate по умолчанию — recall@5 ≥ 0.85.
      </p>

      <div className="row">
        <label>
          top_k:{" "}
          <input
            type="number"
            min={1}
            max={50}
            value={topK}
            onChange={(e) => setTopK(Number.parseInt(e.target.value || "5", 10))}
            style={{ width: 80 }}
            data-testid="top-k"
          />
        </label>
        <label>
          threshold recall@5:{" "}
          <input
            type="text"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            placeholder="по умолчанию 0.85"
            style={{ width: 140 }}
            data-testid="threshold"
          />
        </label>
      </div>

      <h3 style={{ marginTop: 16 }}>Golden queries</h3>
      {rows.map((row, idx) => (
        <div key={row.id} className="row" style={{ marginBottom: 8 }}>
          <input
            placeholder="Запрос (на естественном языке)"
            value={row.query}
            onChange={(e) =>
              setRows(
                rows.map((r) =>
                  r.id === row.id ? { ...r, query: e.target.value } : r,
                ),
              )
            }
            style={{ flex: 1 }}
            data-testid={`query-${idx}`}
          />
          <input
            placeholder="Expected doc_id-ы через запятую"
            value={row.expected}
            onChange={(e) =>
              setRows(
                rows.map((r) =>
                  r.id === row.id ? { ...r, expected: e.target.value } : r,
                ),
              )
            }
            style={{ flex: 1 }}
            data-testid={`expected-${idx}`}
          />
          {rows.length > 1 && (
            <button
              className="btn btn-secondary"
              onClick={() => setRows(rows.filter((r) => r.id !== row.id))}
            >
              −
            </button>
          )}
        </div>
      ))}
      <button
        className="btn btn-secondary"
        onClick={() => setRows([...rows, newRow()])}
        data-testid="add-row"
      >
        + строка
      </button>

      <div className="btn-row">
        <button
          className="btn"
          onClick={() => mutation.mutate()}
          disabled={validRows.length === 0 || mutation.isPending}
          data-testid="submit-eval"
        >
          {mutation.isPending ? "Запускаем eval…" : "Запустить eval"}
        </button>
      </div>

      {errorMessage && (
        <div className="error-text" data-testid="eval-error">
          {errorMessage}
        </div>
      )}

      {report && (
        <div style={{ marginTop: 24 }}>
          <h3>Отчёт eval</h3>
          <div
            className={
              report.passed ? "banner banner-success" : "banner banner-error"
            }
            data-testid="eval-banner"
          >
            Gate: {report.passed ? "PASSED" : "FAILED"} · recall@{report.top_k}={" "}
            {report.mean_recall_at_k.toFixed(3)} (threshold{" "}
            {report.threshold_recall_at_5.toFixed(2)})
          </div>
          <div className="kv-grid">
            <div className="key">Запросов</div>
            <div>{report.queries_total}</div>
            <div className="key">Ошибок</div>
            <div>{report.queries_errored}</div>
            <div className="key">mean precision@k</div>
            <div>{report.mean_precision_at_k.toFixed(3)}</div>
            <div className="key">MRR</div>
            <div>{report.mean_reciprocal_rank.toFixed(3)}</div>
            <div className="key">no_context_rate</div>
            <div>{report.no_context_rate.toFixed(3)}</div>
          </div>

          <details style={{ marginTop: 12 }}>
            <summary>Per-query breakdown</summary>
            <ul>
              {report.per_query.map((q, i) => (
                <li key={i}>
                  <strong>{q.query}</strong>: recall={q.recall_at_k.toFixed(2)},
                  precision={q.precision_at_k.toFixed(2)}, RR=
                  {q.reciprocal_rank.toFixed(2)}
                  {q.is_no_context && " ⚠️ no context"}
                  {q.error_message && ` ⚠️ ${q.error_message}`}
                </li>
              ))}
            </ul>
          </details>

          <div className="btn-row">
            <button
              className="btn"
              onClick={() => setStep("publish")}
              disabled={!report.passed}
              data-testid="continue-to-publish"
            >
              К публикации KB →
            </button>
            {!report.passed && (
              <button
                className="btn btn-secondary"
                onClick={() => setStep("review")}
              >
                Вернуться к review карточек
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
