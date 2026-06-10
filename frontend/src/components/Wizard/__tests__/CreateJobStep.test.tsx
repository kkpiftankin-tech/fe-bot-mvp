import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { resetMockState, server } from "../../../test/msw";
import { useWizardStore } from "../../../store/wizardStore";
import { CreateJobStep } from "../steps/CreateJobStep";

beforeEach(() => {
  useWizardStore.getState().reset();
  resetMockState();
});
afterEach(() => useWizardStore.getState().reset());

describe("CreateJobStep", () => {
  it("creates a job and advances wizard to upload step", async () => {
    renderWithProviders(<CreateJobStep />);
    const user = userEvent.setup();

    await user.type(screen.getByTestId("project-name"), "Test KB");
    await user.click(screen.getByTestId("submit-create"));

    await waitFor(() =>
      expect(screen.getByTestId("create-success")).toBeInTheDocument(),
    );
    const state = useWizardStore.getState();
    expect(state.setupJobId).toMatch(/^setup_/);
    expect(state.projectName).toBe("Test KB");
    expect(state.currentStep).toBe("upload");
  });

  it("disables submit when project_name is too short", () => {
    renderWithProviders(<CreateJobStep />);
    const submit = screen.getByTestId("submit-create");
    expect(submit).toBeDisabled();
  });

  it("shows error message when API returns 422", async () => {
    server.use(
      http.post("/api/v1/setup/jobs", () =>
        HttpResponse.json(
          { detail: "project_name too short" },
          { status: 422 },
        ),
      ),
    );
    renderWithProviders(<CreateJobStep />);
    const user = userEvent.setup();
    await user.type(screen.getByTestId("project-name"), "abc");
    await user.click(screen.getByTestId("submit-create"));

    await waitFor(() =>
      expect(screen.getByTestId("create-error")).toHaveTextContent(
        "project_name too short",
      ),
    );
  });
});
