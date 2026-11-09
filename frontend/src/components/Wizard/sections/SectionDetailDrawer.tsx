// SETUP-04 UX: детализация ParsedSection в drawer'е.
// 3 вкладки:
//   1. Content — raw_text, normalized_text, heading_path, offsets, hash
//   2. Классификация — bitmap-расшифровка (level, slug, confidence, is_primary)
//   3. Prompts — LLM prompt preview для L0/L1/L2

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getSectionDetail, getSectionPrompts } from "../../../api/parse";

interface Props {
  setupJobId: string;
  parseJobId: string;
  sectionId: string;
  onClose: () => void;
}

type Tab = "content" | "classification" | "prompts";

export function SectionDetailDrawer({
  setupJobId,
  parseJobId,
  sectionId,
  onClose,
}: Props): JSX.Element {
  const [tab, setTab] = useState<Tab>("content");
  const detailQuery = useQuery({
    queryKey: ["sectionDetail", setupJobId, parseJobId, sectionId],
    queryFn: () => getSectionDetail(setupJobId, parseJobId, sectionId),
  });
  const promptsQuery = useQuery({
    queryKey: ["sectionPrompts", setupJobId, parseJobId, sectionId],
    queryFn: () => getSectionPrompts(setupJobId, parseJobId, sectionId),
    enabled: tab === "prompts",
  });

  const detail = detailQuery.data;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: "min(900px, 90vw)",
        background: "#fff",
        boxShadow: "-2px 0 10px rgba(0,0,0,0.15)",
        zIndex: 100,
        display: "flex",
        flexDirection: "column",
      }}
      data-testid="section-detail-drawer"
    >
      <header
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid #ddd",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <h3 style={{ margin: 0, flex: 1 }}>
          {detail?.title ?? "Секция"}{" "}
          {detail && (
            <code style={{ fontSize: 11, color: "#888" }}>
              [{detail.section_type}]
            </code>
          )}
        </h3>
        <button
          className="btn btn-secondary"
          onClick={onClose}
          data-testid="drawer-close"
        >
          ✕
        </button>
      </header>

      <nav
        style={{
          display: "flex",
          borderBottom: "1px solid #ddd",
          gap: 0,
        }}
      >
        {(
          [
            ["content", "Текст (raw / normalized)"],
            ["classification", "Классификация"],
            ["prompts", "LLM Prompts"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            data-testid={`tab-${id}`}
            style={{
              padding: "8px 16px",
              background: tab === id ? "#4c9aff" : "transparent",
              color: tab === id ? "white" : "#333",
              border: "none",
              borderBottom: tab === id ? "2px solid #4c9aff" : "none",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: tab === id ? 600 : 400,
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {detailQuery.isLoading && <p>Загружаем детали секции…</p>}
        {detailQuery.error && (
          <div className="banner banner-error">
            {detailQuery.error instanceof Error
              ? detailQuery.error.message
              : "Ошибка"}
          </div>
        )}
        {detail && tab === "content" && (
          <ContentTab detail={detail} />
        )}
        {detail && tab === "classification" && (
          <ClassificationTab detail={detail} />
        )}
        {detail && tab === "prompts" && (
          <PromptsTab
            prompts={promptsQuery.data ?? []}
            loading={promptsQuery.isLoading}
            error={
              promptsQuery.error instanceof Error
                ? promptsQuery.error.message
                : null
            }
          />
        )}
      </div>
    </div>
  );
}

// --------------------------------------------------
// Tab components
// --------------------------------------------------

function ContentTab({
  detail,
}: {
  detail: import("../../../api/types").ParsedSectionDetailDTO;
}): JSX.Element {
  return (
    <div data-testid="content-tab">
      <div className="kv-grid" style={{ marginBottom: 12 }}>
        <div className="key">section_id</div>
        <div>
          <code style={{ fontSize: 11 }}>{detail.section_id}</code>
        </div>
        <div className="key">heading_path</div>
        <div>{detail.heading_path.join(" › ") || "—"}</div>
        <div className="key">index</div>
        <div>{detail.section_index}</div>
        <div className="key">offsets</div>
        <div>
          {detail.start_offset ?? "—"}..{detail.end_offset ?? "—"}
        </div>
        <div className="key">content_hash</div>
        <div>
          <code style={{ fontSize: 11 }}>
            {detail.content_hash.slice(0, 16)}…
          </code>
        </div>
        <div className="key">status</div>
        <div>{detail.section_status}</div>
        <div className="key">confidence</div>
        <div>{detail.confidence?.toFixed(3) ?? "—"}</div>
        <div className="key">method</div>
        <div>{detail.classification_method ?? "—"}</div>
      </div>

      <h4>raw_text ({detail.raw_text.length} симв.)</h4>
      <pre
        style={{
          background: "#f6f8fa",
          padding: 12,
          borderRadius: 4,
          fontSize: 12,
          maxHeight: 300,
          overflow: "auto",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
        data-testid="raw-text"
      >
        {detail.raw_text}
      </pre>

      <h4>normalized_text ({detail.normalized_text.length} симв.)</h4>
      <pre
        style={{
          background: "#f6f8fa",
          padding: 12,
          borderRadius: 4,
          fontSize: 12,
          maxHeight: 300,
          overflow: "auto",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
        data-testid="normalized-text"
      >
        {detail.normalized_text}
      </pre>
    </div>
  );
}

function ClassifierTreeResultTab({
  result,
}: {
  result: NonNullable<
    import("../../../api/types").ParsedSectionDetailDTO["classifier_result"]
  >;
}): JSX.Element {
  if (result.path.length === 0) {
    return (
      <div className="banner banner-warning" data-testid="classifier-result-unmatched">
        Маленькая LLM не смогла уверенно отнести фрагмент ни к одному
        классу верхнего уровня дерева <code>{result.tree_id}</code>.
      </div>
    );
  }
  return (
    <div data-testid="classifier-result-tab">
      <div className="kv-grid" style={{ marginBottom: 12 }}>
        <div className="key">дерево</div>
        <div>
          <code>{result.tree_id}</code>
        </div>
        <div className="key">путь</div>
        <div>{result.path.map((s) => s.name).join(" → ")}</div>
        <div className="key">дошли до листа?</div>
        <div>
          {result.reached_leaf ? (
            <span style={{ color: "#2fbf71" }}>да</span>
          ) : (
            <span className="text-muted">нет — можно уточнить глубже</span>
          )}
        </div>
      </div>

      <table className="table" style={{ fontSize: 12 }}>
        <thead>
          <tr>
            <th>уровень</th>
            <th>класс</th>
            <th>node_id</th>
            <th>confidence</th>
            <th>обоснование LLM</th>
          </tr>
        </thead>
        <tbody>
          {result.path.map((step, idx) => (
            <tr key={step.node_id} data-testid={`classifier-result-step-${idx}`}>
              <td>{idx}</td>
              <td>{step.name}</td>
              <td>
                <code style={{ fontSize: 11 }}>{step.node_id}</code>
              </td>
              <td>{step.confidence.toFixed(2)}</td>
              <td>{step.reason || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ClassificationTab({
  detail,
}: {
  detail: import("../../../api/types").ParsedSectionDetailDTO;
}): JSX.Element {
  if (detail.classifier_result) {
    return <ClassifierTreeResultTab result={detail.classifier_result} />;
  }
  const state = detail.classification_state;
  if (!state) {
    return (
      <div className="text-muted" data-testid="no-classification">
        Секция классифицирована rule-based методом — классификация по
        дереву классификаторов не запускалась. Запустите backend с{" "}
        <code>FE_BOT_TAXONOMY_MODE=llm</code>, чтобы каждая секция
        классифицировалась по дереву из вкладки «Библиотека
        классификаторов».
      </div>
    );
  }
  const bitsByLevel = new Map<number, typeof detail.classification_bits>();
  for (const b of detail.classification_bits) {
    const arr = bitsByLevel.get(b.level) ?? [];
    arr.push(b);
    bitsByLevel.set(b.level, arr);
  }
  return (
    <div data-testid="classification-tab">
      <div className="kv-grid" style={{ marginBottom: 12 }}>
        <div className="key">taxonomy_version</div>
        <div>
          <code>{state.taxonomy_version_id}</code>
        </div>
        <div className="key">bitmap</div>
        <div>
          <code>{binaryString(state.classification_bitmap)}</code>
          <span className="text-muted" style={{ marginLeft: 6, fontSize: 11 }}>
            (dec: {state.classification_bitmap})
          </span>
        </div>
        <div className="key">primary_l0_idx</div>
        <div>{state.primary_l0_idx ?? "—"}</div>
        <div className="key">primary_l1_idx</div>
        <div>{state.primary_l1_idx ?? "—"}</div>
        <div className="key">unknown_at_level</div>
        <div>
          {state.unknown_at_level !== null ? (
            <>
              L{state.unknown_at_level} (cascading stop)
            </>
          ) : (
            <span style={{ color: "#2fbf71" }}>none — все 3 уровня</span>
          )}
        </div>
        <div className="key">confidence per level</div>
        <div>
          L0: {state.confidence_per_level[0].toFixed(2)} · L1:{" "}
          {state.confidence_per_level[1].toFixed(2)} · L2:{" "}
          {state.confidence_per_level[2].toFixed(2)}
        </div>
      </div>

      {[0, 1, 2].map((lvl) => {
        const bits = bitsByLevel.get(lvl) ?? [];
        return (
          <div key={lvl} style={{ marginBottom: 16 }}>
            <h4>Уровень L{lvl}</h4>
            {bits.length === 0 ? (
              <p className="text-muted">Нет установленных бит.</p>
            ) : (
              <table className="table" style={{ fontSize: 12 }}>
                <thead>
                  <tr>
                    <th>bit</th>
                    <th>class_slug</th>
                    <th>display_name</th>
                    <th>doc_type_hint</th>
                    <th>confidence</th>
                    <th>primary?</th>
                  </tr>
                </thead>
                <tbody>
                  {bits.map((b) => (
                    <tr
                      key={`${b.level}-${b.bit_index}`}
                      data-testid={`bit-${b.level}-${b.bit_index}`}
                    >
                      <td>{b.bit_index}</td>
                      <td>
                        <code>{b.class_slug}</code>
                      </td>
                      <td>{b.display_name_ru}</td>
                      <td>
                        <code style={{ fontSize: 11 }}>
                          {b.doc_type_hint ?? "—"}
                        </code>
                      </td>
                      <td>{b.confidence?.toFixed(3) ?? "—"}</td>
                      <td>
                        {b.is_primary ? (
                          <span style={{ color: "#2fbf71" }}>★</span>
                        ) : (
                          ""
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </div>
  );
}

function PromptsTab({
  prompts,
  loading,
  error,
}: {
  prompts: import("../../../api/types").ClassificationPromptDTO[];
  loading: boolean;
  error: string | null;
}): JSX.Element {
  if (loading) return <p>Загружаем prompts…</p>;
  if (error)
    return <div className="banner banner-error">{error}</div>;
  if (prompts.length === 0)
    return <p className="text-muted">Prompts не доступны.</p>;
  return (
    <div data-testid="prompts-tab">
      <p className="text-muted" style={{ fontSize: 12 }}>
        Prompts рендерятся <strong>текущим</strong> ClassificationPromptRenderer
        с текущим состоянием реестра. Это не исторический prompt (не
        сохраняется), а «как выглядел бы запрос сейчас». Пригодится для
        отладки и понимания что видит LLM.
      </p>
      {prompts.map((p) => (
        <details
          key={p.level}
          open={p.level === 0}
          style={{
            marginBottom: 12,
            border: "1px solid #ddd",
            borderRadius: 4,
          }}
          data-testid={`prompt-l${p.level}`}
        >
          <summary
            style={{
              padding: "8px 12px",
              background: p.can_render ? "#eef" : "#f6f6f6",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            Уровень L{p.level}{" "}
            <code style={{ fontSize: 11, fontWeight: 400 }}>
              {p.parent_path || "(root)"}
            </code>{" "}
            —{" "}
            {p.can_render ? (
              <>
                {p.candidates_count} кандидатов, {p.free_slots_count}{" "}
                свободных слотов
              </>
            ) : (
              <span style={{ color: "#c0392b" }}>{p.reason ?? "n/a"}</span>
            )}
          </summary>
          {p.can_render ? (
            <pre
              style={{
                background: "#0f172a",
                color: "#e2e8f0",
                padding: 12,
                margin: 0,
                fontSize: 11,
                maxHeight: 400,
                overflow: "auto",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {p.rendered_prompt}
            </pre>
          ) : null}
        </details>
      ))}
    </div>
  );
}

function binaryString(n: number): string {
  // 30-bit repr, group by 10 for L2 | L1 | L0
  const bits = n.toString(2).padStart(30, "0");
  return `${bits.slice(0, 10)} | ${bits.slice(10, 20)} | ${bits.slice(20, 30)}`;
}
