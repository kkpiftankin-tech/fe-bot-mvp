import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { WIZARD_STEPS, useWizardStore } from "../../store/wizardStore";
import { CreateJobStep } from "./steps/CreateJobStep";
import { PublishStep } from "./steps/PublishStep";
import { ReportStep } from "./steps/ReportStep";
import { RetrievalTestsStep } from "./steps/RetrievalTestsStep";
import { ReviewCardsStep } from "./steps/ReviewCardsStep";
import { RunPipelineStep } from "./steps/RunPipelineStep";
import { UploadDocumentsStep } from "./steps/UploadDocumentsStep";
export function WizardLayout() {
    const { currentStep, setupJobId, setStep } = useWizardStore();
    return (_jsxs("div", { className: "wizard", children: [_jsx("nav", { className: "wizard-nav", "aria-label": "\u0428\u0430\u0433\u0438 \u043C\u0430\u0441\u0442\u0435\u0440\u0430", children: _jsx("ul", { children: WIZARD_STEPS.map((step) => {
                        const isFirst = step.id === "create";
                        const disabled = !isFirst && !setupJobId;
                        const isActive = currentStep === step.id;
                        return (_jsx("li", { className: `${isActive ? "active" : ""} ${disabled ? "disabled" : ""}`, onClick: () => !disabled && setStep(step.id), "data-testid": `nav-${step.id}`, children: step.label }, step.id));
                    }) }) }), _jsxs("section", { className: "wizard-content", "aria-live": "polite", children: [currentStep === "create" && _jsx(CreateJobStep, {}), currentStep === "upload" && _jsx(UploadDocumentsStep, {}), currentStep === "run" && _jsx(RunPipelineStep, {}), currentStep === "review" && _jsx(ReviewCardsStep, {}), currentStep === "tests" && _jsx(RetrievalTestsStep, {}), currentStep === "publish" && _jsx(PublishStep, {}), currentStep === "report" && _jsx(ReportStep, {})] })] }));
}
