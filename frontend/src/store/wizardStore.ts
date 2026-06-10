import { create } from "zustand";
import type { EvalReportResponse } from "../api/types";

export type WizardStep =
  | "create"
  | "upload"
  | "run"
  | "review"
  | "tests"
  | "publish"
  | "report";

export const WIZARD_STEPS: { id: WizardStep; label: string }[] = [
  { id: "create", label: "1. Создать job" },
  { id: "upload", label: "2. Загрузить документы" },
  { id: "run", label: "3. Запустить pipeline" },
  { id: "review", label: "4. Проверить карточки" },
  { id: "tests", label: "5. Retrieval-tests" },
  { id: "publish", label: "6. Публикация KB" },
  { id: "report", label: "7. Отчёт" },
];

interface WizardState {
  setupJobId: string | null;
  projectName: string;
  currentStep: WizardStep;
  evalReport: EvalReportResponse | null;
  setSetupJobId: (id: string, projectName: string) => void;
  setStep: (step: WizardStep) => void;
  setEvalReport: (report: EvalReportResponse | null) => void;
  reset: () => void;
}

export const useWizardStore = create<WizardState>((set) => ({
  setupJobId: null,
  projectName: "",
  currentStep: "create",
  evalReport: null,
  setSetupJobId: (id, projectName) =>
    set({ setupJobId: id, projectName, currentStep: "upload" }),
  setStep: (step) => set({ currentStep: step }),
  setEvalReport: (report) => set({ evalReport: report }),
  reset: () =>
    set({
      setupJobId: null,
      projectName: "",
      currentStep: "create",
      evalReport: null,
    }),
}));
