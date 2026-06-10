import { ApiError } from "./types";

const DEFAULT_BASE_URL = "/api/v1";

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  formData?: FormData;
  query?: Record<string, string | number | boolean | undefined>;
}

export interface AuthHeaders {
  userId: string;
  roles: string;
}

let authHeaders: AuthHeaders = { userId: "u1", roles: "user" };

export function setAuthHeaders(headers: AuthHeaders): void {
  authHeaders = headers;
}

export function getAuthHeaders(): AuthHeaders {
  return authHeaders;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
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

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    method = "GET",
    body,
    headers = {},
    formData,
    query,
  } = options;

  const url = buildUrl(path, query);
  const requestHeaders: Record<string, string> = {
    "X-User-Id": authHeaders.userId,
    "X-Roles": authHeaders.roles,
    ...headers,
  };

  let finalBody: BodyInit | undefined;
  if (formData) {
    finalBody = formData;
  } else if (body !== undefined) {
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

  let parsedBody: unknown = null;
  if (isJson) {
    try {
      parsedBody = await response.json();
    } catch {
      parsedBody = null;
    }
  }

  if (!response.ok) {
    const errorMessage =
      (typeof parsedBody === "object" &&
        parsedBody !== null &&
        "detail" in parsedBody &&
        typeof (parsedBody as { detail: unknown }).detail === "string"
        ? (parsedBody as { detail: string }).detail
        : `HTTP ${response.status}`);
    throw new ApiError(response.status, errorMessage, parsedBody);
  }

  return parsedBody as T;
}
