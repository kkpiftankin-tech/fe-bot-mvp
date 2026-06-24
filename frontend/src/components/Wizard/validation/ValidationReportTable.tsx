import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listValidationReports } from "../../../api/validation";

interface Props {
  setupJobId: string;
  onSelect?: (docId: string) => void;
}

const STATUS_OPTIONS = ["", "passed", "warning", "failed", "repair_required"];

export function ValidationReportTable({
  setupJobId,
  onSelect,
}: Props): JSX.Element {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [codeFilter, setCodeFilter] = useState<string>("");

  const query = useQuery({
    queryKey: ["validationReports", setupJobId, statusFilter, codeFilter],
    queryFn: () =>
      listValidationReports(setupJobId, {
        status: statusFilter || undefined,
        code: codeFilter || undefined,
      }),
    enabled: !!setupJobId,
  });

  const items = query.data?.items ?? [];

  return (
    <div data-testid="validation-table">
      <div className="btn-row" style={{ gap: 12, flexWrap: "wrap" }}>
        <label>
          status{" "}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            data-testid="filter-status"
          >
            {STATUS_OPTIONS.map((v) => (
              <option key={v} value={v}>
                {v || "— любой —"}
              </option>
            ))}
          </select>
        </label>
        <label>
          code{" "}
          <input
            type="text"
            value={codeFilter}
            onChange={(e) => setCodeFilter(e.target.value)}
            placeholder="UNKNOWN_DOMAIN, …"
            data-testid="filter-code"
          />
        </label>
      </div>

      {query.isLoading && <p>Загрузка…</p>}
      {!query.isLoading && items.length === 0 && (
        <p className="text-muted" data-testid="empty-state">
          Reports пока нет. Запустите валидацию.
        </p>
      )}

      {items.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>doc_id</th>
              <th>version</th>
              <th>status</th>
              <th>errors</th>
              <th>warnings</th>
              <th>created_at</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.validation_report_id}>
                <td>
                  <code>{r.doc_id}</code>
                </td>
                <td>{r.card_version ?? "—"}</td>
                <td>{r.status}</td>
                <td>{r.errors.length}</td>
                <td>{r.warnings.length}</td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td>
                  {onSelect && (
                    <button
                      className="btn btn-secondary"
                      onClick={() => onSelect(r.doc_id)}
                      data-testid={`open-report-${r.doc_id}`}
                    >
                      Открыть
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
