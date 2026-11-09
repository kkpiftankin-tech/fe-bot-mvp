// SETUP-12 / T-S12-070: vitest tests для TaxonomyTreeView.

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { resetMockState, server } from "../../../test/msw";
import { TaxonomyTreeView } from "../TaxonomyTreeView";

beforeEach(() => {
  resetMockState();
});

const TREE_RESPONSE = {
  version: {
    version_id: "v1.0.0",
    created_at: "2026-06-26T00:00:00Z",
    description: "Bootstrap",
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
        display_name_en: "Task",
        description: "ML-задача.",
        doc_type_hint: "task_card",
        auto_created: false,
        usage_count: 3,
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
            description: "Противовоздушная оборона.",
            doc_type_hint: null,
            auto_created: true,
            usage_count: 1,
          },
          children: [],
        },
      ],
    },
    {
      node: {
        version_id: "v1.0.0",
        level: 0,
        parent_path: "",
        bit_index: 1,
        class_slug: "schema",
        display_name_ru: "Схема данных",
        display_name_en: "Data schema",
        description: "Схема данных.",
        doc_type_hint: "schema_card",
        auto_created: false,
        usage_count: 0,
      },
      children: [],
    },
  ],
  total_classes: 3,
  auto_created_count: 1,
};

describe("TaxonomyTreeView", () => {
  it("renders active version metadata", async () => {
    server.use(
      http.get("/api/v1/taxonomy/tree", () => HttpResponse.json(TREE_RESPONSE)),
    );
    renderWithProviders(<TaxonomyTreeView />);
    await waitFor(() =>
      expect(screen.getByTestId("taxonomy-tree")).toBeInTheDocument(),
    );
    expect(screen.getByText("v1.0.0")).toBeInTheDocument();
    expect(screen.getByText("Bootstrap")).toBeInTheDocument();
    expect(screen.getByText("2 / 10")).toBeInTheDocument();
  });

  it("renders all L0 root classes", async () => {
    server.use(
      http.get("/api/v1/taxonomy/tree", () => HttpResponse.json(TREE_RESPONSE)),
    );
    renderWithProviders(<TaxonomyTreeView />);
    await waitFor(() => {
      expect(screen.getByTestId("tax-node-task")).toBeInTheDocument();
    });
    expect(screen.getByTestId("tax-node-schema")).toBeInTheDocument();
  });

  it("expands root by default and shows child", async () => {
    server.use(
      http.get("/api/v1/taxonomy/tree", () => HttpResponse.json(TREE_RESPONSE)),
    );
    renderWithProviders(<TaxonomyTreeView />);
    await waitFor(() => {
      expect(screen.getByTestId("tax-node-pvo")).toBeInTheDocument();
    });
  });

  it("shows usage badge when usage_count > 0", async () => {
    server.use(
      http.get("/api/v1/taxonomy/tree", () => HttpResponse.json(TREE_RESPONSE)),
    );
    renderWithProviders(<TaxonomyTreeView />);
    await waitFor(() =>
      expect(screen.getByTestId("tax-usage-task")).toHaveTextContent("uses: 3"),
    );
    // schema usage_count=0 → нет badge'а
    expect(screen.queryByTestId("tax-usage-schema")).not.toBeInTheDocument();
  });

  it("toggles expand/collapse on child node", async () => {
    server.use(
      http.get("/api/v1/taxonomy/tree", () => HttpResponse.json(TREE_RESPONSE)),
    );
    renderWithProviders(<TaxonomyTreeView />);
    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByTestId("tax-node-pvo")).toBeInTheDocument();
    });
    const collapseTask = screen.getByTestId("tax-expand-task");
    await user.click(collapseTask);
    // Дочерний узел теперь скрыт
    expect(screen.queryByTestId("tax-node-pvo")).not.toBeInTheDocument();
  });

  it("shows empty-state for empty taxonomy", async () => {
    server.use(
      http.get("/api/v1/taxonomy/tree", () =>
        HttpResponse.json({
          version: TREE_RESPONSE.version,
          roots: [],
          total_classes: 0,
          auto_created_count: 0,
        }),
      ),
    );
    renderWithProviders(<TaxonomyTreeView />);
    await waitFor(() =>
      expect(screen.getByTestId("taxonomy-empty-roots")).toBeInTheDocument(),
    );
  });

  it("shows error banner when API fails", async () => {
    server.use(
      http.get(
        "/api/v1/taxonomy/tree",
        () => new HttpResponse(null, { status: 500 }),
      ),
    );
    renderWithProviders(<TaxonomyTreeView />);
    await waitFor(() =>
      expect(screen.getByTestId("taxonomy-error")).toBeInTheDocument(),
    );
  });
});
