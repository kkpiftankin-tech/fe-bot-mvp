import { JOB_INDEPENDENT_STEPS, WIZARD_STEPS, useWizardStore } from "../../store/wizardStore";
import { ChunkingStep } from "./steps/ChunkingStep";
import { ClassifierLibraryStep } from "./steps/ClassifierLibraryStep";
import { CreateJobStep } from "./steps/CreateJobStep";
import { ParsingStep } from "./steps/ParsingStep";
import { PublishStep } from "./steps/PublishStep";
import { RAGCardGenerationStep } from "./steps/RAGCardGenerationStep";
import { ReportStep } from "./steps/ReportStep";
import { RetrievalTestsStep } from "./steps/RetrievalTestsStep";
import { ReviewCardsStep } from "./steps/ReviewCardsStep";
import { UploadDocumentsStep } from "./steps/UploadDocumentsStep";
import { ValidationStep } from "./steps/ValidationStep";

export function WizardLayout(): JSX.Element {
  const { currentStep, setupJobId, setStep } = useWizardStore();

  return (
    <div className="wizard">
      <nav className="wizard-nav" aria-label="Шаги мастера">
        <ul>
          {WIZARD_STEPS.map((step) => {
            const jobIndependent = JOB_INDEPENDENT_STEPS.includes(step.id);
            const disabled = !jobIndependent && !setupJobId;
            const isActive = currentStep === step.id;
            return (
              <li
                key={step.id}
                className={`${isActive ? "active" : ""} ${disabled ? "disabled" : ""}`}
                onClick={() => !disabled && setStep(step.id)}
                data-testid={`nav-${step.id}`}
              >
                {step.label}
              </li>
            );
          })}
        </ul>
      </nav>
      <section className="wizard-content" aria-live="polite">
        {currentStep === "create" && <CreateJobStep />}
        {currentStep === "upload" && <UploadDocumentsStep />}
        {currentStep === "parse" && <ParsingStep />}
        {currentStep === "rag_card_generation" && <RAGCardGenerationStep />}
        {currentStep === "review" && <ReviewCardsStep />}
        {currentStep === "validation" && <ValidationStep />}
        {currentStep === "chunking" && <ChunkingStep />}
        {currentStep === "tests" && <RetrievalTestsStep />}
        {currentStep === "publish" && <PublishStep />}
        {currentStep === "report" && <ReportStep />}
        {currentStep === "classifiers" && <ClassifierLibraryStep />}
      </section>
    </div>
  );
}
