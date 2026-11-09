// SETUP-13 / ADR-HTC-09: vitest tests для ClassifierResultBadge.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClassifierResultBadge } from "../ClassifierResultBadge";
import type { FragmentClassificationResult } from "../../../api/types";

describe("ClassifierResultBadge", () => {
  it("shows the legacy label when result is null (rule_based mode)", () => {
    render(<ClassifierResultBadge result={null} />);
    expect(screen.getByTestId("classifier-result-badge-legacy")).toHaveTextContent(
      "rule-based (legacy)",
    );
  });

  it("shows an unmatched badge when the path is empty", () => {
    const result: FragmentClassificationResult = {
      tree_id: "t1",
      path: [],
      reached_leaf: false,
    };
    render(<ClassifierResultBadge result={result} />);
    expect(screen.getByTestId("classifier-result-badge-unmatched")).toBeInTheDocument();
  });

  it("renders the full path with names and overall (minimum) confidence", () => {
    const result: FragmentClassificationResult = {
      tree_id: "asu_v1",
      path: [
        { node_id: "analitika", name: "Аналитика", confidence: 0.95, reason: "r1" },
        { node_id: "dnn", name: "DNN", confidence: 0.62, reason: "r2" },
      ],
      reached_leaf: true,
    };
    render(<ClassifierResultBadge result={result} />);
    const badge = screen.getByTestId("classifier-result-badge");
    expect(badge).toHaveTextContent("Аналитика");
    expect(badge).toHaveTextContent("DNN");
    expect(badge).toHaveTextContent("0.62");
    expect(
      screen.queryByTestId("classifier-result-badge-not-leaf"),
    ).not.toBeInTheDocument();
  });

  it("flags when the path did not reach a leaf", () => {
    const result: FragmentClassificationResult = {
      tree_id: "asu_v1",
      path: [{ node_id: "analitika", name: "Аналитика", confidence: 0.7, reason: "" }],
      reached_leaf: false,
    };
    render(<ClassifierResultBadge result={result} />);
    expect(screen.getByTestId("classifier-result-badge-not-leaf")).toBeInTheDocument();
  });
});
