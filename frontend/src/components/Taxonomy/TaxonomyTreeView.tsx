// SETUP-12 / T-S12-070: дерево активной taxonomy с usage_count.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getActiveTaxonomyTree } from "../../api/taxonomy";
import type { TaxonomyTreeNodeDTO } from "../../api/taxonomy";

export function TaxonomyTreeView(): JSX.Element {
  const query = useQuery({
    queryKey: ["taxonomyTree", "active"],
    queryFn: getActiveTaxonomyTree,
  });

  if (query.isLoading) {
    return <p className="text-muted">Загрузка таксономии…</p>;
  }
  if (query.error) {
    const msg =
      query.error instanceof Error ? query.error.message : "Ошибка";
    return (
      <div className="banner banner-error" data-testid="taxonomy-error">
        {msg}
      </div>
    );
  }
  if (!query.data) {
    return (
      <p className="text-muted" data-testid="taxonomy-empty">
        Таксономия не загружена.
      </p>
    );
  }

  const { version, roots, total_classes, auto_created_count } = query.data;

  return (
    <div data-testid="taxonomy-tree">
      <h3>Иерархическая таксономия</h3>
      <div className="kv-grid" style={{ marginBottom: 12 }}>
        <div className="key">Активная версия</div>
        <div>
          <code>{version.version_id}</code>
          {version.description && (
            <span className="text-muted" style={{ marginLeft: 8 }}>
              {version.description}
            </span>
          )}
        </div>
        <div className="key">Всего классов</div>
        <div>{total_classes}</div>
        <div className="key">Авто-созданных</div>
        <div>{auto_created_count}</div>
        <div className="key">Корневых (L0)</div>
        <div>{roots.length} / 10</div>
      </div>

      {roots.length === 0 ? (
        <p className="text-muted" data-testid="taxonomy-empty-roots">
          Таксономия пуста — нет L0 классов в активной версии.
        </p>
      ) : (
        <ul className="tree" style={{ listStyle: "none", paddingLeft: 0 }}>
          {roots.map((root) => (
            <TreeNodeRow
              key={`${root.node.level}:${root.node.parent_path}:${root.node.bit_index}`}
              node={root}
              depth={0}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

interface TreeNodeRowProps {
  node: TaxonomyTreeNodeDTO;
  depth: number;
}

function TreeNodeRow({ node, depth }: TreeNodeRowProps): JSX.Element {
  const hasChildren = node.children.length > 0;
  const [expanded, setExpanded] = useState<boolean>(depth === 0);
  const padding = depth * 20;
  const slug = node.node.class_slug;
  return (
    <li>
      <div
        style={{
          paddingLeft: padding,
          display: "flex",
          gap: 8,
          alignItems: "center",
          padding: "4px 0",
        }}
        data-testid={`tax-node-${slug}`}
      >
        {hasChildren ? (
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: "0 8px", minWidth: 28 }}
            onClick={() => setExpanded((e) => !e)}
            data-testid={`tax-expand-${slug}`}
          >
            {expanded ? "▾" : "▸"}
          </button>
        ) : (
          <span style={{ display: "inline-block", width: 28 }} />
        )}
        <strong>{node.node.display_name_ru}</strong>
        <code style={{ color: "#666" }}>{slug}</code>
        <span className="text-muted" style={{ fontSize: 12 }}>
          L{node.node.level} · bit {node.node.bit_index}
        </span>
        {node.node.usage_count > 0 && (
          <span
            className="badge"
            style={{
              background: "#eef",
              padding: "1px 8px",
              borderRadius: 8,
              fontSize: 12,
            }}
            data-testid={`tax-usage-${slug}`}
          >
            uses: {node.node.usage_count}
          </span>
        )}
        {node.node.auto_created && (
          <span
            className="badge"
            style={{
              background: "#ffe8c2",
              padding: "1px 8px",
              borderRadius: 8,
              fontSize: 12,
            }}
          >
            auto
          </span>
        )}
        {node.node.doc_type_hint && (
          <span className="text-muted" style={{ fontSize: 11 }}>
            doc_type: <code>{node.node.doc_type_hint}</code>
          </span>
        )}
      </div>
      {hasChildren && expanded && (
        <ul style={{ listStyle: "none", paddingLeft: 0 }}>
          {node.children.map((child) => (
            <TreeNodeRow
              key={`${child.node.level}:${child.node.parent_path}:${child.node.bit_index}`}
              node={child}
              depth={depth + 1}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
