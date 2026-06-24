import { useState } from "react";
import { useWizardStore } from "../../../store/wizardStore";
import { ValidationReportTable } from "../validation/ValidationReportTable";
import { ValidationSummaryCard } from "../validation/ValidationSummaryCard";

export function ValidationStep(): JSX.Element {
  const { setupJobId, setStep } = useWizardStore();
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  if (!setupJobId) {
    return (
      <div>
        <h2>Шаг 7. Валидация metadata</h2>
        <div className="banner banner-warning">
          Сначала создайте setup_job на шаге 1.
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2>Шаг 7. Валидация metadata</h2>
      <p className="text-muted">
        Детерминированная проверка metadata всех approved карточек: required
        fields, ontology, references, uniqueness. Карточки в FAILED возвращаются
        в SETUP-06 review_required.
      </p>

      <ValidationSummaryCard setupJobId={setupJobId} />
      <ValidationReportTable
        setupJobId={setupJobId}
        onSelect={(docId) => setSelectedDocId(docId)}
      />

      <div className="btn-row" style={{ marginTop: 16 }}>
        <button
          className="btn btn-secondary"
          onClick={() => setStep("chunking")}
          data-testid="continue-to-chunking"
        >
          Далее → Chunking
        </button>
      </div>

      {selectedDocId && (
        <p className="text-muted">
          Selected: <code>{selectedDocId}</code>
        </p>
      )}
    </div>
  );
}
