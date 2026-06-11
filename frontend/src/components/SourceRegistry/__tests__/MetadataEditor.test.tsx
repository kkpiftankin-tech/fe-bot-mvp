/**
 * Тесты MetadataEditor (SETUP-03 / T-S03-026).
 */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { MetadataEditor } from "../MetadataEditor";

describe("MetadataEditor", () => {
  it("renders form fields", async () => {
    renderWithProviders(
      <MetadataEditor setupJobId="s1" sourceDocumentId="src_001" />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("tags-input")).toBeInTheDocument();
    });
    expect(screen.getByTestId("description-input")).toBeInTheDocument();
    expect(screen.getByTestId("owner-note-input")).toBeInTheDocument();
  });

  it("submits PATCH on Save click", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <MetadataEditor setupJobId="s1" sourceDocumentId="src_001" />,
    );
    const tagsInput = (await screen.findByTestId("tags-input")) as HTMLInputElement;
    await user.clear(tagsInput);
    await user.type(tagsInput, "naval, schema");
    await user.click(screen.getByTestId("metadata-save"));
    await waitFor(() => {
      expect(screen.getByTestId("metadata-success")).toBeInTheDocument();
    });
  });
});
