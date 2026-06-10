import { apiRequest } from "./client";
// ----- Jobs -----
export function createSetupJob(request) {
    return apiRequest("/setup/jobs", { method: "POST", body: request });
}
export function getSetupJob(setupJobId) {
    return apiRequest(`/setup/${setupJobId}`);
}
export function getSetupProgress(setupJobId) {
    return apiRequest(`/setup/${setupJobId}/progress`);
}
export function cancelSetupJob(setupJobId) {
    return apiRequest(`/setup/${setupJobId}/cancel`, { method: "POST" });
}
// ----- Documents -----
export function uploadDocuments(setupJobId, files, duplicateStrategy = "skip") {
    const formData = new FormData();
    for (const file of files) {
        formData.append("files", file);
    }
    return apiRequest(`/setup/${setupJobId}/documents`, {
        method: "POST",
        formData,
        query: { duplicate_strategy: duplicateStrategy },
    });
}
export function listDocuments(setupJobId) {
    return apiRequest(`/setup/${setupJobId}/documents`);
}
// ----- Pipeline -----
export function runPipeline(setupJobId) {
    return apiRequest(`/setup/${setupJobId}/run`, { method: "POST" });
}
export function reindexCards(setupJobId) {
    return apiRequest(`/setup/${setupJobId}/reindex`, { method: "POST" });
}
export function listRAGCards(setupJobId, options = {}) {
    return apiRequest(`/setup/${setupJobId}/rag-cards`, {
        query: {
            card_status: options.cardStatus,
            doc_type: options.docType,
            confidence_level: options.confidenceLevel,
            include: options.includeBody ? "body" : undefined,
        },
    });
}
export function reviewRAGCard(setupJobId, docId, request) {
    return apiRequest(`/setup/${setupJobId}/rag-cards/${encodeURIComponent(docId)}/review`, { method: "POST", body: request });
}
// ----- Retrieval tests / Publish / Report -----
export function runRetrievalTests(setupJobId, request) {
    return apiRequest(`/setup/${setupJobId}/retrieval-tests`, {
        method: "POST",
        body: request,
    });
}
export function publishKB(setupJobId, request) {
    return apiRequest(`/setup/${setupJobId}/publish`, {
        method: "POST",
        body: request,
    });
}
export function getReport(setupJobId) {
    return apiRequest(`/setup/${setupJobId}/report`);
}
