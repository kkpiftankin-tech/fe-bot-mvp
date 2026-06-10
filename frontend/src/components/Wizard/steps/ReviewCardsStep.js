import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listRAGCards, reviewRAGCard } from "../../../api/setup";
import { ApiError, } from "../../../api/types";
import { useWizardStore } from "../../../store/wizardStore";
function badgeClass(status) {
    if (status === "review_required")
        return "badge badge-review";
    if (status === "approved" || status === "metadata_validated")
        return "badge badge-approved";
    if (status === "deprecated")
        return "badge badge-deprecated";
    if (status === "published")
        return "badge badge-published";
    return "badge";
}
export function ReviewCardsStep() {
    const { setupJobId, setStep } = useWizardStore();
    const qc = useQueryClient();
    const [filterStatus, setFilterStatus] = useState("review_required");
    const [openCardId, setOpenCardId] = useState(null);
    const cardsQuery = useQuery({
        queryKey: ["cards", setupJobId, filterStatus],
        queryFn: () => {
            if (!setupJobId)
                throw new Error("no setup_job_id");
            return listRAGCards(setupJobId, {
                cardStatus: filterStatus || undefined,
                includeBody: true,
            });
        },
        enabled: !!setupJobId,
    });
    const reviewMutation = useMutation({
        mutationFn: async (vars) => {
            if (!setupJobId)
                throw new Error("no setup_job_id");
            return reviewRAGCard(setupJobId, vars.docId, {
                decision: vars.decision,
                comment: vars.comment,
                updated_title: vars.title,
                updated_body_markdown: vars.body,
            });
        },
        onSuccess: async () => {
            setOpenCardId(null);
            await qc.invalidateQueries({ queryKey: ["cards", setupJobId] });
        },
    });
    const cards = cardsQuery.data?.cards ?? [];
    return (_jsxs("div", { children: [_jsx("h2", { children: "\u0428\u0430\u0433 4. \u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u043A\u0430\u0440\u0442\u043E\u0447\u043A\u0438" }), _jsxs("p", { className: "text-muted", children: ["\u041A\u0430\u0440\u0442\u043E\u0447\u043A\u0438 \u0432 \u0441\u0442\u0430\u0442\u0443\u0441\u0435 ", _jsx("code", { children: "review_required" }), " \u0442\u0440\u0435\u0431\u0443\u044E\u0442 HITL.", _jsx("br", {}), "Approve \u2192 \u043E\u0434\u043E\u0431\u0440\u0438\u0442\u044C \u00B7 Reject \u2192 \u0443\u0434\u0430\u043B\u0438\u0442\u044C \u00B7 Edit \u2192 \u043D\u043E\u0432\u0430\u044F \u0432\u0435\u0440\u0441\u0438\u044F \u00B7 Regenerate \u2192 \u0432\u0435\u0440\u043D\u0443\u0442\u044C \u0432 draft."] }), _jsxs("div", { className: "row", style: { marginBottom: 12 }, children: [_jsxs("label", { children: ["\u0424\u0438\u043B\u044C\u0442\u0440 \u0441\u0442\u0430\u0442\u0443\u0441:", " ", _jsxs("select", { value: filterStatus, onChange: (e) => setFilterStatus(e.target.value), "data-testid": "status-filter", children: [_jsx("option", { value: "", children: "\u0412\u0441\u0435" }), _jsx("option", { value: "review_required", children: "review_required" }), _jsx("option", { value: "approved", children: "approved" }), _jsx("option", { value: "metadata_validated", children: "metadata_validated" }), _jsx("option", { value: "published", children: "published" }), _jsx("option", { value: "deprecated", children: "deprecated" })] })] }), _jsxs("span", { className: "text-muted", children: ["\u041D\u0430\u0439\u0434\u0435\u043D\u043E: ", cards.length] }), _jsx("button", { className: "btn btn-secondary", onClick: () => setStep("tests"), style: { marginLeft: "auto" }, "data-testid": "continue-to-tests", children: "\u041A retrieval-tests \u2192" })] }), cardsQuery.isLoading ? (_jsx("p", { className: "text-muted", children: "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043C \u043A\u0430\u0440\u0442\u043E\u0447\u043A\u0438\u2026" })) : cards.length === 0 ? (_jsx("p", { className: "text-muted", "data-testid": "no-cards", children: "\u041D\u0435\u0442 \u043A\u0430\u0440\u0442\u043E\u0447\u0435\u043A, \u0441\u043E\u043E\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0443\u044E\u0449\u0438\u0445 \u0444\u0438\u043B\u044C\u0442\u0440\u0443." })) : (_jsx("ul", { className: "card-list", "data-testid": "card-list", children: cards.map((card) => (_jsx("li", { className: "card-item", children: _jsx(CardRow, { card: card, isOpen: openCardId === card.doc_id, onToggle: () => setOpenCardId(openCardId === card.doc_id ? null : card.doc_id), onAction: (decision, payload) => reviewMutation.mutate({
                            docId: card.doc_id,
                            decision,
                            comment: payload.comment,
                            title: payload.title,
                            body: payload.body,
                        }), isPending: reviewMutation.isPending }) }, card.doc_id))) })), reviewMutation.error && (_jsx("div", { className: "banner banner-error", style: { marginTop: 16 }, "data-testid": "review-error", children: reviewMutation.error instanceof ApiError
                    ? reviewMutation.error.message
                    : "Ошибка review" }))] }));
}
function CardRow({ card, isOpen, onToggle, onAction, isPending, }) {
    const [comment, setComment] = useState("");
    const [editTitle, setEditTitle] = useState(card.title);
    const [editBody, setEditBody] = useState(card.body_markdown ?? "");
    return (_jsxs(_Fragment, { children: [_jsxs("header", { children: [_jsxs("div", { children: [_jsx("strong", { children: card.title }), " ", _jsx("span", { className: badgeClass(card.status), "data-testid": `status-${card.doc_id}`, children: card.status }), _jsxs("div", { className: "meta", children: [card.doc_id, " \u00B7 ", card.doc_type, " \u00B7 v", card.version, card.confidence_level && _jsxs(_Fragment, { children: [" \u00B7 conf=", card.confidence_level] })] })] }), _jsx("button", { className: "btn btn-secondary", onClick: onToggle, "data-testid": `toggle-${card.doc_id}`, children: isOpen ? "Свернуть" : "Развернуть" })] }), isOpen && (_jsxs("div", { style: { marginTop: 12 }, children: [card.body_markdown && (_jsx("pre", { style: {
                            background: "#f3f4f6",
                            padding: 12,
                            borderRadius: 8,
                            overflow: "auto",
                            maxHeight: 240,
                            fontSize: 12,
                        }, children: card.body_markdown })), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "\u041A\u043E\u043C\u043C\u0435\u043D\u0442\u0430\u0440\u0438\u0439 (\u043E\u043F\u0446\u0438\u043E\u043D\u0430\u043B\u044C\u043D\u043E)" }), _jsx("input", { value: comment, onChange: (e) => setComment(e.target.value), "data-testid": `comment-${card.doc_id}` })] }), _jsxs("div", { className: "btn-row", children: [_jsx("button", { className: "btn", disabled: isPending, onClick: () => onAction("approve", { comment }), "data-testid": `approve-${card.doc_id}`, children: "Approve" }), _jsx("button", { className: "btn btn-danger", disabled: isPending, onClick: () => onAction("reject", { comment }), "data-testid": `reject-${card.doc_id}`, children: "Reject" }), _jsx("button", { className: "btn btn-secondary", disabled: isPending, onClick: () => onAction("regenerate", { comment }), "data-testid": `regenerate-${card.doc_id}`, children: "Regenerate" })] }), _jsxs("details", { style: { marginTop: 16 }, children: [_jsx("summary", { children: "Edit (\u043D\u043E\u0432\u0430\u044F \u0432\u0435\u0440\u0441\u0438\u044F)" }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "\u041D\u043E\u0432\u044B\u0439 title" }), _jsx("input", { value: editTitle, onChange: (e) => setEditTitle(e.target.value) })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "\u041D\u043E\u0432\u044B\u0439 body markdown" }), _jsx("textarea", { value: editBody, onChange: (e) => setEditBody(e.target.value), rows: 6 })] }), _jsx("div", { className: "btn-row", children: _jsx("button", { className: "btn", disabled: isPending ||
                                        (editTitle === card.title &&
                                            editBody === (card.body_markdown ?? "")), onClick: () => onAction("edit", {
                                        comment,
                                        title: editTitle !== card.title ? editTitle : undefined,
                                        body: editBody !== (card.body_markdown ?? "")
                                            ? editBody
                                            : undefined,
                                    }), "data-testid": `edit-${card.doc_id}`, children: "\u041F\u0440\u0438\u043C\u0435\u043D\u0438\u0442\u044C edit" }) })] })] }))] }));
}
