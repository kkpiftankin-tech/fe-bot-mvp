import { useWizardStore } from "../../../store/wizardStore";
import { ChunkPreviewPanel } from "../chunking/ChunkPreviewPanel";
import { IndexingPanel } from "../chunking/IndexingPanel";

export function ChunkingStep(): JSX.Element {
  const { setupJobId, setStep } = useWizardStore();

  if (!setupJobId) {
    return (
      <div>
        <h2>Шаг 7. Chunking + индексация</h2>
        <div className="banner banner-warning">
          Сначала создайте setup_job на шаге 1.
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2>Шаг 7. Chunking + индексация</h2>
      <p className="text-muted">
        Превращение METADATA_VALIDATED карточек в логические chunks
        (summary + definition + metadata_summary). Каждая карточка даёт 3 chunk-а
        со стабильным chunk_id и оптимизированным embedding_text. После
        chunking'а нужно отдельно запустить индексацию — она строит эмбеддинги
        и загружает chunks в векторную БД, без этого retrieval-tests не найдут
        ничего.
      </p>

      <ChunkPreviewPanel setupJobId={setupJobId} />
      <IndexingPanel setupJobId={setupJobId} />

      <div className="btn-row" style={{ marginTop: 16 }}>
        <button
          className="btn btn-secondary"
          onClick={() => setStep("tests")}
          data-testid="continue-to-tests-from-chunking"
        >
          Далее → Retrieval tests
        </button>
      </div>
    </div>
  );
}
