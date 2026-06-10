/**
 * FileUploadPanel (SETUP-02 / T-S02-017).
 *
 * Drag-and-drop area + fallback file picker. Показывает список выбранных
 * файлов с per-file size + extension, валидирует client-side через
 * lib/uploadValidation, передаёт outcome (valid + invalid) в onChange.
 */
import { useCallback, useId, useMemo, useRef, useState } from "react";
import {
  ALLOWED_EXTENSIONS,
  MAX_FILE_SIZE_BYTES,
  partitionByValidation,
  validateBatch,
  type ValidationError,
} from "../../lib/uploadValidation";

interface FileUploadPanelProps {
  /** Вызывается при каждом изменении выбора. */
  onChange: (state: {
    valid: File[];
    invalid: { file: File; error: ValidationError }[];
    batchErrors: ValidationError[];
  }) => void;
  /** Disabled state (no setup_job или job не принимает upload). */
  disabled?: boolean;
  /** Подсказка над зоной. */
  hint?: string;
}

const ACCEPT_ATTR = ALLOWED_EXTENSIONS.map((e) => `.${e}`).join(",");

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileUploadPanel({
  onChange,
  disabled = false,
  hint,
}: FileUploadPanelProps): JSX.Element {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  const computeValidation = useCallback(
    (next: File[]) => {
      const batchResult = validateBatch(next);
      // Per-file partition (исключаем batch-level errors из per-file).
      const { valid, invalid } = partitionByValidation(next);
      // Batch-level errors — те, у которых filename пустой
      // ИЛИ duplicate_in_batch (не per-file).
      const batchErrors = batchResult.errors.filter(
        (e) =>
          e.filename === "" ||
          e.details?.reason === "duplicate_in_batch" ||
          e.details?.reason === "too_many_files" ||
          e.details?.reason === "total_size_exceeded",
      );
      return { valid, invalid, batchErrors };
    },
    [],
  );

  const applyFiles = useCallback(
    (next: File[]) => {
      setFiles(next);
      onChange(computeValidation(next));
    },
    [computeValidation, onChange],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled) return;
      const dropped = Array.from(e.dataTransfer.files);
      applyFiles([...files, ...dropped]);
    },
    [applyFiles, disabled, files],
  );

  const handleSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (disabled) return;
      const picked = Array.from(e.target.files ?? []);
      applyFiles([...files, ...picked]);
      // Сброс input.value чтобы повторный выбор того же файла тригал change.
      if (inputRef.current) inputRef.current.value = "";
    },
    [applyFiles, disabled, files],
  );

  const handleRemove = useCallback(
    (idx: number) => {
      applyFiles(files.filter((_, i) => i !== idx));
    },
    [applyFiles, files],
  );

  const handleClear = useCallback(() => {
    applyFiles([]);
  }, [applyFiles]);

  const { invalid, batchErrors } = useMemo(
    () => computeValidation(files),
    [computeValidation, files],
  );
  const invalidByName = useMemo(
    () => new Map(invalid.map((x) => [x.file.name, x.error])),
    [invalid],
  );

  return (
    <div className="upload-panel" data-testid="file-upload-panel">
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-label="Зона загрузки файлов"
        className={`drop-zone ${isDragging ? "dragging" : ""} ${disabled ? "disabled" : ""}`}
        onDragEnter={(e) => {
          e.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        data-testid="drop-zone"
      >
        <p>
          {disabled
            ? "Загрузка недоступна для этого setup-job"
            : isDragging
              ? "Отпустите, чтобы добавить файлы"
              : "Перетащите файлы сюда или нажмите для выбора"}
        </p>
        <p className="text-muted">
          {hint ??
            `Допустимые форматы: ${ALLOWED_EXTENSIONS.join(", ")}. Максимум ${formatBytes(MAX_FILE_SIZE_BYTES)} на файл.`}
        </p>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          multiple
          accept={ACCEPT_ATTR}
          onChange={handleSelect}
          disabled={disabled}
          style={{ display: "none" }}
          data-testid="file-input"
        />
      </div>

      {batchErrors.length > 0 && (
        <ul className="batch-errors" data-testid="batch-errors">
          {batchErrors.map((e, i) => (
            <li key={i} className="error-text">
              {e.message}
            </li>
          ))}
        </ul>
      )}

      {files.length > 0 && (
        <>
          <div className="row" style={{ marginTop: 12 }}>
            <strong>Выбрано файлов: {files.length}</strong>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleClear}
              style={{ marginLeft: "auto" }}
              data-testid="clear-files"
            >
              Очистить
            </button>
          </div>
          <ul className="selected-files" data-testid="selected-files">
            {files.map((f, idx) => {
              const err = invalidByName.get(f.name);
              return (
                <li
                  key={`${f.name}-${idx}`}
                  className={err ? "file-row invalid" : "file-row"}
                  data-testid={`file-row-${idx}`}
                >
                  <span className="filename">{f.name}</span>
                  <span className="text-muted">{formatBytes(f.size)}</span>
                  {err && (
                    <span
                      className="error-text"
                      data-testid={`file-error-${idx}`}
                    >
                      {err.message}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => handleRemove(idx)}
                    className="btn-icon"
                    aria-label={`Удалить ${f.name}`}
                    data-testid={`remove-file-${idx}`}
                  >
                    ×
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
