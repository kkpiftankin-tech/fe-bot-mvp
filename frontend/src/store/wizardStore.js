import { create } from "zustand";
export const WIZARD_STEPS = [
    { id: "create", label: "1. Создать job" },
    { id: "upload", label: "2. Загрузить документы" },
    { id: "run", label: "3. Запустить pipeline" },
    { id: "review", label: "4. Проверить карточки" },
    { id: "tests", label: "5. Retrieval-tests" },
    { id: "publish", label: "6. Публикация KB" },
    { id: "report", label: "7. Отчёт" },
];
export const useWizardStore = create((set) => ({
    setupJobId: null,
    projectName: "",
    currentStep: "create",
    evalReport: null,
    setSetupJobId: (id, projectName) => set({ setupJobId: id, projectName, currentStep: "upload" }),
    setStep: (step) => set({ currentStep: step }),
    setEvalReport: (report) => set({ evalReport: report }),
    reset: () => set({
        setupJobId: null,
        projectName: "",
        currentStep: "create",
        evalReport: null,
    }),
}));
