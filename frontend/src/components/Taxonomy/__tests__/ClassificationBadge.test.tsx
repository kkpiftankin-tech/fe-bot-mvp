// SETUP-12 / T-S12-071: vitest tests для ClassificationBadge.

import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { resetMockState, server } from "../../../test/msw";
import { ClassificationBadge } from "../ClassificationBadge";
import type { ClassificationStateDTO } from "../../../api/taxonomy";

beforeEach(() => {
  resetMockState();
});

const TREE_FIXTURE = {
  version: {
    version_id: "v1.0.0",
    created_at: "2026-06-26T00:00:00Z",
    description: "",
    is_active: true,
  },
  roots: [
    {
      node: {
        version_id: "v1.0.0",
        level: 0,
        parent_path: "",
        bit_index: 0,
        class_slug: "task",
        display_name_ru: "Задача",
        display_name_en: "",
        description: "Задача.",
        doc_type_hint: "task_card",
        auto_created: false,
        usage_count: 0,
      },
      children: [
        {
          node: {
            version_id: "v1.0.0",
            level: 1,
            parent_path: "task",
            bit_index: 0,
            class_slug: "pvo",
            display_name_ru: "ПВО",
            display_name_en: "",
            description: "ПВО.",
            doc_type_hint: null,
            auto_created: true,
            usage_count: 0,
          },
          children: [
            {
              node: {
                version_id: "v1.0.0",
                level: 2,
                parent_path: "task.pvo",
                bit_index: 0,
                class_slug: "tracking",
                display_name_ru: "Сопровождение",
                display_name_en: "",
                description: "Tracking.",
                doc_type_hint: null,
                auto_created: true,
                usage_count: 0,
              },
              children: [],
            },
          ],
        },
      ],
    },
  ],
  total_classes: 3,
  auto_created_count: 2,
};

const _bitOffset = (level: number, bit: number) => 1 << (level * 10 + bit);

describe("ClassificationBadge", () => {
  it("shows 'rule-based' when state is null", () => {
    renderWithProviders(<ClassificationBadge state={null} />);
    expect(screen.getByTestId("classif-badge-legacy")).toHaveTextContent(
      "rule-based",
    );
  });

  it("shows 'unknown' when unknown_at_level=0", async () => {
    server.use(
      http.get("/api/v1/taxonomy/tree", () => HttpResponse.json(TREE_FIXTURE)),
    );
    const state: ClassificationStateDTO = {
      classification_bitmap: 0,
      primary_l0_idx: null,
      primary_l1_idx: null,
      unknown_at_level: 0,
      confidence_per_level: [0, 0, 0],
      confidence_per_bit: {},
      taxonomy_version_id: "v1.0.0",
      classification_method: "llm",
      auto_created_bits: [],
      llm_trace_ids: [],
    };
    renderWithProviders(<ClassificationBadge state={state} />);
    expect(screen.getByTestId("classif-badge-unknown")).toBeInTheDocument();
  });

  it("renders L0 path", async () => {
    server.use(
      http.get("/api/v1/taxonomy/tree", () => HttpResponse.json(TREE_FIXTURE)),
    );
    const state: ClassificationStateDTO = {
      classification_bitmap: _bitOffset(0, 0),
      primary_l0_idx: 0,
      primary_l1_idx: null,
      unknown_at_level: 1,
      confidence_per_level: [0.9, 0, 0],
      confidence_per_bit: { "0:0": 0.9 },
      taxonomy_version_id: "v1.0.0",
      classification_method: "llm",
      auto_created_bits: [],
      llm_trace_ids: [],
    };
    renderWithProviders(<ClassificationBadge state={state} />);
    await waitFor(() => {
      expect(screen.getByTestId("classif-badge")).toBeInTheDocument();
    });
    expect(screen.getByText("Задача")).toBeInTheDocument();
    // L1 cascading-indicator
    expect(screen.getByTestId("classif-cascading")).toHaveTextContent("L1");
  });

  it("renders full L0.L1.L2 path", async () => {
    server.use(
      http.get("/api/v1/taxonomy/tree", () => HttpResponse.json(TREE_FIXTURE)),
    );
    const state: ClassificationStateDTO = {
      classification_bitmap:
        _bitOffset(0, 0) | _bitOffset(1, 0) | _bitOffset(2, 0),
      primary_l0_idx: 0,
      primary_l1_idx: 0,
      unknown_at_level: null,
      confidence_per_level: [0.9, 0.85, 0.8],
      confidence_per_bit: { "0:0": 0.9, "1:0": 0.85, "2:0": 0.8 },
      taxonomy_version_id: "v1.0.0",
      classification_method: "llm",
      auto_created_bits: [],
      llm_trace_ids: [],
    };
    renderWithProviders(<ClassificationBadge state={state} />);
    await waitFor(() => {
      expect(screen.getByText("Задача")).toBeInTheDocument();
    });
    expect(screen.getByText("ПВО")).toBeInTheDocument();
    expect(screen.getByText("Сопровождение")).toBeInTheDocument();
    // unknown_at_level=null → нет cascading-tag
    expect(screen.queryByTestId("classif-cascading")).not.toBeInTheDocument();
  });
});
