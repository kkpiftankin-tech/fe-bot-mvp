/**
 * UploadProgressList (SETUP-02 / T-S02-018).
 *
 * Per-file progress bars + статусы:
 *   - uploading: in-flight (XHR onprogress)
 *   - uploaded: окончено, файл в response.uploaded
 *   - duplicate: окончено, файл в response.skipped_duplicates
 *   - rejected: окончено, файл в response.errors с error_code
 */
import type { UploadDocumentsResponse } from "../../api/types";

interface UploadProgressListProps {
  /** Файлы, отправленные в upload (для определения "что было в batch"). */
  filenames: string[];
  /** Per-file progress percent 0..100. */
  perFileProgress: Record<string, number>;
  inFlight: boolean;
  /** Если есть — отображаем финальные статусы вместо прогресса. */
  response?: UploadDocumentsResponse | null;
  /** Глобальная ошибка (сеть, 5xx). */
  error?: string | null;
}

type Outcome = "uploading" | "uploaded" | "duplicate" | "rejected" | "pending";

function outcomeFor(
  filename: string,
  response: UploadDocumentsResponse | null | undefined,
  inFlight: boolean,
): { outcome: Outcome; message?: string } {
  if (response) {
    if (response.uploaded.some((d) => d.filename === filename)) {
      return { outcome: "uploaded" };
    }
    if (response.skipped_duplicates.some((d) => d.filename === filename)) {
      return { outcome: "duplicate", message: "Уже загружен ранее" };
    }
    const err = response.errors?.find((e) => e.filename === filename);
    if (err) {
      return { outcome: "rejected", message: `${err.error_code}: ${err.message}` };
    }
  }
  return { outcome: inFlight ? "uploading" : "pending" };
}

const OUTCOME_LABEL: Record<Outcome, string> = {
  uploading: "Загружается",
  uploaded: "Загружен",
  duplicate: "Дубликат",
  rejected: "Отклонён",
  pending: "Ожидание",
};

export function UploadProgressList({
  filenames,
  perFileProgress,
  inFlight,
  response,
  error,
}: UploadProgressListProps): JSX.Element | null {
  if (filenames.length === 0) return null;

  return (
    <div className="upload-progress-list" data-testid="upload-progress-list">
      {error && (
        <div className="banner banner-error" data-testid="upload-fatal-error">
          {error}
        </div>
      )}
      <ul>
        {filenames.map((name, idx) => {
          const pct = perFileProgress[name] ?? 0;
          const { outcome, message } = outcomeFor(name, response, inFlight);
          return (
            <li
              key={`${name}-${idx}`}
              className={`progress-row ${outcome}`}
              data-testid={`progress-row-${idx}`}
            >
              <div className="progress-row-header">
                <span className="filename">{name}</span>
                <span
                  className={`badge badge-${outcome}`}
                  data-testid={`outcome-${idx}`}
                >
                  {OUTCOME_LABEL[outcome]}
                </span>
              </div>
              <div className="progress-bar" aria-label={`${name}: ${pct}%`}>
                <div style={{ width: `${pct}%` }} />
              </div>
              {message && (
                <div
                  className={outcome === "rejected" ? "error-text" : "text-muted"}
                  data-testid={`outcome-message-${idx}`}
                >
                  {message}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
