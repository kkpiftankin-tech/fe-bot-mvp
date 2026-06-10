import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listDocuments, uploadDocuments } from "../../../api/setup";
import { ApiError } from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";
export function UploadDocumentsStep() {
    const { setupJobId, setStep } = useWizardStore();
    const qc = useQueryClient();
    const [selected, setSelected] = useState([]);
    const docsQuery = useQuery({
        queryKey: ["docs", setupJobId],
        queryFn: () => {
            if (!setupJobId)
                throw new Error("no setup_job_id");
            return listDocuments(setupJobId);
        },
        enabled: !!setupJobId,
    });
    const uploadMutation = useMutation({
        mutationFn: () => {
            if (!setupJobId)
                throw new Error("no setup_job_id");
            return uploadDocuments(setupJobId, selected);
        },
        onSuccess: async () => {
            setSelected([]);
            await qc.invalidateQueries({ queryKey: ["docs", setupJobId] });
        },
    });
    const errorMessage = uploadMutation.error instanceof ApiError
        ? uploadMutation.error.message
        : uploadMutation.error?.message;
    const documents = docsQuery.data?.documents ?? [];
    return (_jsxs("div", { children: [_jsx("h2", { children: "\u0428\u0430\u0433 2. \u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044C \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B" }), _jsx("p", { className: "text-muted", children: "\u041F\u043E\u0434\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u044E\u0442\u0441\u044F: Markdown (.md), Plain Text (.txt), CSV, JSON. \u0414\u0443\u0431\u043B\u0438\u043A\u0430\u0442\u044B \u043F\u043E checksum SHA-256 \u043F\u0440\u043E\u043F\u0443\u0441\u043A\u0430\u044E\u0442\u0441\u044F." }), _jsxs("div", { className: "form-group", children: [_jsx("label", { htmlFor: "files", children: "\u0412\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u0444\u0430\u0439\u043B\u044B" }), _jsx("input", { id: "files", type: "file", multiple: true, accept: ".md,.txt,.csv,.json,text/markdown,text/plain,text/csv,application/json", onChange: (e) => setSelected(Array.from(e.target.files ?? [])), "data-testid": "file-input" })] }), selected.length > 0 && (_jsx("ul", { className: "text-muted", children: selected.map((f) => (_jsxs("li", { children: [f.name, " \u2014 ", (f.size / 1024).toFixed(1), " KB"] }, f.name))) })), _jsxs("div", { className: "btn-row", children: [_jsx("button", { className: "btn", onClick: () => uploadMutation.mutate(), disabled: selected.length === 0 || uploadMutation.isPending, "data-testid": "submit-upload", children: uploadMutation.isPending ? "Загружаем…" : "Загрузить" }), _jsx("button", { className: "btn btn-secondary", onClick: () => setStep("run"), disabled: documents.length === 0, "data-testid": "continue-to-run", children: "\u0414\u0430\u043B\u0435\u0435 \u2192" })] }), errorMessage && (_jsx("div", { className: "error-text", "data-testid": "upload-error", children: errorMessage })), _jsxs("h3", { style: { marginTop: 24 }, children: ["\u0417\u0430\u0433\u0440\u0443\u0436\u0435\u043D\u043D\u044B\u0435 \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B (", documents.length, ")"] }), docsQuery.isLoading ? (_jsx("p", { className: "text-muted", children: "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043C \u0441\u043F\u0438\u0441\u043E\u043A\u2026" })) : documents.length === 0 ? (_jsx("p", { className: "text-muted", children: "\u041F\u043E\u043A\u0430 \u043D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043D\u043E." })) : (_jsx("ul", { "data-testid": "doc-list", children: documents.map((d) => (_jsxs("li", { children: [_jsx("strong", { children: d.filename }), " (", d.content_type, ",", " ", (d.size_bytes / 1024).toFixed(1), " KB) \u2014 ", d.status] }, d.source_document_id))) }))] }));
}
