import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { EvalReportResponse } from "../api/types";

export type WizardStep =
  | "create"
  | "upload"
  | "parse"
  | "rag_card_generation"
  | "run"
  | "review"
  | "validation"
  | "chunking"
  | "tests"
  | "publish"
  | "report";

export const WIZARD_STEPS: { id: WizardStep; label: string }[] = [
  { id: "create", label: "1. Создать job" },
  { id: "upload", label: "2. Загрузить документы" },
  { id: "parse", label: "3. Парсинг документов" },
  { id: "rag_card_generation", label: "4. Генерация RAG-карточек" },
  { id: "run", label: "5. Запустить pipeline" },
  { id: "review", label: "6. Проверить карточки" },
  { id: "validation", label: "7. Валидация metadata" },
  { id: "chunking", label: "8. Chunking" },
  { id: "tests", label: "9. Retrieval-tests" },
  { id: "publish", label: "10. Публикация KB" },
  { id: "report", label: "11. Отчёт" },
];

interface WizardState {
  setupJobId: string | null;
  projectName: string;
  currentStep: WizardStep;
  evalReport: EvalReportResponse | null;
  ragCardGenerationJobId: string | null;
  setSetupJobId: (id: string, projectName: string) => void;
  setStep: (step: WizardStep) => void;
  setEvalReport: (report: EvalReportResponse | null) => void;
  setRagCardGenerationJobId: (id: string | null) => void;
  reset: () => void;
}

const STORAGE_KEY = "fe-bot.wizard.v1";

export const useWizardStore = create<WizardState>()(
  persist(
    (set) => ({
      setupJobId: null,
      projectName: "",
      currentStep: "create",
      evalReport: null,
      ragCardGenerationJobId: null,
      setSetupJobId: (id, projectName) =>
        set({ setupJobId: id, projectName, currentStep: "upload" }),
      setStep: (step) => set({ currentStep: step }),
      setEvalReport: (report) => set({ evalReport: report }),
      setRagCardGenerationJobId: (id) => set({ ragCardGenerationJobId: id }),
      reset: () =>
        set({
          setupJobId: null,
          projectName: "",
          currentStep: "create",
          evalReport: null,
          ragCardGenerationJobId: null,
        }),
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      // evalReport не сохраняем — это эфемерный отчёт прогона.
      partialize: (state) => ({
        setupJobId: state.setupJobId,
        projectName: state.projectName,
        currentStep: state.currentStep,
        ragCardGenerationJobId: state.ragCardGenerationJobId,
      }),
      version: 2,
    },
  ),
);
