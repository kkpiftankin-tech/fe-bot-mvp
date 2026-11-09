import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { getAuthHeaders } from "../../../api/client";
import { listDocuments } from "../../../api/setup";
import type { SourceDocumentResponse } from "../../../api/types";
import { useUploadProgress } from "../../../hooks/useUploadProgress";
import {
  ALLOWED_EXTENSIONS,
  type ValidationError,
} from "../../../lib/uploadValidation";
import { useWizardStore } from "../../../store/wizardStore";
import { DuplicateFileDialog } from "../../Upload/DuplicateFileDialog";
import { FileUploadPanel } from "../../Upload/FileUploadPanel";
import { FileValidationErrorsPanel } from "../../Upload/FileValidationErrorsPanel";
import { UploadProgressList } from "../../Upload/UploadProgressList";
import { UploadedFilesTable } from "../../Upload/UploadedFilesTable";

export function UploadDocumentsStep(): JSX.Element {
  const { setupJobId, setStep } = useWizardStore();
  const qc = useQueryClient();
  const [validFiles, setValidFiles] = useState<File[]>([]);
  const [invalidFiles, setInvalidFiles] = useState<
    { file: File; error: ValidationError }[]
  >([]);
  const [batchErrors, setBatchErrors] = useState<ValidationError[]>([]);
  const [batchFilenames, setBatchFilenames] = useState<string[]>([]);
  const [duplicatesDialog, setDuplicatesDialog] = useState<
    SourceDocumentResponse[] | null
  >(null);

  const { progress, response, error, inFlight, upload, reset } =
    useUploadProgress();

  const docsQuery = useQuery({
    queryKey: ["docs", setupJobId],
    queryFn: () => {
      if (!setupJobId) throw new Error("no setup_job_id");
      return listDocuments(setupJobId);
    },
    enabled: !!setupJobId,
  });

  // T-S02-022: показать duplicate dialog, если backend пометил файлы как дубликаты.
  useEffect(() => {
    if (response?.skipped_duplicates && response.skipped_duplicates.length > 0) {
      setDuplicatesDialog(response.skipped_duplicates);
    }
  }, [response]);

  const handleFilesChange = useCallback(
    (state: {
      valid: File[];
      invalid: { file: File; error: ValidationError }[];
      batchErrors: ValidationError[];
    }) => {
      setValidFiles(state.valid);
      setInvalidFiles(state.invalid);
      setBatchErrors(state.batchErrors);
    },
    [],
  );

  const handleSubmit = useCallback(async () => {
    if (!setupJobId || validFiles.length === 0) return;
    const auth = getAuthHeaders();
    const headers = {
      "X-User-Id": auth.userId,
      "X-Roles": auth.roles,
    };
    setBatchFilenames(validFiles.map((f) => f.name));
    try {
      await upload(
        `/api/v1/setup/${setupJobId}/documents`,
        validFiles,
        headers,
      );
      setValidFiles([]);
      setInvalidFiles([]);
      setBatchErrors([]);
      await qc.invalidateQueries({ queryKey: ["docs", setupJobId] });
    } catch {
      // error состояние в hook'е, обрабатывается отдельно
    }
  }, [qc, setupJobId, upload, validFiles]);

  const documents = docsQuery.data?.documents ?? [];
  const blockingBatchErrors = batchErrors.length > 0;
  const canSubmit =
    validFiles.length > 0 && !inFlight && !blockingBatchErrors;

  return (
    <div>
      <h2>Шаг 2. Загрузить документы</h2>
      <p className="text-muted">
        Поддерживаются: {ALLOWED_EXTENSIONS.join(", ")}. Дубликаты по
        checksum SHA-256 пропускаются (показываются отдельно).
      </p>

      <FileUploadPanel
        onChange={handleFilesChange}
        disabled={!setupJobId}
      />

      <FileValidationErrorsPanel
        clientInvalid={invalidFiles}
        clientBatchErrors={batchErrors}
        serverErrors={response?.errors ?? []}
        onClear={() => {
          setInvalidFiles([]);
          setBatchErrors([]);
        }}
      />

      <div className="btn-row">
        <button
          className="btn"
          onClick={handleSubmit}
          disabled={!canSubmit}
          data-testid="submit-upload"
        >
          {inFlight
            ? `Загружаем… ${progress.overall}%`
            : `Загрузить ${validFiles.length} файл(ов)`}
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => {
            reset();
            setBatchFilenames([]);
          }}
          disabled={inFlight || (!response && !error)}
          data-testid="clear-progress"
        >
          Сбросить прогресс
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => setStep("parse")}
          disabled={documents.filter((d) => d.status !== "removed").length === 0}
          data-testid="continue-to-parse"
        >
          Далее →
        </button>
      </div>

      {batchFilenames.length > 0 && (
        <UploadProgressList
          filenames={batchFilenames}
          perFileProgress={progress.perFile}
          inFlight={inFlight}
          response={response}
          error={error}
        />
      )}

      {response?.summary && (
        <div
          className={
            response.summary.files_rejected === 0
              ? "banner banner-success"
              : "banner banner-warning"
          }
          style={{ marginTop: 12 }}
          data-testid="upload-summary"
        >
          Из {response.summary.files_total} файлов: загружено{" "}
          {response.summary.files_uploaded}, дубликатов{" "}
          {response.summary.duplicates_detected}, отклонено{" "}
          {response.summary.files_rejected}.
          {response.upload_batch_id && (
            <span className="text-muted">
              {" "}
              · batch_id: {response.upload_batch_id}
            </span>
          )}
        </div>
      )}

      {setupJobId && (
        <div style={{ marginTop: 24 }}>
          <h3>Загруженные документы ({documents.length})</h3>
          <UploadedFilesTable
            setupJobId={setupJobId}
            documents={documents}
            loading={docsQuery.isLoading}
          />
        </div>
      )}

      {duplicatesDialog && (
        <DuplicateFileDialog
          duplicates={duplicatesDialog}
          onClose={() => setDuplicatesDialog(null)}
        />
      )}
    </div>
  );
}
