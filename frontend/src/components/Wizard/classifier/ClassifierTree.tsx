import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getClassifierNode } from "../../../api/classifier";
import type { ClassifierNodeDTO } from "../../../api/types";

interface TreeNodeProps {
  node: ClassifierNodeDTO;
  depth: number;
  selectedNodeId: string | null;
  onSelect: (nodeId: string) => void;
}

/**
 * SETUP-13 / ADR-HTC-09: одна строка дерева. Разворачивает своих детей
 * ПО МЕСТУ (аккордеон) — клик по строке не заменяет собой всю панель.
 *
 * Клик по всей строке одновременно выбирает узел (для панели
 * редактирования) И разворачивает/сворачивает его — так что
 * "подклассы не раскрываются" не может случиться из-за промаха мимо
 * маленькой стрелки: сработает клик в любом месте строки. Стрелка —
 * дополнительная явная подсказка, что у узла есть дети.
 *
 * Дети запрашиваются лениво тем же GET /tree/nodes/{id}, что и панель
 * редактирования — react-query дедуплицирует по ключу
 * ["classifierNode", id], так что разворачивание узла в дереве и его
 * выбор для редактирования не делают двойной запрос.
 */
function TreeNode({ node, depth, selectedNodeId, onSelect }: TreeNodeProps): JSX.Element {
  const [expanded, setExpanded] = useState(depth === 0);
  const childrenQuery = useQuery({
    queryKey: ["classifierNode", node.node_id],
    queryFn: () => getClassifierNode(node.node_id),
    enabled: expanded && !node.is_leaf,
  });

  const isSelected = node.node_id === selectedNodeId;

  function handleRowClick(): void {
    onSelect(node.node_id);
    if (!node.is_leaf) setExpanded((e) => !e);
  }

  return (
    <li>
      <button
        type="button"
        data-testid={`classifier-tree-node-${node.node_id}`}
        onClick={handleRowClick}
        style={{
          display: "flex",
          alignItems: "center",
          width: "100%",
          background: isSelected ? "#e8f0fe" : "transparent",
          border: "none",
          borderLeft: isSelected ? "3px solid #1a73e8" : "3px solid transparent",
          cursor: "pointer",
          padding: "5px 8px 5px 6px",
          paddingLeft: 6 + depth * 18,
          textAlign: "left",
          font: "inherit",
          borderRadius: 3,
        }}
      >
        <span
          aria-hidden="true"
          data-testid={`classifier-tree-toggle-${node.node_id}`}
          style={{
            display: "inline-block",
            width: 16,
            flexShrink: 0,
            color: "#888",
            fontSize: 11,
            transform: expanded ? "rotate(90deg)" : "none",
            transition: "transform 0.1s",
          }}
        >
          {!node.is_leaf ? "▶" : ""}
        </span>
        <span
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            fontWeight: isSelected ? 600 : 400,
          }}
        >
          {node.name}
        </span>
        {!node.is_leaf && (
          <span style={{ marginLeft: 6, color: "#999", fontSize: 12, flexShrink: 0 }}>
            {node.children_ids.length}
          </span>
        )}
      </button>

      {expanded && !node.is_leaf && (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {childrenQuery.isLoading && (
            <li
              className="text-muted"
              style={{ paddingLeft: 6 + (depth + 1) * 18, fontSize: 13, padding: "4px 0" }}
            >
              Загрузка…
            </li>
          )}
          {childrenQuery.error && (
            <li style={{ paddingLeft: 6 + (depth + 1) * 18 }}>
              <span className="banner banner-error" style={{ display: "inline-block" }}>
                Ошибка загрузки
              </span>
            </li>
          )}
          {childrenQuery.data?.children.map((child) => (
            <TreeNode
              key={child.node_id}
              node={child}
              depth={depth + 1}
              selectedNodeId={selectedNodeId}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

interface Props {
  root: ClassifierNodeDTO;
  selectedNodeId: string | null;
  onSelect: (nodeId: string) => void;
}

/** Дерево классов — раскрывается по месту (аккордеон), не заменяя панель редактирования. */
export function ClassifierTree({ root, selectedNodeId, onSelect }: Props): JSX.Element {
  return (
    <ul
      data-testid="classifier-tree"
      style={{ listStyle: "none", padding: 0, margin: 0 }}
    >
      <TreeNode node={root} depth={0} selectedNodeId={selectedNodeId} onSelect={onSelect} />
    </ul>
  );
}
