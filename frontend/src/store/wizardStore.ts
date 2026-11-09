import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { EvalReportResponse } from "../api/types";

// "run" (легаси одношаговый SetupPipeline) намеренно убран из мастера:
// он дублировал шаги 3/4/6/7/8 своим собственным парсером и генератором
// карточек, писал в тот же card_registry и создавал вторую, несовместимую
// по качеству карточку для тех же секций — источник путаницы в UI.
// Эндпоинт и RunPipelineStep.tsx оставлены как internal/legacy-инструмент
// вне мастера (см. RunPipelineStep.tsx), но в WIZARD_STEPS не участвуют.
export type WizardStep =
  | "create"
  | "upload"
  | "parse"
  | "rag_card_generation"
  | "review"
  | "validation"
  | "chunking"
  | "tests"
  | "publish"
  | "report"
  | "classifiers";

// "classifiers" (SETUP-13 / ADR-HTC-09) не привязан к конкретному
// setup_job — это общая библиотека дерева классов + промптов,
// используемая (в будущем) многоуровневым классификатором фрагментов.
// Поэтому, как и "create", он не блокируется отсутствием setupJobId
// (см. WizardLayout.tsx).
export const JOB_INDEPENDENT_STEPS: WizardStep[] = ["create", "classifiers"];

export const WIZARD_STEPS: { id: WizardStep; label: string }[] = [
  { id: "create", label: "1. Создать job" },
  { id: "upload", label: "2. Загрузить документы" },
  { id: "parse", label: "3. Парсинг документов" },
  { id: "rag_card_generation", label: "4. Генерация RAG-карточек" },
  { id: "review", label: "5. Проверить карточки" },
  { id: "validation", label: "6. Валидация metadata" },
  { id: "chunking", label: "7. Chunking + индексация" },
  { id: "tests", label: "8. Retrieval-tests" },
  { id: "publish", label: "9. Публикация KB" },
  { id: "report", label: "10. Отчёт" },
  { id: "classifiers", label: "11. Библиотека классификаторов" },
];

interface WizardState {
  setupJobId: string | null;
  projectName: string;
  currentStep: WizardStep;
  evalReport: EvalReportResponse | null;
  ragCardGenerationJobId: string | null;
  parseJobId: string | null;
  setSetupJobId: (id: string, projectName: string) => void;
  setStep: (step: WizardStep) => void;
  setEvalReport: (report: EvalReportResponse | null) => void;
  setRagCardGenerationJobId: (id: string | null) => void;
  setParseJobId: (id: string | null) => void;
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
      parseJobId: null,
      setSetupJobId: (id, projectName) =>
        set({
          setupJobId: id,
          projectName,
          currentStep: "upload",
          // SETUP-04: при смене setup_job сбрасываем parseJobId, чтобы
          // не отображать stale результаты предыдущего парсинга.
          parseJobId: null,
        }),
      setStep: (step) => set({ currentStep: step }),
      setEvalReport: (report) => set({ evalReport: report }),
      setRagCardGenerationJobId: (id) => set({ ragCardGenerationJobId: id }),
      setParseJobId: (id) => set({ parseJobId: id }),
      reset: () =>
        set({
          setupJobId: null,
          projectName: "",
          currentStep: "create",
          evalReport: null,
          ragCardGenerationJobId: null,
          parseJobId: null,
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
        parseJobId: state.parseJobId,
      }),
      version: 4,
      // v3 → v4: шаг "run" убран из WizardStep. Если в localStorage лежит
      // стейт со старым currentStep="run" — откатываем на "rag_card_generation",
      // чтобы не застрять на несуществующем шаге.
      migrate: (persisted) => {
        const state = persisted as Omit<Partial<WizardState>, "currentStep"> & {
          currentStep?: string;
        };
        if (state?.currentStep === "run") {
          return { ...state, currentStep: "rag_card_generation" as WizardStep };
        }
        return state;
      },
    },
  ),
);
