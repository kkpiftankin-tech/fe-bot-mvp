import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listRAGCards, reviewRAGCard } from "../../../api/setup";
import {
  ApiError,
  type RAGCardSummary,
  type ReviewDecision,
} from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";

function badgeClass(status: string): string {
  if (status === "review_required") return "badge badge-review";
  if (status === "approved" || status === "metadata_validated")
    return "badge badge-approved";
  if (status === "deprecated") return "badge badge-deprecated";
  if (status === "published") return "badge badge-published";
  return "badge";
}

export function ReviewCardsStep(): JSX.Element {
  const { setupJobId, setStep } = useWizardStore();
  const qc = useQueryClient();
  const [filterStatus, setFilterStatus] = useState<string>("review_required");
  const [openCardId, setOpenCardId] = useState<string | null>(null);

  const cardsQuery = useQuery({
    queryKey: ["cards", setupJobId, filterStatus],
    queryFn: () => {
      if (!setupJobId) throw new Error("no setup_job_id");
      return listRAGCards(setupJobId, {
        cardStatus: filterStatus || undefined,
        includeBody: true,
      });
    },
    enabled: !!setupJobId,
  });

  const reviewMutation = useMutation({
    mutationFn: async (vars: {
      docId: string;
      decision: ReviewDecision;
      comment?: string;
      title?: string;
      body?: string;
    }) => {
      if (!setupJobId) throw new Error("no setup_job_id");
      return reviewRAGCard(setupJobId, vars.docId, {
        decision: vars.decision,
        comment: vars.comment,
        updated_title: vars.title,
        updated_body_markdown: vars.body,
      });
    },
    onSuccess: async () => {
      setOpenCardId(null);
      await qc.invalidateQueries({ queryKey: ["cards", setupJobId] });
    },
  });

  const cards = cardsQuery.data?.cards ?? [];

  return (
    <div>
      <h2>Шаг 4. Проверить карточки</h2>
      <p className="text-muted">
        Карточки в статусе <code>review_required</code> требуют HITL.
        <br />
        Approve → одобрить · Reject → удалить · Edit → новая версия · Regenerate
        → вернуть в draft.
      </p>

      <div className="row" style={{ marginBottom: 12 }}>
        <label>
          Фильтр статус:{" "}
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            data-testid="status-filter"
          >
            <option value="">Все</option>
            <option value="review_required">review_required</option>
            <option value="approved">approved</option>
            <option value="metadata_validated">metadata_validated</option>
            <option value="published">published</option>
            <option value="deprecated">deprecated</option>
          </select>
        </label>
        <span className="text-muted">Найдено: {cards.length}</span>
        <button
          className="btn btn-secondary"
          onClick={() => setStep("tests")}
          style={{ marginLeft: "auto" }}
          data-testid="continue-to-tests"
        >
          К retrieval-tests →
        </button>
      </div>

      {cardsQuery.isLoading ? (
        <p className="text-muted">Загружаем карточки…</p>
      ) : cards.length === 0 ? (
        <p className="text-muted" data-testid="no-cards">
          Нет карточек, соответствующих фильтру.
        </p>
      ) : (
        <ul className="card-list" data-testid="card-list">
          {cards.map((card) => (
            <li key={card.doc_id} className="card-item">
              <CardRow
                card={card}
                isOpen={openCardId === card.doc_id}
                onToggle={() =>
                  setOpenCardId(openCardId === card.doc_id ? null : card.doc_id)
                }
                onAction={(decision, payload) =>
                  reviewMutation.mutate({
                    docId: card.doc_id,
                    decision,
                    comment: payload.comment,
                    title: payload.title,
                    body: payload.body,
                  })
                }
                isPending={reviewMutation.isPending}
              />
            </li>
          ))}
        </ul>
      )}

      {reviewMutation.error && (
        <div
          className="banner banner-error"
          style={{ marginTop: 16 }}
          data-testid="review-error"
        >
          {reviewMutation.error instanceof ApiError
            ? reviewMutation.error.message
            : "Ошибка review"}
        </div>
      )}
    </div>
  );
}

interface CardRowProps {
  card: RAGCardSummary;
  isOpen: boolean;
  onToggle: () => void;
  onAction: (
    decision: ReviewDecision,
    payload: { comment?: string; title?: string; body?: string },
  ) => void;
  isPending: boolean;
}

function CardRow({
  card,
  isOpen,
  onToggle,
  onAction,
  isPending,
}: CardRowProps): JSX.Element {
  const [comment, setComment] = useState("");
  const [editTitle, setEditTitle] = useState(card.title);
  const [editBody, setEditBody] = useState(card.body_markdown ?? "");

  return (
    <>
      <header>
        <div>
          <strong>{card.title}</strong>{" "}
          <span className={badgeClass(card.status)} data-testid={`status-${card.doc_id}`}>
            {card.status}
          </span>
          <div className="meta">
            {card.doc_id} · {card.doc_type} · v{card.version}
            {card.confidence_level && <> · conf={card.confidence_level}</>}
          </div>
        </div>
        <button
          className="btn btn-secondary"
          onClick={onToggle}
          data-testid={`toggle-${card.doc_id}`}
        >
          {isOpen ? "Свернуть" : "Развернуть"}
        </button>
      </header>

      {isOpen && (
        <div style={{ marginTop: 12 }}>
          {card.body_markdown && (
            <pre
              style={{
                background: "#f3f4f6",
                padding: 12,
                borderRadius: 8,
                overflow: "auto",
                maxHeight: 240,
                fontSize: 12,
              }}
            >
              {card.body_markdown}
            </pre>
          )}
          <div className="form-group">
            <label>Комментарий (опционально)</label>
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              data-testid={`comment-${card.doc_id}`}
            />
          </div>
          <div className="btn-row">
            <button
              className="btn"
              disabled={isPending}
              onClick={() => onAction("approve", { comment })}
              data-testid={`approve-${card.doc_id}`}
            >
              Approve
            </button>
            <button
              className="btn btn-danger"
              disabled={isPending}
              onClick={() => onAction("reject", { comment })}
              data-testid={`reject-${card.doc_id}`}
            >
              Reject
            </button>
            <button
              className="btn btn-secondary"
              disabled={isPending}
              onClick={() => onAction("regenerate", { comment })}
              data-testid={`regenerate-${card.doc_id}`}
            >
              Regenerate
            </button>
          </div>

          <details style={{ marginTop: 16 }}>
            <summary>Edit (новая версия)</summary>
            <div className="form-group">
              <label>Новый title</label>
              <input
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>Новый body markdown</label>
              <textarea
                value={editBody}
                onChange={(e) => setEditBody(e.target.value)}
                rows={6}
              />
            </div>
            <div className="btn-row">
              <button
                className="btn"
                disabled={
                  isPending ||
                  (editTitle === card.title &&
                    editBody === (card.body_markdown ?? ""))
                }
                onClick={() =>
                  onAction("edit", {
                    comment,
                    title: editTitle !== card.title ? editTitle : undefined,
                    body:
                      editBody !== (card.body_markdown ?? "")
                        ? editBody
                        : undefined,
                  })
                }
                data-testid={`edit-${card.doc_id}`}
              >
                Применить edit
              </button>
            </div>
          </details>
        </div>
      )}
    </>
  );
}
