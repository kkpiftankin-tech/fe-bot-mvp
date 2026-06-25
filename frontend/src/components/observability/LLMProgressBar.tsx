import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getLLMStats } from "../../api/llm_stats";
import type { LLMModelStats } from "../../api/types";

interface Props {
  /** Активен ли LLM-вызов прямо сейчас. */
  active: boolean;
  /** Сколько одновременных LLM-вызовов ожидается. */
  concurrency?: number;
  /** Имя модели (для выбора avg/p95 из stats). */
  model?: string;
  /** Текст над progress bar. */
  label?: string;
}

const POLL_INTERVAL_MS = 1000;
const FRAME_MS = 100;
const COLD_START_AVG_MS = 5_000;

function pickModel(
  models: LLMModelStats[],
  preferred?: string,
): LLMModelStats | null {
  if (!models.length) return null;
  if (preferred) {
    const match = models.find((m) => m.model === preferred);
    if (match) return match;
  }
  // Fallback: модель с наибольшим counts (наиболее активная).
  return models.reduce((a, b) => (a.count >= b.count ? a : b));
}

/**
 * OBS-LLM-01: live progress bar для текущего LLM-вызова на основе running
 * статистики. Когда active=true:
 * - анимирует от 0% до 100% за `avg_ms` (running average для модели).
 * - после avg_ms переключается в indeterminate (striped pulse) — значит
 *   вызов идёт дольше обычного.
 * - после p95_ms показывает "медленнее обычного, но процесс идёт".
 */
export function LLMProgressBar({
  active,
  concurrency = 1,
  model,
  label,
}: Props): JSX.Element | null {
  const stats = useQuery({
    queryKey: ["llmStats"],
    queryFn: getLLMStats,
    refetchInterval: active ? POLL_INTERVAL_MS : 30_000,
    enabled: true,
  });

  const [elapsedMs, setElapsedMs] = useState<number>(0);

  // Animate clock when active.
  useEffect(() => {
    if (!active) {
      setElapsedMs(0);
      return;
    }
    setElapsedMs(0);
    const start = Date.now();
    const id = window.setInterval(() => {
      setElapsedMs(Date.now() - start);
    }, FRAME_MS);
    return () => window.clearInterval(id);
  }, [active]);

  const selected = pickModel(stats.data?.models ?? [], model);
  const avgMs =
    (selected?.avg_ms ?? COLD_START_AVG_MS) * Math.max(concurrency, 1);
  const p95Ms =
    (selected?.p95_ms ?? COLD_START_AVG_MS * 2) * Math.max(concurrency, 1);

  if (!active) return null;

  const ratio = Math.min(elapsedMs / Math.max(avgMs, 1), 1);
  const pct = Math.round(ratio * 100);
  const overAvg = elapsedMs > avgMs;
  const overP95 = elapsedMs > p95Ms;

  const elapsedSec = (elapsedMs / 1000).toFixed(1);
  const avgSec = (avgMs / 1000).toFixed(1);
  const p95Sec = (p95Ms / 1000).toFixed(1);

  const statusText = overP95
    ? `Дольше обычного (>p95 ${p95Sec}s) — процесс идёт, не застрял`
    : overAvg
      ? `Чуть дольше среднего (${avgSec}s) — почти готово`
      : `~ ${elapsedSec}s из ${avgSec}s`;

  return (
    <div
      data-testid="llm-progress-bar"
      style={{
        margin: "8px 0",
        padding: "8px 12px",
        background: "#f8f9fa",
        border: "1px solid #ddd",
        borderRadius: 4,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 13,
          marginBottom: 4,
        }}
      >
        <span>
          {label ?? `LLM ${selected?.model ?? model ?? "ollama"}`}{" "}
          {concurrency > 1 ? `×${concurrency}` : ""}
        </span>
        <span
          className="text-muted"
          data-testid="llm-progress-status"
          style={{ color: overP95 ? "#c0392b" : overAvg ? "#d35400" : "#666" }}
        >
          {statusText}
        </span>
      </div>
      <div
        style={{
          width: "100%",
          height: 8,
          background: "#e9ecef",
          borderRadius: 4,
          overflow: "hidden",
          position: "relative",
        }}
      >
        {!overAvg ? (
          <div
            data-testid="llm-progress-fill"
            style={{
              width: `${pct}%`,
              height: "100%",
              background: "#3498db",
              transition: `width ${FRAME_MS}ms linear`,
            }}
          />
        ) : (
          // Indeterminate striped pulse после avg_ms.
          <div
            data-testid="llm-progress-indeterminate"
            style={{
              width: "100%",
              height: "100%",
              backgroundImage:
                "repeating-linear-gradient(45deg, #3498db 0 10px, #2980b9 10px 20px)",
              backgroundSize: "40px 8px",
              animation: "llmprogress-stripe 1.2s linear infinite",
            }}
          />
        )}
      </div>
      <style>{`@keyframes llmprogress-stripe { from { background-position: 0 0; } to { background-position: 40px 0; } }`}</style>
      {selected && (
        <div
          className="text-muted"
          style={{ fontSize: 11, marginTop: 4 }}
          data-testid="llm-progress-stats"
        >
          Статистика {selected.model}: avg {(selected.avg_ms / 1000).toFixed(1)}s ·
          p50 {(selected.p50_ms / 1000).toFixed(1)}s · p95{" "}
          {(selected.p95_ms / 1000).toFixed(1)}s · вызовов {selected.count}
        </div>
      )}
    </div>
  );
}
