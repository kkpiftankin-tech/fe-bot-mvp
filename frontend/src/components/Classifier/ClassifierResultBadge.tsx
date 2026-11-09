// SETUP-13 / ADR-HTC-09: бэдж классификации секции по дереву
// классификаторов (заменяет legacy ClassificationBadge из
// components/Taxonomy — SETUP-12 bitmap-дерево, см. ADR-HTC-09).
//
// В отличие от SETUP-12, path уже содержит человекочитаемые name на
// каждом уровне — дополнительный запрос дерева не нужен.

import type { FragmentClassificationResult } from "../../api/types";

interface Props {
  result: FragmentClassificationResult | null | undefined;
}

const BADGE_COLORS = ["#dde9ff", "#dff5e2", "#fdf6c2", "#fde2e2", "#f0dcf7", "#ffe4cc"];

export function ClassifierResultBadge({ result }: Props): JSX.Element {
  if (!result) {
    return (
      <span
        className="text-muted"
        style={{ fontSize: 12 }}
        data-testid="classifier-result-badge-legacy"
      >
        rule-based (legacy)
      </span>
    );
  }

  if (result.path.length === 0) {
    return (
      <span
        className="badge"
        style={{
          background: "#fde2e2",
          color: "#a33",
          padding: "2px 8px",
          borderRadius: 8,
          fontSize: 12,
        }}
        data-testid="classifier-result-badge-unmatched"
      >
        не удалось отнести ни к одному классу
      </span>
    );
  }

  const overallConfidence = Math.min(...result.path.map((step) => step.confidence));

  return (
    <span
      style={{ display: "inline-flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}
      data-testid="classifier-result-badge"
      title={result.path.map((step) => `${step.name}: ${step.reason}`).join("\n")}
    >
      {result.path.map((step, idx) => (
        <span
          key={step.node_id}
          style={{ display: "inline-flex", gap: 4, alignItems: "center" }}
        >
          {idx > 0 && <span className="text-muted">›</span>}
          <span
            className="badge"
            style={{
              background: BADGE_COLORS[idx % BADGE_COLORS.length],
              padding: "2px 8px",
              borderRadius: 8,
              fontSize: 12,
            }}
          >
            {step.name}
          </span>
        </span>
      ))}
      <span className="text-muted" style={{ fontSize: 11 }}>
        ({overallConfidence.toFixed(2)})
      </span>
      {!result.reached_leaf && (
        <span
          className="text-muted"
          style={{ fontSize: 11 }}
          data-testid="classifier-result-badge-not-leaf"
        >
          — можно уточнить глубже
        </span>
      )}
    </span>
  );
}
