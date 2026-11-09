import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getClassifierTree } from "../../../api/classifier";
import { ClassifierNodePanel } from "../classifier/ClassifierNodePanel";
import { ClassifierTree } from "../classifier/ClassifierTree";

/**
 * SETUP-13 / ADR-HTC-09: библиотека классификаторов — просмотр и
 * редактирование дерева классов АСУ (906 узлов на реальном seed) и
 * промптов, которыми маленькая LLM определяет подкласс на каждом
 * уровне. Не привязана к конкретному setup_job (см. JOB_INDEPENDENT_STEPS
 * в wizardStore.ts) — это общий ресурс, который в будущем шаге будет
 * использоваться многоуровневым классификатором фрагментов документа
 * (пока не реализовано — вне текущего scope).
 *
 * Дерево слева раскрывается по месту (аккордеон) — клик по узлу не
 * заменяет весь экран, а только выбирает узел для панели редактирования
 * справа.
 */
export function ClassifierLibraryStep(): JSX.Element {
  const tree = useQuery({
    queryKey: ["classifierTree"],
    queryFn: getClassifierTree,
  });

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  useEffect(() => {
    const firstRoot = tree.data?.roots[0];
    if (!selectedNodeId && firstRoot) {
      setSelectedNodeId(firstRoot.node_id);
    }
  }, [tree.data, selectedNodeId]);

  const root = tree.data?.roots[0];

  return (
    <div>
      <h2>Шаг 11. Библиотека классификаторов</h2>
      <p className="text-muted">
        Дерево классов документов АСУ и промпты, которыми маленькая LLM
        определяет подкласс на каждом уровне — при условии, что родительский
        класс уже определён предыдущим вызовом. Изменения (название,
        описание, override промпта, новые/удалённые классы) сохраняются
        сразу и переживают перезапуск backend'а.
      </p>

      {tree.isLoading && <p>Загрузка дерева…</p>}
      {tree.error && (
        <div className="banner banner-error">
          {tree.error instanceof Error ? tree.error.message : "Ошибка загрузки дерева"}
        </div>
      )}

      {root && (
        <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div
            className="card"
            style={{
              flex: "1 1 320px",
              minWidth: 260,
              maxWidth: 420,
              border: "1px solid #ddd",
              borderRadius: 4,
              position: "sticky",
              top: 16,
            }}
          >
            <div
              style={{
                padding: "10px 12px",
                borderBottom: "1px solid #eee",
                fontWeight: 600,
                fontSize: 13,
              }}
              data-testid="classifier-tree-summary"
            >
              Дерево классов ·{" "}
              <span className="text-muted" style={{ fontWeight: 400 }}>
                {tree.data?.total_nodes ?? 0} всего
              </span>
            </div>
            <div style={{ maxHeight: 560, overflowY: "auto", padding: "6px 4px" }}>
              <ClassifierTree
                root={root}
                selectedNodeId={selectedNodeId}
                onSelect={setSelectedNodeId}
              />
            </div>
          </div>
          <div style={{ flex: "2 1 420px", minWidth: 300 }}>
            {selectedNodeId && (
              <ClassifierNodePanel nodeId={selectedNodeId} onSelectNode={setSelectedNodeId} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
