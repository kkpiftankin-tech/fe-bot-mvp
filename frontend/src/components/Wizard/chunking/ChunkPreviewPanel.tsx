import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getChunkManifest, runChunking } from "../../../api/chunking";

interface Props {
  setupJobId: string;
}

export function ChunkPreviewPanel({ setupJobId }: Props): JSX.Element {
  const qc = useQueryClient();
  const manifest = useQuery({
    queryKey: ["chunkManifest", setupJobId],
    queryFn: () => getChunkManifest(setupJobId),
    enabled: !!setupJobId,
    // 404 — ОК (значит batch не запускали), не показываем как ошибку
    retry: false,
  });

  const runMut = useMutation({
    mutationFn: () => runChunking(setupJobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chunkManifest", setupJobId] });
    },
  });

  const m = manifest.data;
  const noManifestYet =
    manifest.isError && (manifest.error as { status?: number })?.status === 404;

  return (
    <div
      data-testid="chunk-preview-panel"
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
        <h3 style={{ margin: 0 }}>Chunking</h3>
        <button
          className="btn"
          onClick={() => runMut.mutate()}
          disabled={runMut.isPending}
          data-testid="run-chunking"
        >
          {runMut.isPending ? "Запускаем…" : "Сгенерировать chunks"}
        </button>
      </div>

      {manifest.isLoading && <p>Загрузка manifest…</p>}
      {noManifestYet && (
        <p className="text-muted" data-testid="no-manifest">
          Manifest пока не создан. Запустите chunking.
        </p>
      )}

      {m && (
        <div style={{ marginTop: 12 }}>
          <p>
            <strong>{m.total_chunks}</strong> chunks из{" "}
            <strong>{Object.values(m.by_type).reduce((a, b) => a + b, 0) > 0
              ? new Set(m.chunks.map((c) => c.doc_id)).size
              : 0}</strong>{" "}
            карточек
          </p>
          <ul>
            {Object.entries(m.by_type).map(([type, count]) => (
              <li key={type}>
                <code>{type}</code>: {count}
              </li>
            ))}
          </ul>
          <p className="text-muted">
            Manifest: <code>{m.manifest_id}</code> · created{" "}
            {new Date(m.created_at).toLocaleString()}
          </p>
        </div>
      )}

      {runMut.isError && (
        <div className="banner banner-error" style={{ marginTop: 8 }}>
          {runMut.error instanceof Error ? runMut.error.message : "Ошибка"}
        </div>
      )}
    </div>
  );
}
