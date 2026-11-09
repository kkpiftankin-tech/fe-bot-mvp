import { useMutation } from "@tanstack/react-query";
import { reindexCards } from "../../../api/setup";

interface Props {
  setupJobId: string;
}

/**
 * SETUP-08 gap-fix: пошаговый мастер чанкует карточки (ChunkPreviewPanel),
 * но раньше нигде не эмбеддил и не индексировал их в векторную БД — это
 * умел только legacy-пайплайн (Шаг "Быстрый запуск", теперь убран из
 * мастера). Без этой панели retrieval-tests/publish работали бы по факту
 * с пустым индексом. Использует уже существующий backend endpoint
 * POST /reindex (T-S01-034), который строит indexed-версию из approved
 * карточек независимо от legacy pipeline.
 */
export function IndexingPanel({ setupJobId }: Props): JSX.Element {
  const indexMut = useMutation({
    mutationFn: () => reindexCards(setupJobId),
  });

  const result = indexMut.data;

  return (
    <div
      data-testid="indexing-panel"
      className="card"
      style={{
        border: "1px solid #ddd",
        borderRadius: 4,
        padding: 16,
        marginBottom: 16,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h3 style={{ margin: 0 }}>Эмбеддинг + индексация</h3>
        <button
          className="btn"
          onClick={() => indexMut.mutate()}
          disabled={indexMut.isPending}
          data-testid="run-indexing"
        >
          {indexMut.isPending ? "Индексируем…" : "Индексировать"}
        </button>
      </div>
      <p className="text-muted" style={{ marginTop: 8 }}>
        Строит эмбеддинги chunk-ов approved карточек и загружает их в
        векторную БД под новым index_version. Без этого шага
        retrieval-tests и publish увидят пустой индекс.
      </p>

      {result && (
        <div style={{ marginTop: 12 }} data-testid="indexing-result">
          <p>
            Проиндексировано <strong>{result.chunks_indexed}</strong> из{" "}
            <strong>{result.chunks_total}</strong> chunk-ов ·{" "}
            index_version <code>{result.index_version}</code>
          </p>
          {result.chunks_failed > 0 && (
            <p className="text-muted">Ошибок: {result.chunks_failed}</p>
          )}
          {result.errors.length > 0 && (
            <ul>
              {result.errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {indexMut.isError && (
        <div className="banner banner-error" style={{ marginTop: 8 }}>
          {indexMut.error instanceof Error
            ? indexMut.error.message
            : "Ошибка"}
        </div>
      )}
    </div>
  );
}
