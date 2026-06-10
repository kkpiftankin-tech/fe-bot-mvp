import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useMutation, useQuery } from "@tanstack/react-query";
import { getSetupProgress, runPipeline } from "../../../api/setup";
import { ApiError } from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";
export function RunPipelineStep() {
    const { setupJobId, setStep } = useWizardStore();
    const progressQuery = useQuery({
        queryKey: ["progress", setupJobId],
        queryFn: () => {
            if (!setupJobId)
                throw new Error("no setup_job_id");
            return getSetupProgress(setupJobId);
        },
        enabled: !!setupJobId,
        refetchInterval: (q) => {
            const data = q.state.data;
            if (!data)
                return 2000;
            const terminal = ["ready", "failed", "cancelled", "review_required"];
            return terminal.includes(data.status) ? false : 2000;
        },
    });
    const runMutation = useMutation({
        mutationFn: () => {
            if (!setupJobId)
                throw new Error("no setup_job_id");
            return runPipeline(setupJobId);
        },
    });
    const result = runMutation.data;
    const errorMessage = runMutation.error instanceof ApiError
        ? runMutation.error.message
        : runMutation.error?.message;
    return (_jsxs("div", { children: [_jsx("h2", { children: "\u0428\u0430\u0433 3. \u0417\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C pipeline" }), _jsx("p", { className: "text-muted", children: "Pipeline \u043F\u0440\u043E\u0445\u043E\u0434\u0438\u0442: parsing \u2192 sections_extracted \u2192 rag_cards_generating \u2192 metadata_validating \u2192 (review_required \u0418\u041B\u0418 chunking \u2192 embedding \u2192 indexing)." }), _jsx("div", { className: "btn-row", children: _jsx("button", { className: "btn", onClick: () => runMutation.mutate(), disabled: runMutation.isPending, "data-testid": "submit-run", children: runMutation.isPending ? "Запускаем…" : "Запустить pipeline" }) }), errorMessage && (_jsx("div", { className: "error-text", "data-testid": "run-error", children: errorMessage })), progressQuery.data && (_jsxs("div", { style: { marginTop: 24 }, children: [_jsx("div", { className: "progress-bar", children: _jsx("div", { style: { width: `${progressQuery.data.progress_percent}%` } }) }), _jsxs("div", { className: "text-muted", "data-testid": "progress-status", children: ["\u0421\u0442\u0430\u0442\u0443\u0441: ", _jsx("strong", { children: progressQuery.data.status }), " \u00B7", " ", progressQuery.data.progress_percent.toFixed(0), "%", progressQuery.data.current_step && (_jsxs(_Fragment, { children: [" \u00B7 \u0448\u0430\u0433: ", progressQuery.data.current_step] })), "\u00B7 \u043E\u0448\u0438\u0431\u043E\u043A: ", progressQuery.data.error_count, ", \u043F\u0440\u0435\u0434\u0443\u043F\u0440\u0435\u0436\u0434\u0435\u043D\u0438\u0439:", " ", progressQuery.data.warning_count] })] })), result && (_jsxs("div", { style: { marginTop: 24 }, children: [_jsx("h3", { children: "\u0421\u0432\u043E\u0434\u043A\u0430 pipeline" }), _jsxs("div", { className: "kv-grid", children: [_jsx("div", { className: "key", children: "\u0424\u0438\u043D\u0430\u043B\u044C\u043D\u044B\u0439 \u0441\u0442\u0430\u0442\u0443\u0441" }), _jsx("div", { "data-testid": "result-final-status", children: result.final_status }), _jsx("div", { className: "key", children: "\u0414\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B" }), _jsxs("div", { children: [result.documents_parsed, "/", result.documents_total, " \u0440\u0430\u0441\u043F\u0430\u0440\u0441\u0435\u043D\u043E,", " ", result.documents_failed, " \u0441 \u043E\u0448\u0438\u0431\u043A\u043E\u0439"] }), _jsx("div", { className: "key", children: "\u0421\u0435\u043A\u0446\u0438\u0438" }), _jsx("div", { children: result.sections_extracted }), _jsx("div", { className: "key", children: "\u0421\u0433\u0435\u043D\u0435\u0440\u0438\u0440\u043E\u0432\u0430\u043D\u043E \u043A\u0430\u0440\u0442\u043E\u0447\u0435\u043A" }), _jsx("div", { children: result.cards_generated }), _jsx("div", { className: "key", children: "\u0422\u0440\u0435\u0431\u0443\u044E\u0442 review" }), _jsx("div", { children: result.cards_review_required }), _jsx("div", { className: "key", children: "Auto-approved" }), _jsx("div", { children: result.cards_approved_auto }), _jsx("div", { className: "key", children: "Chunks" }), _jsxs("div", { children: [result.chunks_indexed, "/", result.chunks_total, " \u043F\u0440\u043E\u0438\u043D\u0434\u0435\u043A\u0441\u0438\u0440\u043E\u0432\u0430\u043D\u043E"] }), result.vector_index && (_jsxs(_Fragment, { children: [_jsx("div", { className: "key", children: "Vector index" }), _jsxs("div", { children: [result.vector_index.index_version, " \u00B7", " ", result.vector_index.status] })] })), result.errors.length > 0 && (_jsxs(_Fragment, { children: [_jsx("div", { className: "key", children: "\u041E\u0448\u0438\u0431\u043A\u0438" }), _jsx("div", { children: _jsx("ul", { style: { margin: 0, paddingLeft: 16 }, children: result.errors.map((e) => (_jsx("li", { children: e }, e))) }) })] }))] }), _jsx("div", { className: "btn-row", children: result.cards_review_required > 0 ? (_jsx("button", { className: "btn", onClick: () => setStep("review"), "data-testid": "continue-to-review", children: "\u041A \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0435 \u043A\u0430\u0440\u0442\u043E\u0447\u0435\u043A \u2192" })) : (_jsx("button", { className: "btn", onClick: () => setStep("tests"), "data-testid": "continue-to-tests", children: "\u041A retrieval-tests \u2192" })) })] }))] }));
}
