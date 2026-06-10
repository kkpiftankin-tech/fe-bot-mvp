import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { publishKB } from "../../../api/setup";
import { ApiError } from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";
export function PublishStep() {
    const { setupJobId, setStep, evalReport } = useWizardStore();
    const [comment, setComment] = useState("");
    const mutation = useMutation({
        mutationFn: () => {
            if (!setupJobId)
                throw new Error("no setup_job_id");
            return publishKB(setupJobId, {
                eval_report: evalReport,
                comment: comment || undefined,
            });
        },
    });
    const errorMessage = mutation.error instanceof ApiError
        ? mutation.error.message
        : mutation.error?.message;
    const result = mutation.data;
    return (_jsxs("div", { children: [_jsx("h2", { children: "\u0428\u0430\u0433 6. \u041F\u0443\u0431\u043B\u0438\u043A\u0430\u0446\u0438\u044F Knowledge Base" }), _jsxs("p", { className: "text-muted", children: ["\u0421\u043E\u0437\u0434\u0430\u0451\u0442 \u043D\u043E\u0432\u0443\u044E ", _jsx("code", { children: "KnowledgeBaseVersion" }), " \u0438 \u0430\u043A\u0442\u0438\u0432\u0438\u0440\u0443\u0435\u0442 \u0435\u0451. \u041F\u0440\u0435\u0434\u044B\u0434\u0443\u0449\u0430\u044F ACTIVE KB \u0430\u0432\u0442\u043E\u043C\u0430\u0442\u0438\u0447\u0435\u0441\u043A\u0438 \u0434\u0435preset\u0442\u0435\u0442\u0441\u044F.", _jsx("br", {}), "\u0422\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044F \u0440\u043E\u043B\u044C ", _jsx("code", { children: "admin" }), " \u0438\u043B\u0438 ", _jsx("code", { children: "rag_admin" }), " (permission", _jsx("code", { children: "kb.publish" }), ")."] }), !evalReport && (_jsx("div", { className: "banner banner-warning", "data-testid": "no-eval-warning", children: "Eval-\u043E\u0442\u0447\u0451\u0442 \u043E\u0442\u0441\u0443\u0442\u0441\u0442\u0432\u0443\u0435\u0442. \u041F\u0443\u0431\u043B\u0438\u043A\u0430\u0446\u0438\u044F \u043F\u0440\u043E\u0439\u0434\u0451\u0442 \u0431\u0435\u0437 gate-\u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0438. \u0420\u0435\u043A\u043E\u043C\u0435\u043D\u0434\u0443\u0435\u043C \u0441\u043D\u0430\u0447\u0430\u043B\u0430 \u043F\u0440\u043E\u0439\u0442\u0438 retrieval-tests." })), evalReport && (_jsxs("div", { className: evalReport.passed ? "banner banner-success" : "banner banner-error", children: ["Eval: ", evalReport.passed ? "passed" : "FAILED", " \u00B7 recall@", evalReport.top_k, "=", evalReport.mean_recall_at_k.toFixed(3)] })), _jsxs("div", { className: "form-group", children: [_jsx("label", { htmlFor: "comment", children: "\u041A\u043E\u043C\u043C\u0435\u043D\u0442\u0430\u0440\u0438\u0439 (\u043E\u043F\u0446\u0438\u043E\u043D\u0430\u043B\u044C\u043D\u043E)" }), _jsx("input", { id: "comment", value: comment, onChange: (e) => setComment(e.target.value), "data-testid": "publish-comment" })] }), _jsx("div", { className: "btn-row", children: _jsx("button", { className: "btn", disabled: mutation.isPending || evalReport?.passed === false, onClick: () => mutation.mutate(), "data-testid": "submit-publish", children: mutation.isPending ? "Публикуем…" : "Опубликовать KB" }) }), errorMessage && (_jsx("div", { className: "error-text", "data-testid": "publish-error", children: errorMessage })), result && (_jsxs("div", { className: "banner banner-success", style: { marginTop: 16 }, children: ["KB ", _jsx("strong", { children: result.knowledge_base_version }), " \u0430\u043A\u0442\u0438\u0432\u0438\u0440\u043E\u0432\u0430\u043D\u0430.", _jsxs("div", { className: "kv-grid", style: { marginTop: 8 }, children: [_jsx("div", { className: "key", children: "Status" }), _jsx("div", { "data-testid": "published-status", children: result.status }), _jsx("div", { className: "key", children: "is_active" }), _jsx("div", { children: String(result.is_active) }), _jsx("div", { className: "key", children: "Published by" }), _jsx("div", { children: result.published_by ?? "—" }), _jsx("div", { className: "key", children: "Published at" }), _jsx("div", { children: result.published_at ?? "—" }), _jsx("div", { className: "key", children: "index_version" }), _jsx("div", { children: result.index_version ?? "—" }), _jsx("div", { className: "key", children: "\u041A\u0430\u0440\u0442\u043E\u0447\u0435\u043A" }), _jsx("div", { children: result.rag_card_count }), _jsx("div", { className: "key", children: "Chunks" }), _jsx("div", { children: result.chunk_count })] }), _jsx("div", { className: "btn-row", children: _jsx("button", { className: "btn", onClick: () => setStep("report"), "data-testid": "continue-to-report", children: "\u041A \u0438\u0442\u043E\u0433\u043E\u0432\u043E\u043C\u0443 \u043E\u0442\u0447\u0451\u0442\u0443 \u2192" }) })] }))] }));
}
