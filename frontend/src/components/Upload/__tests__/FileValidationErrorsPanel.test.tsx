/**
 * Тесты FileValidationErrorsPanel (SETUP-02 / T-S02-021).
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FileValidationErrorsPanel } from "../FileValidationErrorsPanel";

describe("FileValidationErrorsPanel", () => {
  it("renders nothing if no errors", () => {
    const { container } = render(
      <FileValidationErrorsPanel
        clientInvalid={[]}
        clientBatchErrors={[]}
        serverErrors={[]}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows summary with counts", () => {
    render(
      <FileValidationErrorsPanel
        clientInvalid={[
          {
            file: new File(["x"], "bad.exe"),
            error: {
              filename: "bad.exe",
              error_code: "UNSUPPORTED_FILE_TYPE",
              message: "not allowed",
            },
          },
        ]}
        clientBatchErrors={[
          {
            filename: "",
            error_code: "BATCH_TOO_LARGE",
            message: "limit exceeded",
          },
        ]}
        serverErrors={[
          {
            filename: "huge.md",
            error_code: "FILE_TOO_LARGE",
            message: "100MB max",
          },
        ]}
      />,
    );
    const panel = screen.getByTestId("validation-errors-panel");
    expect(panel).toHaveTextContent("3");
    expect(panel).toHaveTextContent("клиент: 2");
    expect(panel).toHaveTextContent("сервер: 1");
  });

  it("expands to show per-file errors", async () => {
    const user = userEvent.setup();
    render(
      <FileValidationErrorsPanel
        clientInvalid={[
          {
            file: new File(["x"], "bad.exe"),
            error: {
              filename: "bad.exe",
              error_code: "UNSUPPORTED_FILE_TYPE",
              message: "exe rejected",
            },
          },
        ]}
        clientBatchErrors={[]}
        serverErrors={[]}
      />,
    );
    // collapsed by default
    expect(screen.queryByTestId("error-list")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("toggle-errors"));
    expect(screen.getByTestId("error-list")).toBeInTheDocument();
    expect(screen.getByTestId("client-error-0")).toHaveTextContent("bad.exe");
    expect(screen.getByTestId("client-error-0")).toHaveTextContent(
      "UNSUPPORTED_FILE_TYPE",
    );
  });

  it("renders hint for known error codes", async () => {
    const user = userEvent.setup();
    render(
      <FileValidationErrorsPanel
        clientInvalid={[]}
        clientBatchErrors={[]}
        serverErrors={[
          {
            filename: "huge.md",
            error_code: "FILE_TOO_LARGE",
            message: "100MB max",
          },
        ]}
      />,
    );
    await user.click(screen.getByTestId("toggle-errors"));
    // Hint встроен под error
    expect(
      screen.getByText(/Файл превышает максимально допустимый/),
    ).toBeInTheDocument();
  });

  it("invokes onClear when Clear button clicked", async () => {
    const onClear = vi.fn();
    const user = userEvent.setup();
    render(
      <FileValidationErrorsPanel
        clientInvalid={[
          {
            file: new File(["x"], "bad.exe"),
            error: {
              filename: "bad.exe",
              error_code: "UNSUPPORTED_FILE_TYPE",
              message: "m",
            },
          },
        ]}
        clientBatchErrors={[]}
        serverErrors={[]}
        onClear={onClear}
      />,
    );
    await user.click(screen.getByTestId("clear-errors"));
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});
