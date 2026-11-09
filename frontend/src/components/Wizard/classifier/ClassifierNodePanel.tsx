import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createClassifierChild,
  deleteClassifierNode,
  generateClassifierDescription,
  getClassifierNode,
  updateClassifierNode,
} from "../../../api/classifier";

interface Props {
  nodeId: string;
  onSelectNode: (nodeId: string) => void;
}

/**
 * SETUP-13 / ADR-HTC-09: детальная панель одного узла дерева
 * классификаторов — просмотр/редактирование name/description/
 * prompt_override и добавление/удаление дочерних классов.
 *
 * Навигация по дереву (просмотр детей, переход между узлами) живёт в
 * соседнем ClassifierTree — эта панель только показывает и
 * редактирует ВЫБРАННЫЙ узел, поэтому клик по дереву не «уходит
 * внутрь» и не теряет общий контекст.
 */
export function ClassifierNodePanel({ nodeId, onSelectNode }: Props): JSX.Element {
  const qc = useQueryClient();
  const detail = useQuery({
    queryKey: ["classifierNode", nodeId],
    queryFn: () => getClassifierNode(nodeId),
  });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  // Одно редактируемое поле — фактический промпт узла (автосгенерированный
  // по умолчанию или ранее сохранённый override), без отдельного "превью
  // шаблона": шаблонизация не давала пользы, поэтому промпт просто
  // редактируется как обычный текст.
  const [promptText, setPromptText] = useState("");
  const [newChildName, setNewChildName] = useState("");
  const [newChildDescription, setNewChildDescription] = useState("");

  const node = detail.data?.node;
  const renderedPrompt = detail.data?.rendered_prompt;

  useEffect(() => {
    if (node) {
      setName(node.name);
      setDescription(node.description);
      setPromptText(renderedPrompt ?? "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node, renderedPrompt]);

  function invalidateAfterMutation(affectedNodeId: string): void {
    qc.invalidateQueries({ queryKey: ["classifierNode", affectedNodeId] });
    qc.invalidateQueries({ queryKey: ["classifierTree"] });
    if (node?.parent_id) {
      qc.invalidateQueries({ queryKey: ["classifierNode", node.parent_id] });
    }
  }

  const saveMut = useMutation({
    mutationFn: () => updateClassifierNode(nodeId, { name, description }),
    onSuccess: () => invalidateAfterMutation(nodeId),
  });

  // Черновик описания от маленькой LLM — НЕ сохраняется автоматически:
  // только заполняет поле "Описание" для review/правки, сохраняет
  // обычная кнопка "Сохранить" выше. Названия классов вроде "DNN"
  // без пояснения непонятны ни человеку, ни классифицирующей LLM.
  const generateDescriptionMut = useMutation({
    mutationFn: () => generateClassifierDescription(nodeId),
    onSuccess: (result) => setDescription(result.description),
  });

  const savePromptMut = useMutation({
    mutationFn: () => updateClassifierNode(nodeId, { prompt_override: promptText }),
    onSuccess: () => invalidateAfterMutation(nodeId),
  });

  const resetPromptMut = useMutation({
    mutationFn: () => updateClassifierNode(nodeId, { clear_prompt_override: true }),
    // Поле НЕ очищается вручную — после инвалидации перезапрос вернёт
    // свежий автосгенерированный промпт, и useEffect выше заполнит им поле.
    onSuccess: () => invalidateAfterMutation(nodeId),
  });

  const addChildMut = useMutation({
    mutationFn: () =>
      createClassifierChild(nodeId, {
        name: newChildName,
        description: newChildDescription,
      }),
    onSuccess: () => {
      setNewChildName("");
      setNewChildDescription("");
      invalidateAfterMutation(nodeId);
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteClassifierNode(nodeId),
    onSuccess: () => {
      const parentId = node?.parent_id;
      qc.invalidateQueries({ queryKey: ["classifierTree"] });
      if (parentId) {
        qc.invalidateQueries({ queryKey: ["classifierNode", parentId] });
        onSelectNode(parentId);
      }
    },
  });

  if (detail.isLoading) return <p>Загрузка узла…</p>;
  const data = detail.data;
  if (detail.error || !data || !node) {
    return (
      <div className="banner banner-error">
        {detail.error instanceof Error ? detail.error.message : "Узел не найден"}
      </div>
    );
  }

  const isRoot = node.parent_id === null;

  return (
    <div data-testid="classifier-node-panel">
      <p className="text-muted" data-testid="classifier-node-breadcrumb">
        {node.path.join(" › ")}
      </p>

      <div
        className="card"
        style={{ border: "1px solid #ddd", borderRadius: 4, padding: 16, marginBottom: 16 }}
      >
        <label style={{ display: "block", marginBottom: 8 }}>
          Название
          <input
            data-testid="classifier-node-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <label style={{ display: "block", marginBottom: 8 }}>
          Описание
          <textarea
            data-testid="classifier-node-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="Объясните термин (особенно если это аббревиатура вроде «DNN») — это пояснение попадёт в промпт для классификации."
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <div className="btn-row" style={{ marginBottom: 8 }}>
          <button
            className="btn btn-secondary"
            data-testid="classifier-node-generate-description"
            disabled={generateDescriptionMut.isPending}
            onClick={() => generateDescriptionMut.mutate()}
          >
            {generateDescriptionMut.isPending
              ? "Генерируем…"
              : "🪄 Сгенерировать описание (LLM)"}
          </button>
        </div>
        {generateDescriptionMut.isError && (
          <div className="banner banner-error" style={{ marginBottom: 8 }}>
            {generateDescriptionMut.error instanceof Error
              ? generateDescriptionMut.error.message
              : "Не удалось сгенерировать описание"}
          </div>
        )}
        <div className="btn-row">
          <button
            className="btn"
            data-testid="classifier-node-save"
            disabled={saveMut.isPending}
            onClick={() => saveMut.mutate()}
          >
            {saveMut.isPending ? "Сохраняем…" : "Сохранить"}
          </button>
          {!isRoot && (
            <button
              className="btn btn-danger"
              data-testid="classifier-node-delete"
              disabled={deleteMut.isPending}
              onClick={() => {
                if (window.confirm(`Удалить класс «${node.name}» и всех его потомков?`)) {
                  deleteMut.mutate();
                }
              }}
            >
              {deleteMut.isPending ? "Удаляем…" : "Удалить класс"}
            </button>
          )}
        </div>
        {saveMut.isError && (
          <div className="banner banner-error" style={{ marginTop: 8 }}>
            {saveMut.error instanceof Error ? saveMut.error.message : "Ошибка сохранения"}
          </div>
        )}
        {deleteMut.isError && (
          <div className="banner banner-error" style={{ marginTop: 8 }}>
            {deleteMut.error instanceof Error ? deleteMut.error.message : "Ошибка удаления"}
          </div>
        )}
      </div>

      {!node.is_leaf && (
        <div
          className="card"
          style={{ border: "1px solid #ddd", borderRadius: 4, padding: 16, marginBottom: 16 }}
        >
          <h3 style={{ marginTop: 0 }}>Промпт для классификации подклассов</h3>
          <p className="text-muted">
            Промпт, которым маленькая LLM выбирает один из {node.children_ids.length}{" "}
            дочерних классов ниже — при условии, что этот класс уже определён
            предыдущим шагом. Поле ниже показывает и позволяет напрямую
            редактировать РЕАЛЬНЫЙ промпт этого класса (по умолчанию —
            автосгенерированный из названия, описания и списка дочерних
            классов). Текст самого классифицируемого фрагмента сюда не
            входит — система подставляет его отдельно в момент реальной
            классификации.
          </p>

          <textarea
            data-testid="classifier-node-prompt"
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
            rows={12}
            style={{
              display: "block",
              width: "100%",
              fontFamily: "monospace",
              fontSize: 13,
              boxSizing: "border-box",
            }}
          />
          <div className="btn-row" style={{ marginTop: 8 }}>
            <button
              className="btn"
              data-testid="classifier-node-save-prompt"
              disabled={savePromptMut.isPending || !promptText.trim()}
              onClick={() => savePromptMut.mutate()}
            >
              {savePromptMut.isPending ? "Сохраняем…" : "Сохранить промпт"}
            </button>
            <button
              className="btn btn-secondary"
              data-testid="classifier-node-reset-prompt"
              disabled={resetPromptMut.isPending || !node.prompt_override}
              onClick={() => resetPromptMut.mutate()}
            >
              {resetPromptMut.isPending ? "Восстанавливаем…" : "Восстановить автосгенерированный"}
            </button>
          </div>
          {savePromptMut.isError && (
            <div className="banner banner-error" style={{ marginTop: 8 }}>
              {savePromptMut.error instanceof Error
                ? savePromptMut.error.message
                : "Ошибка сохранения промпта"}
            </div>
          )}
        </div>
      )}

      <div
        className="card"
        style={{ border: "1px solid #ddd", borderRadius: 4, padding: 16, marginBottom: 16 }}
      >
        <details>
          <summary>Добавить дочерний класс</summary>
          <div style={{ marginTop: 8 }}>
            <label style={{ display: "block", marginBottom: 8 }}>
              Название
              <input
                data-testid="classifier-new-child-name"
                value={newChildName}
                onChange={(e) => setNewChildName(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>
            <label style={{ display: "block", marginBottom: 8 }}>
              Описание
              <textarea
                data-testid="classifier-new-child-description"
                value={newChildDescription}
                onChange={(e) => setNewChildDescription(e.target.value)}
                rows={2}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>
            <button
              className="btn"
              data-testid="classifier-add-child"
              disabled={addChildMut.isPending || !newChildName.trim()}
              onClick={() => addChildMut.mutate()}
            >
              {addChildMut.isPending ? "Добавляем…" : "Добавить класс"}
            </button>
            {addChildMut.isError && (
              <div className="banner banner-error" style={{ marginTop: 8 }}>
                {addChildMut.error instanceof Error
                  ? addChildMut.error.message
                  : "Ошибка добавления"}
              </div>
            )}
          </div>
        </details>
      </div>
    </div>
  );
}
