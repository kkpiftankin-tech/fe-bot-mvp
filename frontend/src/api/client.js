import { ApiError } from "./types";
const DEFAULT_BASE_URL = "/api/v1";
let authHeaders = { userId: "u1", roles: "user" };
export function setAuthHeaders(headers) {
    authHeaders = headers;
}
export function getAuthHeaders() {
    return authHeaders;
}
function buildUrl(path, query) {
    const url = new URL(`${DEFAULT_BASE_URL}${path}`, window.location.origin);
    if (query) {
        for (const [key, value] of Object.entries(query)) {
            if (value !== undefined && value !== null) {
                url.searchParams.set(key, String(value));
            }
        }
    }
    return `${url.pathname}${url.search}`;
}
export async function apiRequest(path, options = {}) {
    const { method = "GET", body, headers = {}, formData, query, } = options;
    const url = buildUrl(path, query);
    const requestHeaders = {
        "X-User-Id": authHeaders.userId,
        "X-Roles": authHeaders.roles,
        ...headers,
    };
    let finalBody;
    if (formData) {
        finalBody = formData;
    }
    else if (body !== undefined) {
        finalBody = JSON.stringify(body);
        requestHeaders["Content-Type"] = "application/json";
    }
    const response = await fetch(url, {
        method,
        headers: requestHeaders,
        body: finalBody,
    });
    const contentType = response.headers.get("content-type") ?? "";
    const isJson = contentType.includes("application/json");
    let parsedBody = null;
    if (isJson) {
        try {
            parsedBody = await response.json();
        }
        catch {
            parsedBody = null;
        }
    }
    if (!response.ok) {
        const errorMessage = (typeof parsedBody === "object" &&
            parsedBody !== null &&
            "detail" in parsedBody &&
            typeof parsedBody.detail === "string"
            ? parsedBody.detail
            : `HTTP ${response.status}`);
        throw new ApiError(response.status, errorMessage, parsedBody);
    }
    return parsedBody;
}
