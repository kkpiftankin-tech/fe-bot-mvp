import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listDocuments, uploadDocuments } from "../../../api/setup";
import { ApiError } from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";

export function UploadDocumentsStep(): JSX.Element {
  const { setupJobId, setStep } = useWizardStore();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<File[]>([]);

  const docsQuery = useQuery({
    queryKey: ["docs", setupJobId],
    queryFn: () => {
      if (!setupJobId) throw new Error("no setup_job_id");
      return listDocuments(setupJobId);
    },
    enabled: !!setupJobId,
  });

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!setupJobId) throw new Error("no setup_job_id");
      return uploadDocuments(setupJobId, selected);
    },
    onSuccess: async () => {
      setSelected([]);
      await qc.invalidateQueries({ queryKey: ["docs", setupJobId] });
    },
  });

  const errorMessage =
    uploadMutation.error instanceof ApiError
      ? uploadMutation.error.message
      : uploadMutation.error?.message;

  const documents = docsQuery.data?.documents ?? [];

  return (
    <div>
      <h2>Шаг 2. Загрузить документы</h2>
      <p className="text-muted">
        Поддерживаются: Markdown (.md), Plain Text (.txt), CSV, JSON. Дубликаты
        по checksum SHA-256 пропускаются.
      </p>

      <div className="form-group">
        <label htmlFor="files">Выберите файлы</label>
        <input
          id="files"
          type="file"
          multiple
          accept=".md,.txt,.csv,.json,text/markdown,text/plain,text/csv,application/json"
          onChange={(e) =>
            setSelected(Array.from(e.target.files ?? []))
          }
          data-testid="file-input"
        />
      </div>

      {selected.length > 0 && (
        <ul className="text-muted">
          {selected.map((f) => (
            <li key={f.name}>
              {f.name} — {(f.size / 1024).toFixed(1)} KB
            </li>
          ))}
        </ul>
      )}

      <div className="btn-row">
        <button
          className="btn"
          onClick={() => uploadMutation.mutate()}
          disabled={selected.length === 0 || uploadMutation.isPending}
          data-testid="submit-upload"
        >
          {uploadMutation.isPending ? "Загружаем…" : "Загрузить"}
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => setStep("run")}
          disabled={documents.length === 0}
          data-testid="continue-to-run"
        >
          Далее →
        </button>
      </div>

      {errorMessage && (
        <div className="error-text" data-testid="upload-error">
          {errorMessage}
        </div>
      )}

      <h3 style={{ marginTop: 24 }}>Загруженные документы ({documents.length})</h3>
      {docsQuery.isLoading ? (
        <p className="text-muted">Загружаем список…</p>
      ) : documents.length === 0 ? (
        <p className="text-muted">Пока ничего не загружено.</p>
      ) : (
        <ul data-testid="doc-list">
          {documents.map((d) => (
            <li key={d.source_document_id}>
              <strong>{d.filename}</strong> ({d.content_type},{" "}
              {(d.size_bytes / 1024).toFixed(1)} KB) — {d.status}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
