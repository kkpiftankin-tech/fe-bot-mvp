import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { runRetrievalTests } from "../../../api/setup";
import { ApiError } from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";
let nextId = 1;
const newRow = () => ({
    id: `gq_${nextId++}`,
    query: "",
    expected: "",
});
export function RetrievalTestsStep() {
    const { setupJobId, setStep, setEvalReport } = useWizardStore();
    const [rows, setRows] = useState([newRow()]);
    const [topK, setTopK] = useState(5);
    const [threshold, setThreshold] = useState("");
    const mutation = useMutation({
        mutationFn: () => {
            if (!setupJobId)
                throw new Error("no setup_job_id");
            const golden = rows
                .filter((r) => r.query.trim() && r.expected.trim())
                .map((r) => ({
                query: r.query.trim(),
                expected_doc_ids: r.expected
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
            }));
            const thresholdNum = threshold ? Number.parseFloat(threshold) : undefined;
            return runRetrievalTests(setupJobId, {
                golden_queries: golden,
                top_k: topK,
                threshold_recall_at_5: thresholdNum,
            });
        },
        onSuccess: (report) => setEvalReport(report),
    });
    const errorMessage = mutation.error instanceof ApiError
        ? mutation.error.message
        : mutation.error?.message;
    const validRows = rows.filter((r) => r.query.trim() && r.expected.trim());
    const report = mutation.data;
    return (_jsxs("div", { children: [_jsx("h2", { children: "\u0428\u0430\u0433 5. Retrieval-tests" }), _jsx("p", { className: "text-muted", children: "\u041E\u043F\u0438\u0448\u0438\u0442\u0435 golden-set \u0438\u0437 (query, expected_doc_ids), \u0447\u0442\u043E\u0431\u044B \u0438\u0437\u043C\u0435\u0440\u0438\u0442\u044C \u043A\u0430\u0447\u0435\u0441\u0442\u0432\u043E retrieval \u043F\u0435\u0440\u0435\u0434 \u043F\u0443\u0431\u043B\u0438\u043A\u0430\u0446\u0438\u0435\u0439. Gate \u043F\u043E \u0443\u043C\u043E\u043B\u0447\u0430\u043D\u0438\u044E \u2014 recall@5 \u2265 0.85." }), _jsxs("div", { className: "row", children: [_jsxs("label", { children: ["top_k:", " ", _jsx("input", { type: "number", min: 1, max: 50, value: topK, onChange: (e) => setTopK(Number.parseInt(e.target.value || "5", 10)), style: { width: 80 }, "data-testid": "top-k" })] }), _jsxs("label", { children: ["threshold recall@5:", " ", _jsx("input", { type: "text", value: threshold, onChange: (e) => setThreshold(e.target.value), placeholder: "\u043F\u043E \u0443\u043C\u043E\u043B\u0447\u0430\u043D\u0438\u044E 0.85", style: { width: 140 }, "data-testid": "threshold" })] })] }), _jsx("h3", { style: { marginTop: 16 }, children: "Golden queries" }), rows.map((row, idx) => (_jsxs("div", { className: "row", style: { marginBottom: 8 }, children: [_jsx("input", { placeholder: "\u0417\u0430\u043F\u0440\u043E\u0441 (\u043D\u0430 \u0435\u0441\u0442\u0435\u0441\u0442\u0432\u0435\u043D\u043D\u043E\u043C \u044F\u0437\u044B\u043A\u0435)", value: row.query, onChange: (e) => setRows(rows.map((r) => r.id === row.id ? { ...r, query: e.target.value } : r)), style: { flex: 1 }, "data-testid": `query-${idx}` }), _jsx("input", { placeholder: "Expected doc_id-\u044B \u0447\u0435\u0440\u0435\u0437 \u0437\u0430\u043F\u044F\u0442\u0443\u044E", value: row.expected, onChange: (e) => setRows(rows.map((r) => r.id === row.id ? { ...r, expected: e.target.value } : r)), style: { flex: 1 }, "data-testid": `expected-${idx}` }), rows.length > 1 && (_jsx("button", { className: "btn btn-secondary", onClick: () => setRows(rows.filter((r) => r.id !== row.id)), children: "\u2212" }))] }, row.id))), _jsx("button", { className: "btn btn-secondary", onClick: () => setRows([...rows, newRow()]), "data-testid": "add-row", children: "+ \u0441\u0442\u0440\u043E\u043A\u0430" }), _jsx("div", { className: "btn-row", children: _jsx("button", { className: "btn", onClick: () => mutation.mutate(), disabled: validRows.length === 0 || mutation.isPending, "data-testid": "submit-eval", children: mutation.isPending ? "Запускаем eval…" : "Запустить eval" }) }), errorMessage && (_jsx("div", { className: "error-text", "data-testid": "eval-error", children: errorMessage })), report && (_jsxs("div", { style: { marginTop: 24 }, children: [_jsx("h3", { children: "\u041E\u0442\u0447\u0451\u0442 eval" }), _jsxs("div", { className: report.passed ? "banner banner-success" : "banner banner-error", "data-testid": "eval-banner", children: ["Gate: ", report.passed ? "PASSED" : "FAILED", " \u00B7 recall@", report.top_k, "=", " ", report.mean_recall_at_k.toFixed(3), " (threshold", " ", report.threshold_recall_at_5.toFixed(2), ")"] }), _jsxs("div", { className: "kv-grid", children: [_jsx("div", { className: "key", children: "\u0417\u0430\u043F\u0440\u043E\u0441\u043E\u0432" }), _jsx("div", { children: report.queries_total }), _jsx("div", { className: "key", children: "\u041E\u0448\u0438\u0431\u043E\u043A" }), _jsx("div", { children: report.queries_errored }), _jsx("div", { className: "key", children: "mean precision@k" }), _jsx("div", { children: report.mean_precision_at_k.toFixed(3) }), _jsx("div", { className: "key", children: "MRR" }), _jsx("div", { children: report.mean_reciprocal_rank.toFixed(3) }), _jsx("div", { className: "key", children: "no_context_rate" }), _jsx("div", { children: report.no_context_rate.toFixed(3) })] }), _jsxs("details", { style: { marginTop: 12 }, children: [_jsx("summary", { children: "Per-query breakdown" }), _jsx("ul", { children: report.per_query.map((q, i) => (_jsxs("li", { children: [_jsx("strong", { children: q.query }), ": recall=", q.recall_at_k.toFixed(2), ", precision=", q.precision_at_k.toFixed(2), ", RR=", q.reciprocal_rank.toFixed(2), q.is_no_context && " ⚠️ no context", q.error_message && ` ⚠️ ${q.error_message}`] }, i))) })] }), _jsxs("div", { className: "btn-row", children: [_jsx("button", { className: "btn", onClick: () => setStep("publish"), disabled: !report.passed, "data-testid": "continue-to-publish", children: "\u041A \u043F\u0443\u0431\u043B\u0438\u043A\u0430\u0446\u0438\u0438 KB \u2192" }), !report.passed && (_jsx("button", { className: "btn btn-secondary", onClick: () => setStep("review"), children: "\u0412\u0435\u0440\u043D\u0443\u0442\u044C\u0441\u044F \u043A review \u043A\u0430\u0440\u0442\u043E\u0447\u0435\u043A" }))] })] }))] }));
}
