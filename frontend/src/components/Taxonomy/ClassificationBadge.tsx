// SETUP-12 / T-S12-071: бэдж классификации секции.
//
// Показывает taxonomy_path + индикаторы (auto-created bits, cascading-unknown).
// Принимает classification_state из ParsedSection и опционально tree (чтобы
// разрешить slug'и в display_name). Если state=null — отображает «rule-based».

import { useQuery } from "@tanstack/react-query";
import {
  getActiveTaxonomyTree,
  type ClassificationStateDTO,
  type TaxonomyTreeNodeDTO,
  type TaxonomyTreeResponse,
} from "../../api/taxonomy";

interface Props {
  state: ClassificationStateDTO | null | undefined;
}

export function ClassificationBadge({ state }: Props): JSX.Element {
  const treeQuery = useQuery({
    queryKey: ["taxonomyTree", "active"],
    queryFn: getActiveTaxonomyTree,
    // tree кешируется глобально — все badge'и шарят один запрос
    staleTime: 60_000,
  });

  if (!state) {
    return (
      <span
        className="text-muted"
        style={{ fontSize: 12 }}
        data-testid="classif-badge-legacy"
      >
        rule-based (legacy)
      </span>
    );
  }

  if (state.unknown_at_level === 0) {
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
        data-testid="classif-badge-unknown"
      >
        unknown (L0)
      </span>
    );
  }

  const tree = treeQuery.data;
  const path = resolveTaxonomyPath(state, tree);
  if (!path.length) {
    return (
      <span
        className="text-muted"
        style={{ fontSize: 12 }}
        data-testid="classif-badge-resolving"
      >
        классификация загружается…
      </span>
    );
  }

  const cascadingTag = state.unknown_at_level !== null;

  return (
    <span
      style={{ display: "inline-flex", gap: 4, alignItems: "center" }}
      data-testid="classif-badge"
    >
      {path.map((segment, idx) => (
        <span key={`${idx}-${segment.slug}`} style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
          {idx > 0 && <span className="text-muted">›</span>}
          <span
            className="badge"
            style={{
              background: badgeColor(idx),
              padding: "2px 8px",
              borderRadius: 8,
              fontSize: 12,
            }}
            title={segment.description}
          >
            {segment.display}
          </span>
        </span>
      ))}
      {cascadingTag && (
        <span
          className="text-muted"
          style={{ fontSize: 11, marginLeft: 4 }}
          data-testid="classif-cascading"
        >
          ↛ L{state.unknown_at_level}
        </span>
      )}
    </span>
  );
}

interface PathSegment {
  slug: string;
  display: string;
  description: string;
}

function resolveTaxonomyPath(
  state: ClassificationStateDTO,
  tree: TaxonomyTreeResponse | undefined,
): PathSegment[] {
  if (!tree || state.primary_l0_idx === null) {
    return [];
  }
  const l0Node = findChildByBitIndex(tree.roots, state.primary_l0_idx);
  if (!l0Node) return [];
  const out: PathSegment[] = [
    {
      slug: l0Node.node.class_slug,
      display: l0Node.node.display_name_ru,
      description: l0Node.node.description,
    },
  ];
  if (state.primary_l1_idx === null) {
    return out;
  }
  const l1Node = findChildByBitIndex(l0Node.children, state.primary_l1_idx);
  if (!l1Node) return out;
  out.push({
    slug: l1Node.node.class_slug,
    display: l1Node.node.display_name_ru,
    description: l1Node.node.description,
  });
  // L2: primary не выделяется в state — берём первый bit_index из L2 зоны
  const l2BitIndex = firstBitInLevel(state.classification_bitmap, 2);
  if (l2BitIndex === null) return out;
  const l2Node = findChildByBitIndex(l1Node.children, l2BitIndex);
  if (!l2Node) return out;
  out.push({
    slug: l2Node.node.class_slug,
    display: l2Node.node.display_name_ru,
    description: l2Node.node.description,
  });
  return out;
}

function findChildByBitIndex(
  candidates: TaxonomyTreeNodeDTO[],
  bitIndex: number,
): TaxonomyTreeNodeDTO | null {
  return candidates.find((c) => c.node.bit_index === bitIndex) ?? null;
}

function firstBitInLevel(bitmap: number, level: number): number | null {
  // level=0 → bits 0..9, level=1 → 10..19, level=2 → 20..29
  const offset = level * 10;
  for (let i = 0; i < 10; i++) {
    if ((bitmap & (1 << (offset + i))) !== 0) {
      return i;
    }
  }
  return null;
}

function badgeColor(idx: number): string {
  // L0=голубой, L1=зелёный, L2=жёлтый
  const colors = ["#dde9ff", "#dff5e2", "#fdf6c2"];
  return colors[idx] ?? "#eee";
}
