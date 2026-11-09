import { useState } from "react";
import { useWizardStore } from "../../../store/wizardStore";
import { RAGCardReviewDrawer } from "../review/RAGCardReviewDrawer";
import { RAGCardReviewTable } from "../review/RAGCardReviewTable";

export function ReviewCardsStep(): JSX.Element {
  const { setupJobId, setStep } = useWizardStore();
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  if (!setupJobId) {
    return (
      <div>
        <h2>Шаг 5. Проверить карточки</h2>
        <div className="banner banner-warning">
          Сначала создайте setup_job на шаге 1.
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2>Шаг 5. Проверить карточки</h2>
      <p className="text-muted">
        Human-in-the-loop review для RAG-карточек: фильтруйте по статусу/confidence,
        открывайте карточку, проверяйте metadata/body/source/validation. Действия:
        approve / reject (с причиной) / edit (создаёт новую версию) / regenerate.
        Approved карточки переходят в SETUP-07 metadata validation.
      </p>

      <div className="btn-row" style={{ marginBottom: 12 }}>
        <button
          className="btn btn-secondary"
          onClick={() => setStep("validation")}
          data-testid="continue-to-validation"
        >
          Далее →
        </button>
      </div>

      <RAGCardReviewTable
        setupJobId={setupJobId}
        onSelect={(docId) => setSelectedDocId(docId)}
      />

      {selectedDocId && (
        <RAGCardReviewDrawer
          setupJobId={setupJobId}
          docId={selectedDocId}
          onClose={() => setSelectedDocId(null)}
        />
      )}
    </div>
  );
}
