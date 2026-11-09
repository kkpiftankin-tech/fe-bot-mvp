import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { createSetupJob } from "../../../api/setup";
import { ApiError } from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";
import { SavedSetupsPanel } from "../SavedSetupsPanel";

export function CreateJobStep(): JSX.Element {
  const setSetupJobId = useWizardStore((s) => s.setSetupJobId);
  const [projectName, setProjectName] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createSetupJob({
        project_name: projectName,
        domain: domain || undefined,
        description: description || undefined,
      }),
    onSuccess: (job) => setSetupJobId(job.setup_job_id, job.project_name),
  });

  const errorMessage =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error?.message;

  return (
    <div>
      <h2>Шаг 1. Создать setup job</h2>

      <SavedSetupsPanel />

      <h3 style={{ marginTop: 24 }}>Или создать новый</h3>
      <p className="text-muted">
        Дайте проекту имя — оно станет идентификатором knowledge base.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <div className="form-group">
          <label htmlFor="project_name">Название проекта (≥ 3 символов)</label>
          <input
            id="project_name"
            data-testid="project-name"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            required
            minLength={3}
            maxLength={128}
          />
        </div>
        <div className="form-group">
          <label htmlFor="domain">Домен (опционально)</label>
          <input
            id="domain"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="например, naval / fintech / healthcare"
          />
        </div>
        <div className="form-group">
          <label htmlFor="description">Описание (опционально)</label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
          />
        </div>
        <div className="btn-row">
          <button
            className="btn"
            type="submit"
            disabled={mutation.isPending || projectName.length < 3}
            data-testid="submit-create"
          >
            {mutation.isPending ? "Создаём…" : "Создать job"}
          </button>
        </div>
        {errorMessage && (
          <div className="error-text" data-testid="create-error">
            {errorMessage}
          </div>
        )}
        {mutation.isSuccess && mutation.data && (
          <div
            className="banner banner-success"
            style={{ marginTop: 16 }}
            data-testid="create-success"
          >
            Job создан: {mutation.data.setup_job_id}. Переходите к шагу 2.
          </div>
        )}
      </form>
    </div>
  );
}
