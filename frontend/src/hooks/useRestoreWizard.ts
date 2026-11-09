import { useEffect, useState } from "react";
import { getSetupJob } from "../api/setup";
import { ApiError } from "../api/types";
import { useWizardStore } from "../store/wizardStore";

interface RestoreState {
  status: "idle" | "checking" | "restored" | "stale" | "error";
  message: string | null;
}

/**
 * При маунте App.tsx проверяет: сохранённый в localStorage setup_job_id
 * всё ещё существует на backend. Если backend перезапущен (in-memory state
 * потерян) — мягко сбрасываем wizard и показываем сообщение.
 */
export function useRestoreWizard(): RestoreState {
  const setupJobId = useWizardStore((s) => s.setupJobId);
  const reset = useWizardStore((s) => s.reset);
  const [state, setState] = useState<RestoreState>({
    status: "idle",
    message: null,
  });

  useEffect(() => {
    let cancelled = false;
    if (!setupJobId) {
      setState({ status: "idle", message: null });
      return;
    }
    setState({ status: "checking", message: null });
    getSetupJob(setupJobId)
      .then(() => {
        if (cancelled) return;
        setState({ status: "restored", message: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          reset();
          setState({
            status: "stale",
            message:
              "Сохранённый setup_job больше не существует на сервере (вероятно, backend был перезапущен). Wizard сброшен.",
          });
        } else {
          const message =
            err instanceof Error ? err.message : "Ошибка восстановления wizard";
          setState({ status: "error", message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [setupJobId, reset]);

  return state;
}
