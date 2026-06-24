import { apiRequest } from "./client";
import type {
  ChunkManifestResponse,
  ChunkPreviewResponse,
  ChunkingRunResponse,
} from "./types";

export function runChunking(setupJobId: string): Promise<ChunkingRunResponse> {
  return apiRequest(`/setup/${setupJobId}/chunking/run`, {
    method: "POST",
    body: {},
  });
}

export function getChunkManifest(
  setupJobId: string,
): Promise<ChunkManifestResponse> {
  return apiRequest(`/setup/${setupJobId}/chunking/manifest`);
}

export function previewChunks(
  setupJobId: string,
  docId: string,
): Promise<ChunkPreviewResponse> {
  return apiRequest(
    `/setup/${setupJobId}/chunking/preview/${encodeURIComponent(docId)}`,
  );
}

export function refreshChunks(
  setupJobId: string,
  docId: string,
): Promise<ChunkPreviewResponse> {
  return apiRequest(
    `/setup/${setupJobId}/chunking/refresh/${encodeURIComponent(docId)}`,
    { method: "POST", body: {} },
  );
}
