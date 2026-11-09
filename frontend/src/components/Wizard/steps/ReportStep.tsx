import { useQuery } from "@tanstack/react-query";
import { getReport } from "../../../api/setup";
import { useWizardStore } from "../../../store/wizardStore";
import { TaxonomyTreeView } from "../../Taxonomy/TaxonomyTreeView";

export function ReportStep(): JSX.Element {
  const { setupJobId, reset } = useWizardStore();

  const reportQuery = useQuery({
    queryKey: ["report", setupJobId],
    queryFn: () => {
      if (!setupJobId) throw new Error("no setup_job_id");
      return getReport(setupJobId);
    },
    enabled: !!setupJobId,
  });

  if (reportQuery.isLoading) {
    return <p className="text-muted">Загружаем отчёт…</p>;
  }
  if (!reportQuery.data) {
    return <p className="error-text">Отчёт недоступен.</p>;
  }

  const r = reportQuery.data;

  return (
    <div>
      <h2>Шаг 10. Итоговый отчёт</h2>
      <p className="text-muted">
        Сводка по всему setup job — используется auditor'ом для проверки качества
        KB до выкатки в Runtime.
      </p>

      <div
        className={
          r.knowledge_base_is_active
            ? "banner banner-success"
            : "banner banner-info"
        }
        data-testid="report-banner"
      >
        Job <strong>{r.setup_job_id}</strong> · статус: {r.status}
        {r.knowledge_base_version && (
          <>
            <br />
            Active KB: <strong>{r.knowledge_base_version}</strong> ·{" "}
            {r.knowledge_base_status}
          </>
        )}
      </div>

      <h3>Проект</h3>
      <div className="kv-grid">
        <div className="key">project_name</div>
        <div>{r.project_name}</div>
        <div className="key">user_id</div>
        <div>{r.user_id}</div>
        <div className="key">started_at</div>
        <div>{r.started_at ?? "—"}</div>
        <div className="key">finished_at</div>
        <div>{r.finished_at ?? "—"}</div>
      </div>

      <h3 style={{ marginTop: 16 }}>Документы и карточки</h3>
      <div className="kv-grid">
        <div className="key">Документов загружено</div>
        <div>{r.documents_count}</div>
        <div className="key">Всего карточек</div>
        <div>{r.cards_count}</div>
        <div className="key">Approved+indexed+published</div>
        <div>{r.cards_approved}</div>
        <div className="key">Требуют review</div>
        <div>{r.cards_review_required}</div>
        <div className="key">Deprecated</div>
        <div>{r.cards_deprecated}</div>
      </div>

      <h3 style={{ marginTop: 16 }}>Indexing & Knowledge Base</h3>
      <div className="kv-grid">
        <div className="key">chunks_indexed</div>
        <div>{r.chunks_indexed}</div>
        <div className="key">index_version</div>
        <div>{r.index_version ?? "—"}</div>
        <div className="key">knowledge_base_version</div>
        <div>{r.knowledge_base_version ?? "—"}</div>
        <div className="key">knowledge_base_status</div>
        <div>{r.knowledge_base_status ?? "—"}</div>
        <div className="key">eval_passed</div>
        <div>
          {r.eval_passed === null
            ? "—"
            : r.eval_passed
              ? "✓"
              : "✗"}
        </div>
      </div>

      <h3 style={{ marginTop: 16 }}>Прогресс</h3>
      <div className="progress-bar">
        <div style={{ width: `${r.progress_percent}%` }} />
      </div>
      <div className="text-muted">
        {r.progress_percent.toFixed(0)}% · ошибок: {r.error_count}, предупреждений:{" "}
        {r.warning_count}
      </div>

      <div className="btn-row">
        <button
          className="btn btn-secondary"
          onClick={() => reset()}
          data-testid="new-job"
        >
          Начать новый setup
        </button>
      </div>

      <div style={{ marginTop: 32 }}>
        <TaxonomyTreeView />
      </div>
    </div>
  );
}
