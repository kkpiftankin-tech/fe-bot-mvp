import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getValidationSummary, runValidation } from "../../../api/validation";

interface Props {
  setupJobId: string;
  onRun?: () => void;
}

export function ValidationSummaryCard({ setupJobId, onRun }: Props): JSX.Element {
  const qc = useQueryClient();
  const summary = useQuery({
    queryKey: ["validationSummary", setupJobId],
    queryFn: () => getValidationSummary(setupJobId),
    enabled: !!setupJobId,
  });

  const runMut = useMutation({
    mutationFn: () => runValidation(setupJobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["validationSummary", setupJobId] });
      qc.invalidateQueries({ queryKey: ["validationReports", setupJobId] });
      onRun?.();
    },
  });

  const s = summary.data;

  return (
    <div
      data-testid="validation-summary"
      className="card"
      style={{
        border: "1px solid #ddd",
        borderRadius: 4,
        padding: 16,
        marginBottom: 16,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>Валидация metadata</h3>
        <button
          className="btn"
          onClick={() => runMut.mutate()}
          disabled={runMut.isPending}
          data-testid="run-validation"
        >
          {runMut.isPending ? "Запускаем…" : "Запустить валидацию"}
        </button>
      </div>

      {summary.isLoading && <p>Загрузка…</p>}
      {summary.error && (
        <div className="banner banner-error">
          {summary.error instanceof Error ? summary.error.message : "Ошибка"}
        </div>
      )}

      {s && (
        <div style={{ marginTop: 12 }}>
          <p>
            Всего: <strong>{s.total}</strong> · passed: {s.passed} · warnings:{" "}
            {s.warnings} · failed: {s.failed} · review_required:{" "}
            {s.review_required}
          </p>
          {Object.keys(s.by_code).length > 0 && (
            <details>
              <summary>Issues by code</summary>
              <ul>
                {Object.entries(s.by_code).map(([code, count]) => (
                  <li key={code}>
                    <code>{code}</code>: {count}
                  </li>
                ))}
              </ul>
            </details>
          )}
          {s.last_run_id && (
            <p className="text-muted">Last run: <code>{s.last_run_id}</code></p>
          )}
        </div>
      )}

      {runMut.isError && (
        <div className="banner banner-error" style={{ marginTop: 8 }}>
          {runMut.error instanceof Error
            ? runMut.error.message
            : "Не удалось запустить валидацию"}
        </div>
      )}
    </div>
  );
}
