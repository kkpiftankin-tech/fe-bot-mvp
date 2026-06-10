/**
 * Тесты FileUploadPanel (SETUP-02 / T-S02-017).
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FileUploadPanel } from "../FileUploadPanel";

function mkFile(name: string, content: string = "x", type: string = "text/markdown"): File {
  return new File([content], name, { type });
}

describe("FileUploadPanel", () => {
  let onChange: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onChange = vi.fn();
  });

  it("renders drop zone with hint", () => {
    render(<FileUploadPanel onChange={onChange} />);
    expect(screen.getByTestId("drop-zone")).toBeInTheDocument();
    expect(screen.getByText(/Перетащите файлы/)).toBeInTheDocument();
  });

  it("accepts files via file picker", async () => {
    render(<FileUploadPanel onChange={onChange} />);
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const file = mkFile("doc.md");
    await userEvent.upload(input, [file]);
    expect(onChange).toHaveBeenCalled();
    const last = onChange.mock.calls.at(-1)?.[0];
    expect(last.valid).toHaveLength(1);
    expect(last.valid[0].name).toBe("doc.md");
  });

  it("rejects unsupported extension in invalid bucket", () => {
    // userEvent.upload фильтрует по accept attribute; используем fireEvent
    // чтобы протестировать backend-уровня валидацию (accept — только UI hint).
    render(<FileUploadPanel onChange={onChange} />);
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const file = mkFile("bad.exe", "x", "application/x-msdownload");
    fireEvent.change(input, { target: { files: [file] } });
    const last = onChange.mock.calls.at(-1)?.[0];
    expect(last.invalid).toHaveLength(1);
    expect(last.invalid[0].error.error_code).toBe("UNSUPPORTED_FILE_TYPE");
    expect(screen.getByTestId("file-error-0")).toBeInTheDocument();
  });

  it("shows batch error for duplicate filename in batch", async () => {
    render(<FileUploadPanel onChange={onChange} />);
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    await userEvent.upload(input, [mkFile("same.md"), mkFile("same.md")]);
    const batch = screen.getByTestId("batch-errors");
    expect(within(batch).getByText(/несколько раз/)).toBeInTheDocument();
  });

  it("allows removing individual file", async () => {
    render(<FileUploadPanel onChange={onChange} />);
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    await userEvent.upload(input, [mkFile("a.md"), mkFile("b.md")]);
    expect(screen.getAllByText(/\.md$/)).toHaveLength(2);
    await userEvent.click(screen.getByTestId("remove-file-0"));
    const last = onChange.mock.calls.at(-1)?.[0];
    expect(last.valid).toHaveLength(1);
    expect(last.valid[0].name).toBe("b.md");
  });

  it("clear button removes all files", async () => {
    render(<FileUploadPanel onChange={onChange} />);
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    await userEvent.upload(input, [mkFile("a.md"), mkFile("b.md")]);
    await userEvent.click(screen.getByTestId("clear-files"));
    const last = onChange.mock.calls.at(-1)?.[0];
    expect(last.valid).toHaveLength(0);
    expect(last.invalid).toHaveLength(0);
  });

  it("disabled state blocks input", () => {
    render(<FileUploadPanel onChange={onChange} disabled />);
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    expect(input.disabled).toBe(true);
    expect(screen.getByTestId("drop-zone").className).toContain("disabled");
  });

  it("drag-and-drop triggers onChange", () => {
    render(<FileUploadPanel onChange={onChange} />);
    const dropZone = screen.getByTestId("drop-zone");
    const file = mkFile("dragged.md");
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file] },
    });
    expect(onChange).toHaveBeenCalled();
    const last = onChange.mock.calls.at(-1)?.[0];
    expect(last.valid[0].name).toBe("dragged.md");
  });

  it("accepts custom hint", () => {
    render(<FileUploadPanel onChange={onChange} hint="Только md и txt" />);
    expect(screen.getByText("Только md и txt")).toBeInTheDocument();
  });
});
