import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useQuery } from "@tanstack/react-query";
import { getReport } from "../../../api/setup";
import { useWizardStore } from "../../../store/wizardStore";
export function ReportStep() {
    const { setupJobId, reset } = useWizardStore();
    const reportQuery = useQuery({
        queryKey: ["report", setupJobId],
        queryFn: () => {
            if (!setupJobId)
                throw new Error("no setup_job_id");
            return getReport(setupJobId);
        },
        enabled: !!setupJobId,
    });
    if (reportQuery.isLoading) {
        return _jsx("p", { className: "text-muted", children: "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043C \u043E\u0442\u0447\u0451\u0442\u2026" });
    }
    if (!reportQuery.data) {
        return _jsx("p", { className: "error-text", children: "\u041E\u0442\u0447\u0451\u0442 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D." });
    }
    const r = reportQuery.data;
    return (_jsxs("div", { children: [_jsx("h2", { children: "\u0428\u0430\u0433 7. \u0418\u0442\u043E\u0433\u043E\u0432\u044B\u0439 \u043E\u0442\u0447\u0451\u0442" }), _jsx("p", { className: "text-muted", children: "\u0421\u0432\u043E\u0434\u043A\u0430 \u043F\u043E \u0432\u0441\u0435\u043C\u0443 setup job \u2014 \u0438\u0441\u043F\u043E\u043B\u044C\u0437\u0443\u0435\u0442\u0441\u044F auditor'\u043E\u043C \u0434\u043B\u044F \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0438 \u043A\u0430\u0447\u0435\u0441\u0442\u0432\u0430 KB \u0434\u043E \u0432\u044B\u043A\u0430\u0442\u043A\u0438 \u0432 Runtime." }), _jsxs("div", { className: r.knowledge_base_is_active
                    ? "banner banner-success"
                    : "banner banner-info", "data-testid": "report-banner", children: ["Job ", _jsx("strong", { children: r.setup_job_id }), " \u00B7 \u0441\u0442\u0430\u0442\u0443\u0441: ", r.status, r.knowledge_base_version && (_jsxs(_Fragment, { children: [_jsx("br", {}), "Active KB: ", _jsx("strong", { children: r.knowledge_base_version }), " \u00B7", " ", r.knowledge_base_status] }))] }), _jsx("h3", { children: "\u041F\u0440\u043E\u0435\u043A\u0442" }), _jsxs("div", { className: "kv-grid", children: [_jsx("div", { className: "key", children: "project_name" }), _jsx("div", { children: r.project_name }), _jsx("div", { className: "key", children: "user_id" }), _jsx("div", { children: r.user_id }), _jsx("div", { className: "key", children: "started_at" }), _jsx("div", { children: r.started_at ?? "—" }), _jsx("div", { className: "key", children: "finished_at" }), _jsx("div", { children: r.finished_at ?? "—" })] }), _jsx("h3", { style: { marginTop: 16 }, children: "\u0414\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B \u0438 \u043A\u0430\u0440\u0442\u043E\u0447\u043A\u0438" }), _jsxs("div", { className: "kv-grid", children: [_jsx("div", { className: "key", children: "\u0414\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u043E\u0432 \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043D\u043E" }), _jsx("div", { children: r.documents_count }), _jsx("div", { className: "key", children: "\u0412\u0441\u0435\u0433\u043E \u043A\u0430\u0440\u0442\u043E\u0447\u0435\u043A" }), _jsx("div", { children: r.cards_count }), _jsx("div", { className: "key", children: "Approved+indexed+published" }), _jsx("div", { children: r.cards_approved }), _jsx("div", { className: "key", children: "\u0422\u0440\u0435\u0431\u0443\u044E\u0442 review" }), _jsx("div", { children: r.cards_review_required }), _jsx("div", { className: "key", children: "Deprecated" }), _jsx("div", { children: r.cards_deprecated })] }), _jsx("h3", { style: { marginTop: 16 }, children: "Indexing & Knowledge Base" }), _jsxs("div", { className: "kv-grid", children: [_jsx("div", { className: "key", children: "chunks_indexed" }), _jsx("div", { children: r.chunks_indexed }), _jsx("div", { className: "key", children: "index_version" }), _jsx("div", { children: r.index_version ?? "—" }), _jsx("div", { className: "key", children: "knowledge_base_version" }), _jsx("div", { children: r.knowledge_base_version ?? "—" }), _jsx("div", { className: "key", children: "knowledge_base_status" }), _jsx("div", { children: r.knowledge_base_status ?? "—" }), _jsx("div", { className: "key", children: "eval_passed" }), _jsx("div", { children: r.eval_passed === null
                            ? "—"
                            : r.eval_passed
                                ? "✓"
                                : "✗" })] }), _jsx("h3", { style: { marginTop: 16 }, children: "\u041F\u0440\u043E\u0433\u0440\u0435\u0441\u0441" }), _jsx("div", { className: "progress-bar", children: _jsx("div", { style: { width: `${r.progress_percent}%` } }) }), _jsxs("div", { className: "text-muted", children: [r.progress_percent.toFixed(0), "% \u00B7 \u043E\u0448\u0438\u0431\u043E\u043A: ", r.error_count, ", \u043F\u0440\u0435\u0434\u0443\u043F\u0440\u0435\u0436\u0434\u0435\u043D\u0438\u0439:", " ", r.warning_count] }), _jsx("div", { className: "btn-row", children: _jsx("button", { className: "btn btn-secondary", onClick: () => reset(), "data-testid": "new-job", children: "\u041D\u0430\u0447\u0430\u0442\u044C \u043D\u043E\u0432\u044B\u0439 setup" }) })] }));
}
