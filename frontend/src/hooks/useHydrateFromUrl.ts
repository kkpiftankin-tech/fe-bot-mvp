// SETUP-04 restore-by-URL: гидрация wizardStore из query-параметров,
// чтобы можно было прислать пользователю ссылку вроде
// http://localhost:5173/?setup=setup_XYZ&pj=pj_ABC&project=name&step=parse
// и wizard подхватит state без правки localStorage вручную.
//
// Runs once on mount. Если URL содержит `setup` — устанавливает setupJobId,
// projectName (default = "restored"), currentStep, parseJobId (если задан).
// После этого чистит URL, чтобы reload не подхватывал query повторно.

import { useEffect } from "react";
import { useWizardStore, type WizardStep } from "../store/wizardStore";

const KNOWN_STEPS: readonly WizardStep[] = [
  "create",
  "upload",
  "parse",
  "rag_card_generation",
  "review",
  "validation",
  "chunking",
  "tests",
  "publish",
  "report",
];

function _asStep(raw: string | null): WizardStep | null {
  if (!raw) return null;
  return KNOWN_STEPS.includes(raw as WizardStep) ? (raw as WizardStep) : null;
}

export function useHydrateFromUrl(): void {
  useEffect(() => {
    const url = new URL(window.location.href);
    const setup = url.searchParams.get("setup");
    if (!setup) return;

    const parseJob = url.searchParams.get("pj");
    const project = url.searchParams.get("project") ?? "restored";
    const step = _asStep(url.searchParams.get("step"));

    const store = useWizardStore.getState();
    store.setSetupJobId(setup, project);
    if (parseJob) store.setParseJobId(parseJob);
    if (step) store.setStep(step);

    // Уберём query, чтобы не срабатывало на будущих reload'ах.
    url.searchParams.delete("setup");
    url.searchParams.delete("pj");
    url.searchParams.delete("project");
    url.searchParams.delete("step");
    window.history.replaceState({}, "", url.pathname + url.hash);
  }, []);
}
