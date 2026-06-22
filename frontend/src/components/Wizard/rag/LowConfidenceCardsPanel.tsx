import { useQuery } from "@tanstack/react-query";
import { listRAGCards } from "../../../api/rag_cards";

interface Props {
  setupJobId: string;
  onSelect: (docId: string) => void;
}

export function LowConfidenceCardsPanel({
  setupJobId,
  onSelect,
}: Props): JSX.Element | null {
  const query = useQuery({
    queryKey: ["ragCardList", setupJobId, "low-confidence"],
    queryFn: () =>
      listRAGCards(setupJobId, {
        confidenceLevel: "low",
        pageSize: 50,
      }),
    enabled: !!setupJobId,
  });

  const items = query.data?.items ?? [];
  if (query.isLoading) return null;
  if (items.length === 0) return null;

  return (
    <div
      className="banner banner-warning"
      style={{ marginTop: 24, padding: 12 }}
      data-testid="low-confidence-panel"
    >
      <h3 style={{ marginTop: 0 }}>
        ⚠ Low-confidence карточки ({items.length})
      </h3>
      <p className="text-muted">
        Эти карточки требуют ручной проверки перед публикацией KB.
      </p>
      <ul style={{ marginBottom: 0 }}>
        {items.slice(0, 10).map((c) => (
          <li key={`${c.doc_id}.${c.card_version}`}>
            <button
              className="link"
              onClick={() => onSelect(c.doc_id)}
              data-testid={`low-conf-${c.doc_id}`}
              style={{
                background: "none",
                border: "none",
                color: "var(--link, #06f)",
                cursor: "pointer",
                padding: 0,
              }}
            >
              <code>{c.doc_id}</code>
            </button>
            {" — "}
            {c.title}
            {c.review_required_reason && (
              <> · <em>{c.review_required_reason}</em></>
            )}
          </li>
        ))}
        {items.length > 10 && (
          <li className="text-muted">… ещё {items.length - 10}</li>
        )}
      </ul>
    </div>
  );
}
