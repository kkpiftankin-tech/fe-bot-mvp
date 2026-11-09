// SETUP-12 (T-S12-070): Taxonomy read-only API client.

import { apiRequest } from "./client";

export interface TaxonomyVersionDTO {
  version_id: string;
  created_at: string;
  description: string;
  is_active: boolean;
}

export interface TaxonomyNodeDTO {
  version_id: string;
  level: number;
  parent_path: string;
  bit_index: number;
  class_slug: string;
  display_name_ru: string;
  display_name_en: string;
  description: string;
  doc_type_hint: string | null;
  auto_created: boolean;
  usage_count: number;
}

export interface TaxonomyTreeNodeDTO {
  node: TaxonomyNodeDTO;
  children: TaxonomyTreeNodeDTO[];
}

export interface TaxonomyTreeResponse {
  version: TaxonomyVersionDTO;
  roots: TaxonomyTreeNodeDTO[];
  total_classes: number;
  auto_created_count: number;
}

export interface TaxonomyVersionListResponse {
  versions: TaxonomyVersionDTO[];
  active_version_id: string | null;
}

export function listTaxonomyVersions(): Promise<TaxonomyVersionListResponse> {
  return apiRequest("/taxonomy/versions");
}

export function getActiveTaxonomyTree(): Promise<TaxonomyTreeResponse> {
  return apiRequest("/taxonomy/tree");
}

export function getTaxonomyTreeForVersion(
  versionId: string,
): Promise<TaxonomyTreeResponse> {
  return apiRequest(`/taxonomy/versions/${encodeURIComponent(versionId)}/tree`);
}

// SETUP-12: ClassificationState frontend-mirror (поле в ParsedSection).
// Canonical определение живёт в api/types.ts, здесь re-export для
// backward-compat с существующими importer'ами.
export type { ClassificationStateDTO } from "./types";
