import { apiRequest } from "./client";
import type {
  ClassifierNodeDetailsResponse,
  ClassifierNodeDTO,
  ClassifierTreeSummaryResponse,
  CreateChildNodeRequest,
  DeleteNodeResponse,
  GenerateDescriptionResponse,
  UpdateNodeRequest,
} from "./types";

export function getClassifierTree(): Promise<ClassifierTreeSummaryResponse> {
  return apiRequest("/classifier/tree");
}

export function getClassifierNode(
  nodeId: string,
): Promise<ClassifierNodeDetailsResponse> {
  return apiRequest(`/classifier/tree/nodes/${encodeURIComponent(nodeId)}`);
}

export function createClassifierChild(
  parentId: string,
  request: CreateChildNodeRequest,
): Promise<ClassifierNodeDTO> {
  return apiRequest(
    `/classifier/tree/nodes/${encodeURIComponent(parentId)}/children`,
    { method: "POST", body: request },
  );
}

export function updateClassifierNode(
  nodeId: string,
  request: UpdateNodeRequest,
): Promise<ClassifierNodeDTO> {
  return apiRequest(`/classifier/tree/nodes/${encodeURIComponent(nodeId)}`, {
    method: "PATCH",
    body: request,
  });
}

export function deleteClassifierNode(
  nodeId: string,
): Promise<DeleteNodeResponse> {
  return apiRequest(`/classifier/tree/nodes/${encodeURIComponent(nodeId)}`, {
    method: "DELETE",
  });
}

export function generateClassifierDescription(
  nodeId: string,
): Promise<GenerateDescriptionResponse> {
  return apiRequest(
    `/classifier/tree/nodes/${encodeURIComponent(nodeId)}/generate-description`,
    { method: "POST" },
  );
}
