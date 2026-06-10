import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { createSetupJob } from "../../../api/setup";
import { ApiError } from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";
export function CreateJobStep() {
    const setSetupJobId = useWizardStore((s) => s.setSetupJobId);
    const [projectName, setProjectName] = useState("");
    const [domain, setDomain] = useState("");
    const [description, setDescription] = useState("");
    const mutation = useMutation({
        mutationFn: () => createSetupJob({
            project_name: projectName,
            domain: domain || undefined,
            description: description || undefined,
        }),
        onSuccess: (job) => setSetupJobId(job.setup_job_id, job.project_name),
    });
    const errorMessage = mutation.error instanceof ApiError
        ? mutation.error.message
        : mutation.error?.message;
    return (_jsxs("div", { children: [_jsx("h2", { children: "\u0428\u0430\u0433 1. \u0421\u043E\u0437\u0434\u0430\u0442\u044C setup job" }), _jsx("p", { className: "text-muted", children: "\u0414\u0430\u0439\u0442\u0435 \u043F\u0440\u043E\u0435\u043A\u0442\u0443 \u0438\u043C\u044F \u2014 \u043E\u043D\u043E \u0441\u0442\u0430\u043D\u0435\u0442 \u0438\u0434\u0435\u043D\u0442\u0438\u0444\u0438\u043A\u0430\u0442\u043E\u0440\u043E\u043C knowledge base." }), _jsxs("form", { onSubmit: (e) => {
                    e.preventDefault();
                    mutation.mutate();
                }, children: [_jsxs("div", { className: "form-group", children: [_jsx("label", { htmlFor: "project_name", children: "\u041D\u0430\u0437\u0432\u0430\u043D\u0438\u0435 \u043F\u0440\u043E\u0435\u043A\u0442\u0430 (\u2265 3 \u0441\u0438\u043C\u0432\u043E\u043B\u043E\u0432)" }), _jsx("input", { id: "project_name", "data-testid": "project-name", value: projectName, onChange: (e) => setProjectName(e.target.value), required: true, minLength: 3, maxLength: 128 })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { htmlFor: "domain", children: "\u0414\u043E\u043C\u0435\u043D (\u043E\u043F\u0446\u0438\u043E\u043D\u0430\u043B\u044C\u043D\u043E)" }), _jsx("input", { id: "domain", value: domain, onChange: (e) => setDomain(e.target.value), placeholder: "\u043D\u0430\u043F\u0440\u0438\u043C\u0435\u0440, naval / fintech / healthcare" })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { htmlFor: "description", children: "\u041E\u043F\u0438\u0441\u0430\u043D\u0438\u0435 (\u043E\u043F\u0446\u0438\u043E\u043D\u0430\u043B\u044C\u043D\u043E)" }), _jsx("textarea", { id: "description", value: description, onChange: (e) => setDescription(e.target.value), rows: 3 })] }), _jsx("div", { className: "btn-row", children: _jsx("button", { className: "btn", type: "submit", disabled: mutation.isPending || projectName.length < 3, "data-testid": "submit-create", children: mutation.isPending ? "Создаём…" : "Создать job" }) }), errorMessage && (_jsx("div", { className: "error-text", "data-testid": "create-error", children: errorMessage })), mutation.isSuccess && mutation.data && (_jsxs("div", { className: "banner banner-success", style: { marginTop: 16 }, "data-testid": "create-success", children: ["Job \u0441\u043E\u0437\u0434\u0430\u043D: ", mutation.data.setup_job_id, ". \u041F\u0435\u0440\u0435\u0445\u043E\u0434\u0438\u0442\u0435 \u043A \u0448\u0430\u0433\u0443 2."] }))] })] }));
}
