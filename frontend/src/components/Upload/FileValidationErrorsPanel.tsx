/**
 * FileValidationErrorsPanel (SETUP-02 / T-S02-021).
 *
 * Унифицирует отображение ошибок из двух источников:
 *   1. client-side: per-file invalid + batch-level errors (из FileUploadPanel.onChange)
 *   2. server-side: response.errors (из POST /documents после upload)
 *
 * Show summary banner ("N invalid, K duplicates, M uploaded") + expandable
 * per-file error rows.
 */
import { useState } from "react";
import type { UploadFileError } from "../../api/types";
import type { ValidationError } from "../../lib/uploadValidation";

interface FileValidationErrorsPanelProps {
  /** Client-side per-file invalid (preview before submit). */
  clientInvalid: { file: File; error: ValidationError }[];
  /** Client-side batch-level errors (count/size/duplicate-name). */
  clientBatchErrors: ValidationError[];
  /** Server-side per-file errors after submit (response.errors). */
  serverErrors: UploadFileError[];
  /** Очистить (вызывается caller'ом для сброса состояния). */
  onClear?: () => void;
}

const ERROR_CODE_HINT: Record<string, string> = {
  UNSUPPORTED_FILE_TYPE:
    "Загрузите файл одного из поддерживаемых форматов (md/txt/pdf/docx/xlsx/csv/json).",
  FILE_TOO_LARGE: "Файл превышает максимально допустимый размер.",
  EMPTY_FILE: "Файл пустой. Проверьте содержимое.",
  INVALID_FILENAME:
    "Имя файла содержит запрещённые символы или слишком длинное.",
  BATCH_TOO_LARGE: "Уменьшите количество или общий размер файлов в batch.",
  MISSING_FILES: "Выберите хотя бы один файл.",
  DUPLICATE_FILE:
    "Файл с таким же содержимым уже загружен — будет пропущен.",
  OBJECT_STORAGE_UNAVAILABLE:
    "Внутренняя ошибка хранилища. Попробуйте ещё раз через минуту.",
};

export function FileValidationErrorsPanel({
  clientInvalid,
  clientBatchErrors,
  serverErrors,
  onClear,
}: FileValidationErrorsPanelProps): JSX.Element | null {
  const [expanded, setExpanded] = useState(false);

  const totalClientErrors = clientInvalid.length + clientBatchErrors.length;
  const totalServerErrors = serverErrors.length;
  const total = totalClientErrors + totalServerErrors;

  if (total === 0) return null;

  return (
    <div
      className="banner banner-error"
      style={{ marginTop: 12 }}
      data-testid="validation-errors-panel"
    >
      <div className="row" style={{ alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <strong>Ошибки валидации: {total}</strong>
          {totalClientErrors > 0 && (
            <span className="text-muted">
              {" "}
              · клиент: {totalClientErrors}
            </span>
          )}
          {totalServerErrors > 0 && (
            <span className="text-muted">
              {" "}
              · сервер: {totalServerErrors}
            </span>
          )}
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setExpanded(!expanded)}
          data-testid="toggle-errors"
        >
          {expanded ? "Свернуть" : "Развернуть"}
        </button>
        {onClear && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClear}
            data-testid="clear-errors"
          >
            Очистить
          </button>
        )}
      </div>

      {expanded && (
        <ul className="error-list" data-testid="error-list">
          {clientBatchErrors.map((e, i) => (
            <li key={`bc-${i}`} data-testid={`batch-error-${i}`}>
              <code>{e.error_code}</code>: {e.message}
            </li>
          ))}
          {clientInvalid.map((x, i) => (
            <li key={`ci-${i}`} data-testid={`client-error-${i}`}>
              <strong>{x.file.name}</strong>:{" "}
              <code>{x.error.error_code}</code> — {x.error.message}
              {ERROR_CODE_HINT[x.error.error_code] && (
                <div className="text-muted">
                  {ERROR_CODE_HINT[x.error.error_code]}
                </div>
              )}
            </li>
          ))}
          {serverErrors.map((e, i) => (
            <li key={`se-${i}`} data-testid={`server-error-${i}`}>
              <strong>{e.filename}</strong>:{" "}
              <code>{e.error_code}</code> — {e.message}
              {ERROR_CODE_HINT[e.error_code] && (
                <div className="text-muted">
                  {ERROR_CODE_HINT[e.error_code]}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
