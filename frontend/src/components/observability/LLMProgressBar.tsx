import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
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

const POLL_ACTIVE_MS = 500;
const POLL_IDLE_MS = 10_000;
const FRAME_MS = 100;
const COLD_START_AVG_MS = 5_000;
const COMPLETED_DISPLAY_MS = 4_000;

function pickModel(
  models: LLMModelStats[],
  preferred?: string,
): LLMModelStats | null {
  if (!models.length) return null;
  if (preferred) {
    const match = models.find((m) => m.model === preferred);
    if (match) return match;
  }
  return models.reduce((a, b) => (a.count >= b.count ? a : b));
}

/**
 * OBS-LLM-01: live progress bar для LLM-вызовов.
 *
 * Состояния:
 * - active=true → синяя полоса 0→100% за avg_ms, затем striped indeterminate.
 * - active=false и недавно был active → "✓ Завершено за Xs" (4 секунды).
 * - active=false и накоплена статистика → компактный stats badge всегда.
 * - active=false и нет статистики → ничего.
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
    refetchInterval: active ? POLL_ACTIVE_MS : POLL_IDLE_MS,
  });

  const [elapsedMs, setElapsedMs] = useState<number>(0);
  const [completedAt, setCompletedAt] = useState<number | null>(null);
  const [completedMs, setCompletedMs] = useState<number | null>(null);
  const lastActiveRef = useRef<boolean>(false);
  const startRef = useRef<number>(0);

  useEffect(() => {
    if (active) {
      startRef.current = Date.now();
      setElapsedMs(0);
      setCompletedAt(null);
      setCompletedMs(null);
      lastActiveRef.current = true;
      const id = window.setInterval(() => {
        setElapsedMs(Date.now() - startRef.current);
      }, FRAME_MS);
      return () => window.clearInterval(id);
    }
    // active flipped to false
    if (lastActiveRef.current) {
      setCompletedMs(Date.now() - startRef.current);
      setCompletedAt(Date.now());
      lastActiveRef.current = false;
    }
    return undefined;
  }, [active]);

  // Hide "completed" state after COMPLETED_DISPLAY_MS.
  const [, forceTick] = useState(0);
  useEffect(() => {
    if (completedAt === null) return;
    const id = window.setTimeout(() => {
      setCompletedAt(null);
      forceTick((n) => n + 1);
    }, COMPLETED_DISPLAY_MS);
    return () => window.clearTimeout(id);
  }, [completedAt]);

  const selected = pickModel(stats.data?.models ?? [], model);
  const avgMs =
    (selected?.avg_ms ?? COLD_START_AVG_MS) * Math.max(concurrency, 1);
  const p95Ms =
    (selected?.p95_ms ?? COLD_START_AVG_MS * 2) * Math.max(concurrency, 1);

  const showActive = active;
  const showCompleted = !active && completedAt !== null;
  const showIdleStats = !active && !showCompleted && selected !== null;

  if (!showActive && !showCompleted && !showIdleStats) {
    return null;
  }

  const ratio = Math.min(elapsedMs / Math.max(avgMs, 1), 1);
  const pct = Math.round(ratio * 100);
  const overAvg = elapsedMs > avgMs;
  const overP95 = elapsedMs > p95Ms;

  const elapsedSec = (elapsedMs / 1000).toFixed(1);
  const avgSec = (avgMs / 1000).toFixed(1);
  const p95Sec = (p95Ms / 1000).toFixed(1);
  const completedSec =
    completedMs !== null ? (completedMs / 1000).toFixed(1) : null;

  const statusText = showActive
    ? overP95
      ? `Дольше обычного (>p95 ${p95Sec}s) — процесс идёт, не застрял`
      : overAvg
        ? `Чуть дольше среднего (${avgSec}s) — почти готово`
        : `~ ${elapsedSec}s из ~${avgSec}s ожидаемых`
    : showCompleted
      ? `✓ Завершено за ${completedSec}s`
      : `Готов — последний вызов ${selected?.last_ms ? (selected.last_ms / 1000).toFixed(1) : "?"}s`;

  const bgColor = showActive ? "#f8f9fa" : showCompleted ? "#e8f5e9" : "#f0f0f0";
  const borderColor = showActive ? "#ddd" : showCompleted ? "#a5d6a7" : "#ddd";

  return (
    <div
      data-testid="llm-progress-bar"
      style={{
        margin: "8px 0",
        padding: "8px 12px",
        background: bgColor,
        border: `1px solid ${borderColor}`,
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
          {label ?? `LLM ${selected?.model ?? model ?? "ollama"}`}
          {concurrency > 1 ? ` ×${concurrency}` : ""}
        </span>
        <span
          data-testid="llm-progress-status"
          style={{
            color: showCompleted
              ? "#2e7d32"
              : overP95
                ? "#c0392b"
                : overAvg
                  ? "#d35400"
                  : "#666",
          }}
        >
          {statusText}
        </span>
      </div>
      {(showActive || showCompleted) && (
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
          {showCompleted ? (
            <div
              data-testid="llm-progress-completed"
              style={{
                width: "100%",
                height: "100%",
                background: "#43a047",
              }}
            />
          ) : !overAvg ? (
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
      )}
      <style>{`@keyframes llmprogress-stripe { from { background-position: 0 0; } to { background-position: 40px 0; } }`}</style>
      {selected && (
        <div
          style={{ fontSize: 11, marginTop: 4, color: "#666" }}
          data-testid="llm-progress-stats"
        >
          📊 {selected.model}: avg {(selected.avg_ms / 1000).toFixed(1)}s ·
          p50 {(selected.p50_ms / 1000).toFixed(1)}s · p95{" "}
          {(selected.p95_ms / 1000).toFixed(1)}s · вызовов {selected.count}
        </div>
      )}
      {!selected && (
        <div
          style={{ fontSize: 11, marginTop: 4, color: "#999" }}
          data-testid="llm-progress-cold"
        >
          📊 Статистика пуста — оценка cold start ({(COLD_START_AVG_MS / 1000).toFixed(0)}s)
        </div>
      )}
    </div>
  );
}
