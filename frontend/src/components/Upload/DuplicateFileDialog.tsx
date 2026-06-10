/**
 * DuplicateFileDialog (SETUP-02 / T-S02-022).
 *
 * **MVP:** только информационная модалка с одним выбором «Пропустить дубликат»
 * (фактически дубликаты уже пропущены backend'ом — это post-hoc уведомление).
 *
 * Будущие опции `upload_as_new_version` и `replace_existing` помечены feature
 * flags и в MVP скрыты — структура готова к расширению без breaking change.
 *
 * Открывается автоматически после upload, если response.skipped_duplicates
 * содержит файлы.
 */
import type { SourceDocumentResponse } from "../../api/types";

interface DuplicateFileDialogProps {
  duplicates: SourceDocumentResponse[];
  onClose: () => void;
  /** Feature flag: показать выбор «Загрузить как новую версию». */
  enableUploadAsNewVersion?: boolean;
  /** Feature flag: показать выбор «Заменить существующий». */
  enableReplaceExisting?: boolean;
}

export function DuplicateFileDialog({
  duplicates,
  onClose,
  enableUploadAsNewVersion = false,
  enableReplaceExisting = false,
}: DuplicateFileDialogProps): JSX.Element | null {
  if (duplicates.length === 0) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="duplicate-dialog-title"
      className="modal-backdrop"
      data-testid="duplicate-file-dialog"
      onClick={onClose}
    >
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3 id="duplicate-dialog-title">
          Обнаружены дубликаты ({duplicates.length})
        </h3>
        <p className="text-muted">
          Эти файлы (определены по SHA-256 checksum) уже были загружены
          ранее. В MVP такие файлы автоматически пропускаются — повторная
          загрузка не выполнена.
        </p>

        <ul className="duplicate-list" data-testid="duplicate-list">
          {duplicates.map((d) => (
            <li key={d.source_document_id}>
              <strong>{d.filename}</strong>
              <div className="text-muted">
                существующий id:{" "}
                <code>{d.source_document_id}</code>
              </div>
            </li>
          ))}
        </ul>

        {(enableUploadAsNewVersion || enableReplaceExisting) && (
          <div className="banner banner-info" style={{ marginTop: 12 }}>
            <strong>Доступные действия (feature preview):</strong>
            <ul style={{ margin: 0, paddingLeft: 16 }}>
              {enableUploadAsNewVersion && (
                <li data-testid="action-new-version">
                  Загрузить как новую версию (создать parent-child связь)
                </li>
              )}
              {enableReplaceExisting && (
                <li data-testid="action-replace">
                  Заменить существующий (старая версия → archived)
                </li>
              )}
            </ul>
          </div>
        )}

        <div className="btn-row">
          <button
            className="btn"
            onClick={onClose}
            data-testid="dup-dialog-close"
          >
            Пропустить (по умолчанию)
          </button>
        </div>
      </div>
    </div>
  );
}
