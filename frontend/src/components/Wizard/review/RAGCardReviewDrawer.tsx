import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  editReviewCard,
  getReviewCard,
  getReviewLog,
  getReviewVersions,
  regenerateReviewCard,
  reviewCard,
} from "../../../api/review";
import { LLMProgressBar } from "../../observability/LLMProgressBar";

type Tab = "overview" | "metadata" | "body" | "source" | "validation" | "versions" | "log";

const REJECT_REASONS = [
  "duplicate",
  "wrong_doc_type",
  "incorrect_content",
  "irrelevant",
  "hallucination",
  "source_mismatch",
  "other",
];

interface Props {
  setupJobId: string;
  docId: string;
  onClose: () => void;
}

export function RAGCardReviewDrawer({
  setupJobId,
  docId,
  onClose,
}: Props): JSX.Element {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [actionError, setActionError] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState<string>("duplicate");
  const [rejectComment, setRejectComment] = useState<string>("");
  const [regenReason, setRegenReason] = useState<string>("low_quality");
  const [editBody, setEditBody] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState<string | null>(null);

  const details = useQuery({
    queryKey: ["reviewCardDetails", setupJobId, docId],
    queryFn: () => getReviewCard(setupJobId, docId),
    enabled: !!setupJobId && !!docId,
  });
  const versions = useQuery({
    queryKey: ["reviewCardVersions", setupJobId, docId],
    queryFn: () => getReviewVersions(setupJobId, docId),
    enabled: tab === "versions",
  });
  const log = useQuery({
    queryKey: ["reviewCardLog", setupJobId, docId],
    queryFn: () => getReviewLog(setupJobId, docId),
    enabled: tab === "log",
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["reviewCards", setupJobId] });
    qc.invalidateQueries({ queryKey: ["reviewCardDetails", setupJobId, docId] });
    qc.invalidateQueries({ queryKey: ["reviewCardVersions", setupJobId, docId] });
    qc.invalidateQueries({ queryKey: ["reviewCardLog", setupJobId, docId] });
  };

  const approveMut = useMutation({
    mutationFn: () =>
      reviewCard(setupJobId, docId, { decision: "approve" }),
    onSuccess: () => {
      setActionError(null);
      invalidate();
    },
    onError: (err: Error) => setActionError(err.message),
  });

  const rejectMut = useMutation({
    mutationFn: () => {
      if (!rejectReason.trim()) throw new Error("Укажите причину");
      return reviewCard(setupJobId, docId, {
        decision: "reject",
        reason: rejectReason,
        comment: rejectComment || null,
      });
    },
    onSuccess: () => {
      setActionError(null);
      invalidate();
    },
    onError: (err: Error) => setActionError(err.message),
  });

  const regenMut = useMutation({
    mutationFn: () => {
      if (!regenReason.trim()) throw new Error("Укажите причину");
      return regenerateReviewCard(setupJobId, docId, {
        reason: regenReason,
      });
    },
    onSuccess: () => {
      setActionError(null);
      invalidate();
    },
    onError: (err: Error) => setActionError(err.message),
  });

  const editMut = useMutation({
    mutationFn: () => {
      const d = details.data;
      if (!d) throw new Error("Карточка не загружена");
      const metadataPatch =
        editTitle !== null && editTitle !== d.title ? { title: editTitle } : null;
      const bodyChanged =
        editBody !== null && editBody !== d.body_markdown ? editBody : null;
      if (!metadataPatch && bodyChanged === null) {
        throw new Error("Нет изменений");
      }
      return editReviewCard(setupJobId, docId, {
        expected_version: d.card_version,
        metadata_patch: metadataPatch,
        body_markdown: bodyChanged,
        change_reason: "manual edit",
      });
    },
    onSuccess: () => {
      setActionError(null);
      setEditBody(null);
      setEditTitle(null);
      invalidate();
    },
    onError: (err: Error) => setActionError(err.message),
  });

  const d = details.data;
  const tabs: [Tab, string][] = [
    ["overview", "Overview"],
    ["metadata", "Metadata"],
    ["body", "Body"],
    ["source", "Source"],
    ["validation", "Validation"],
    ["versions", "Versions"],
    ["log", "Log"],
  ];

  return (
    <div
      role="dialog"
      aria-label={`Review ${docId}`}
      data-testid="review-drawer"
      className="drawer"
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        height: "100vh",
        width: "min(820px, 100vw)",
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
          {d?.title ?? docId} <small className="text-muted">v{d?.card_version ?? "—"}</small>
        </h3>
        <button
          className="btn btn-secondary"
          onClick={onClose}
          data-testid="close-drawer"
        >
          ✕ Закрыть
        </button>
      </div>

      {d && (
        <p className="text-muted" style={{ marginTop: 4 }}>
          <code>{d.doc_id}</code> · {d.doc_type} · {d.status}
          {d.confidence_level && ` · confidence: ${d.confidence_level}`}
        </p>
      )}

      {d && (() => {
        // Позиция в структуре исходного документа: без этого нет способа
        // проверить в review-UI, что карточка соответствует своему месту
        // в документе — виден только opaque source_section_id.
        const headingPath = d.metadata.source_heading_path;
        const sectionTitle = d.metadata.source_section_title;
        if (!Array.isArray(headingPath) && !sectionTitle) return null;
        const pathParts = Array.isArray(headingPath) ? headingPath.map(String) : [];
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
        {tabs.map(([id, label]) => (
          <button
            key={id}
            className={`btn ${tab === id ? "" : "btn-secondary"}`}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            data-testid={`drawer-tab-${id}`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div style={{ marginTop: 16 }}>
        {tab === "overview" && d && (
          <div data-testid="pane-overview">
            <p>
              <strong>Status:</strong> {d.status}
            </p>
            <p>
              <strong>Confidence:</strong> {d.confidence_level ?? "—"}
            </p>
            <p>
              <strong>Permissions:</strong>{" "}
              {Object.entries(d.permissions)
                .filter(([, v]) => v)
                .map(([k]) => k.replace("can_", ""))
                .join(", ")}
            </p>
            <h4>Действия</h4>
            <div className="btn-row">
              <button
                className="btn"
                onClick={() => approveMut.mutate()}
                disabled={!d.permissions.can_approve || approveMut.isPending}
                data-testid="approve-btn"
              >
                {approveMut.isPending ? "Принимаем…" : "Принять"}
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => setTab("validation")}
                data-testid="reject-btn"
              >
                Отклонить
              </button>
            </div>
            {actionError && (
              <div className="banner banner-error" style={{ marginTop: 8 }}>
                {actionError}
              </div>
            )}
          </div>
        )}

        {tab === "metadata" && d && (
          <div data-testid="pane-metadata">
            <h4>Title</h4>
            <input
              type="text"
              defaultValue={d.title}
              onChange={(e) => setEditTitle(e.target.value)}
              style={{ width: "100%" }}
              data-testid="edit-title"
            />
            <h4 style={{ marginTop: 16 }}>Metadata (JSON)</h4>
            <pre
              style={{
                background: "#f5f5f5",
                padding: 12,
                borderRadius: 4,
                overflow: "auto",
              }}
            >
              {JSON.stringify(d.metadata, null, 2)}
            </pre>
            <div className="btn-row" style={{ marginTop: 8 }}>
              <button
                className="btn"
                onClick={() => editMut.mutate()}
                disabled={editMut.isPending}
                data-testid="save-edit"
              >
                Сохранить новую версию
              </button>
            </div>
          </div>
        )}

        {tab === "body" && d && (
          <div data-testid="pane-body">
            <textarea
              defaultValue={d.body_markdown}
              onChange={(e) => setEditBody(e.target.value)}
              rows={20}
              style={{ width: "100%", fontFamily: "monospace" }}
              data-testid="edit-body"
            />
            <div className="btn-row" style={{ marginTop: 8 }}>
              <button
                className="btn"
                onClick={() => editMut.mutate()}
                disabled={editMut.isPending}
                data-testid="save-body"
              >
                Сохранить новую версию
              </button>
            </div>
          </div>
        )}

        {tab === "source" && d && (
          <pre
            data-testid="pane-source"
            style={{ background: "#f5f5f5", padding: 12, borderRadius: 4 }}
          >
            {JSON.stringify(d.source_trace, null, 2)}
          </pre>
        )}

        {tab === "validation" && d && (
          <div data-testid="pane-validation">
            {d.validation.critical_errors.length > 0 && (
              <div className="banner banner-error">
                <strong>Critical errors:</strong>
                <ul>
                  {d.validation.critical_errors.map((e) => (
                    <li key={e.code}>
                      <code>{e.code}</code> — {e.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {d.validation.warnings.length > 0 && (
              <div className="banner banner-warning">
                <strong>Warnings:</strong>
                <ul>
                  {d.validation.warnings.map((w) => (
                    <li key={w.code}>
                      <code>{w.code}</code> — {w.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <h4 style={{ marginTop: 16 }}>Отклонить</h4>
            <label>
              Причина:{" "}
              <select
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                data-testid="reject-reason"
              >
                {REJECT_REASONS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
            <textarea
              placeholder="Комментарий (опционально)"
              value={rejectComment}
              onChange={(e) => setRejectComment(e.target.value)}
              style={{ width: "100%", marginTop: 8 }}
              rows={3}
            />
            <div className="btn-row" style={{ marginTop: 8 }}>
              <button
                className="btn"
                onClick={() => rejectMut.mutate()}
                disabled={rejectMut.isPending}
                data-testid="confirm-reject"
              >
                Отклонить
              </button>
            </div>

            <h4 style={{ marginTop: 16 }}>Регенерировать</h4>
            <input
              type="text"
              value={regenReason}
              onChange={(e) => setRegenReason(e.target.value)}
              style={{ width: "100%" }}
              data-testid="regen-reason"
            />
            <div className="btn-row" style={{ marginTop: 8 }}>
              <button
                className="btn"
                onClick={() => regenMut.mutate()}
                disabled={regenMut.isPending}
                data-testid="confirm-regenerate"
              >
                Запросить регенерацию
              </button>
            </div>
            <LLMProgressBar
              active={regenMut.isPending}
              model="llama3.2"
              label="Регенерация карточки — LLM"
            />
          </div>
        )}

        {tab === "versions" && (
          <div data-testid="pane-versions">
            {versions.isLoading && <p>Загрузка…</p>}
            {versions.data && versions.data.versions.length === 0 && (
              <p className="text-muted">Версий нет.</p>
            )}
            {versions.data && versions.data.versions.length > 0 && (
              <ul>
                {versions.data.versions.map((v) => (
                  <li key={v.card_version}>
                    <strong>{v.card_version}</strong>
                    {v.is_current && " (текущая)"} — {v.status} ·{" "}
                    {new Date(v.created_at).toLocaleString()}
                    {v.change_reason && ` · ${v.change_reason}`}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {tab === "log" && (
          <div data-testid="pane-log">
            {log.isLoading && <p>Загрузка…</p>}
            {log.data && log.data.items.length === 0 && (
              <p className="text-muted">Журнал пуст.</p>
            )}
            {log.data && log.data.items.length > 0 && (
              <ul>
                {log.data.items.map((it) => (
                  <li key={it.review_log_id}>
                    <strong>{it.event_type}</strong> · {it.actor_id} ({it.actor_role}) ·{" "}
                    {new Date(it.created_at).toLocaleString()}
                    <br />
                    <span className="text-muted">{it.message}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
