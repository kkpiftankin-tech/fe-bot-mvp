import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  getRAGCard,
  getRAGCardPreview,
  regenerateRAGCard,
} from "../../../api/rag_cards";

type Tab = "metadata" | "body" | "source" | "versions" | "actions";

interface Props {
  setupJobId: string;
  docId: string;
  onClose: () => void;
}

export function RAGCardPreviewDrawer({
  setupJobId,
  docId,
  onClose,
}: Props): JSX.Element {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("metadata");
  const [selectedVersion, setSelectedVersion] = useState<string | undefined>(
    undefined,
  );
  const [regenReason, setRegenReason] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);

  const detailsQuery = useQuery({
    queryKey: ["ragCardDetails", setupJobId, docId, selectedVersion],
    queryFn: () => getRAGCard(setupJobId, docId, selectedVersion),
    enabled: !!setupJobId && !!docId,
  });

  const previewQuery = useQuery({
    queryKey: ["ragCardPreview", setupJobId, docId, selectedVersion],
    queryFn: () => getRAGCardPreview(setupJobId, docId, selectedVersion),
    enabled: !!setupJobId && !!docId,
  });

  const regenMut = useMutation({
    mutationFn: () => {
      if (!regenReason.trim()) throw new Error("Укажите причину регенерации");
      return regenerateRAGCard(setupJobId, docId, { reason: regenReason });
    },
    onSuccess: (resp) => {
      setActionError(null);
      setRegenReason("");
      setSelectedVersion(resp.new_card_version);
      qc.invalidateQueries({ queryKey: ["ragCardDetails", setupJobId, docId] });
      qc.invalidateQueries({ queryKey: ["ragCardPreview", setupJobId, docId] });
      qc.invalidateQueries({ queryKey: ["ragCardList", setupJobId] });
    },
    onError: (err: Error) => setActionError(err.message),
  });

  const details = detailsQuery.data;
  const preview = previewQuery.data;

  return (
    <div
      role="dialog"
      aria-label={`Просмотр карточки ${docId}`}
      data-testid="rag-card-preview-drawer"
      className="drawer"
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        height: "100vh",
        width: "min(720px, 100vw)",
        background: "var(--bg, #fff)",
        borderLeft: "1px solid #ccc",
        boxShadow: "-4px 0 16px rgba(0,0,0,.15)",
        overflowY: "auto",
        padding: 16,
        zIndex: 1000,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3 style={{ margin: 0 }}>
          {details?.title ?? docId}{" "}
          <small className="text-muted">v{details?.card_version ?? "—"}</small>
        </h3>
        <button
          className="btn btn-secondary"
          onClick={onClose}
          data-testid="close-preview"
        >
          ✕ Закрыть
        </button>
      </div>

      {details && (
        <p className="text-muted" style={{ marginTop: 4 }}>
          <code>{details.doc_id}</code> · {details.doc_type} · {details.status}
          {details.confidence_level && ` · confidence: ${details.confidence_level}`}
          {details.review_required_reason && (
            <>
              {" · "}
              <span className="banner banner-warning" style={{ padding: "2px 6px" }}>
                {details.review_required_reason}
              </span>
            </>
          )}
        </p>
      )}

      {details && (() => {
        // Позиция в структуре исходного документа (T-S05 UX fix): без
        // этого нет способа проверить, что карточка соответствует своему
        // месту в документе — виден только opaque source_section_id.
        const headingPath = details.front_matter.source_heading_path;
        const sectionTitle = details.front_matter.source_section_title;
        if (!Array.isArray(headingPath) && !sectionTitle) return null;
        const pathParts = [
          ...(Array.isArray(headingPath) ? headingPath.map(String) : []),
        ];
        return (
          <p
            data-testid="source-structure-summary"
            style={{
              marginTop: 4,
              padding: "6px 10px",
              background: "#eef6ff",
              borderRadius: 4,
              fontSize: 13,
            }}
          >
            📍 Структура документа:{" "}
            {pathParts.length > 0 ? (
              <>
                {pathParts.join(" → ")}
                {sectionTitle ? ` → "${String(sectionTitle)}"` : ""}
              </>
            ) : sectionTitle ? (
              `"${String(sectionTitle)}" (верхний уровень)`
            ) : (
              "—"
            )}
          </p>
        );
      })()}

      <nav role="tablist" className="btn-row" style={{ marginTop: 12 }}>
        {(
          [
            ["metadata", "Metadata"],
            ["body", "Body"],
            ["source", "Source trace"],
            ["versions", "Versions"],
            ["actions", "Actions"],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            className={`btn ${tab === id ? "" : "btn-secondary"}`}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            data-testid={`tab-${id}`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div style={{ marginTop: 16 }}>
        {tab === "metadata" && details && (
          <pre
            data-testid="metadata-pane"
            style={{
              background: "#f5f5f5",
              padding: 12,
              borderRadius: 4,
              overflow: "auto",
            }}
          >
            {JSON.stringify(details.front_matter, null, 2)}
          </pre>
        )}

        {tab === "body" && details && (
          <pre
            data-testid="body-pane"
            style={{
              background: "#f5f5f5",
              padding: 12,
              borderRadius: 4,
              whiteSpace: "pre-wrap",
              overflow: "auto",
            }}
          >
            {details.body_markdown}
          </pre>
        )}

        {tab === "source" && preview && (
          <div data-testid="source-pane">
            {preview.source_trace.length === 0 ? (
              <p className="text-muted">Нет связей источника.</p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>relation</th>
                    <th>source_document_id</th>
                    <th>source_section_id</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.source_trace.map((link) => (
                    <tr key={link.source_link_id}>
                      <td>{link.relation_type}</td>
                      <td>
                        <code>{link.source_document_id}</code>
                      </td>
                      <td>
                        <code>{link.source_section_id}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {tab === "versions" && details && (
          <div data-testid="versions-pane">
            <p className="text-muted">
              Доступные версии: {details.available_versions.length}
            </p>
            <ul>
              {details.available_versions.map((v) => (
                <li key={v}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => setSelectedVersion(v)}
                    aria-current={v === details.card_version}
                    data-testid={`version-${v}`}
                  >
                    {v} {v === details.card_version && "(текущая)"}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {tab === "actions" && (
          <div data-testid="actions-pane">
            <h4>Регенерация карточки</h4>
            <textarea
              value={regenReason}
              onChange={(e) => setRegenReason(e.target.value)}
              placeholder="Причина регенерации (обязательно)"
              rows={3}
              style={{ width: "100%" }}
              data-testid="regen-reason"
            />
            <div className="btn-row" style={{ marginTop: 8 }}>
              <button
                className="btn"
                onClick={() => regenMut.mutate()}
                disabled={regenMut.isPending || !regenReason.trim()}
                data-testid="regenerate-card"
              >
                {regenMut.isPending ? "Регенерируем…" : "Регенерировать"}
              </button>
            </div>
            {actionError && (
              <div className="banner banner-error" style={{ marginTop: 8 }}>
                {actionError}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
