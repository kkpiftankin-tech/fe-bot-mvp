import { useEffect, useState } from "react";
import { getAuthHeaders, setAuthHeaders } from "./api/client";
import { WizardLayout } from "./components/Wizard/WizardLayout";
import { useHydrateFromUrl } from "./hooks/useHydrateFromUrl";
import { useRestoreWizard } from "./hooks/useRestoreWizard";
import { useWizardStore } from "./store/wizardStore";

export default function App(): JSX.Element {
  const [userId, setUserId] = useState(getAuthHeaders().userId);
  const [roles, setRoles] = useState(getAuthHeaders().roles);
  useHydrateFromUrl();
  const restore = useRestoreWizard();
  const reset = useWizardStore((s) => s.reset);
  const setupJobId = useWizardStore((s) => s.setupJobId);
  const projectName = useWizardStore((s) => s.projectName);

  useEffect(() => {
    setAuthHeaders({ userId, roles });
  }, [userId, roles]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>FE-Bot · Setup Wizard</h1>
        <div className="auth-info">
          <span>X-User-Id: </span>
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            data-testid="auth-user-id"
            style={{ marginRight: 8, width: 120 }}
          />
          <span>X-Roles: </span>
          <input
            value={roles}
            onChange={(e) => setRoles(e.target.value)}
            data-testid="auth-roles"
            style={{ width: 160 }}
          />
          {setupJobId && (
            <span style={{ marginLeft: 16 }}>
              <span className="text-muted">job: </span>
              <code data-testid="active-job">{projectName || setupJobId}</code>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ marginLeft: 8 }}
                onClick={() => {
                  if (
                    confirm(
                      "Сбросить wizard? setup_job на сервере останется, но локальный контекст будет очищен.",
                    )
                  ) {
                    reset();
                  }
                }}
                data-testid="reset-wizard"
              >
                Сбросить
              </button>
            </span>
          )}
        </div>
      </header>
      {restore.status === "stale" && restore.message && (
        <div className="banner banner-warning" data-testid="restore-warning">
          {restore.message}
        </div>
      )}
      {restore.status === "error" && restore.message && (
        <div className="banner banner-error" data-testid="restore-error">
          Не удалось проверить сохранённый setup_job: {restore.message}
        </div>
      )}
      <WizardLayout />
    </div>
  );
}
