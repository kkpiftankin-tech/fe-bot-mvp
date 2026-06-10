/**
 * Тесты UploadProgressList (SETUP-02 / T-S02-018).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { UploadDocumentsResponse } from "../../../api/types";
import { UploadProgressList } from "../UploadProgressList";

function mkDoc(filename: string) {
  return {
    source_document_id: `src_${filename}`,
    setup_job_id: "s",
    filename,
    content_type: "text/markdown",
    size_bytes: 1,
    checksum: "x",
    status: "uploaded",
    uploaded_by: "u1",
    uploaded_at: "2026-06-10T10:00:00Z",
  };
}

describe("UploadProgressList", () => {
  it("renders nothing when filenames is empty", () => {
    const { container } = render(
      <UploadProgressList
        filenames={[]}
        perFileProgress={{}}
        inFlight={false}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders uploading state during in-flight", () => {
    render(
      <UploadProgressList
        filenames={["a.md", "b.md"]}
        perFileProgress={{ "a.md": 40, "b.md": 40 }}
        inFlight={true}
      />,
    );
    expect(screen.getByTestId("outcome-0")).toHaveTextContent("Загружается");
    expect(screen.getByTestId("outcome-1")).toHaveTextContent("Загружается");
  });

  it("shows uploaded outcome when in response.uploaded", () => {
    const response: UploadDocumentsResponse = {
      setup_job_id: "s",
      uploaded: [mkDoc("a.md")],
      skipped_duplicates: [],
      errors: [],
      job_status: "files_uploaded",
    };
    render(
      <UploadProgressList
        filenames={["a.md"]}
        perFileProgress={{ "a.md": 100 }}
        inFlight={false}
        response={response}
      />,
    );
    expect(screen.getByTestId("outcome-0")).toHaveTextContent("Загружен");
  });

  it("shows duplicate outcome when in skipped_duplicates", () => {
    const response: UploadDocumentsResponse = {
      setup_job_id: "s",
      uploaded: [],
      skipped_duplicates: [mkDoc("a.md")],
      errors: [],
      job_status: "files_uploaded",
    };
    render(
      <UploadProgressList
        filenames={["a.md"]}
        perFileProgress={{ "a.md": 100 }}
        inFlight={false}
        response={response}
      />,
    );
    expect(screen.getByTestId("outcome-0")).toHaveTextContent("Дубликат");
  });

  it("shows rejected outcome with error_code from response.errors", () => {
    const response: UploadDocumentsResponse = {
      setup_job_id: "s",
      uploaded: [],
      skipped_duplicates: [],
      errors: [
        {
          filename: "bad.exe",
          error_code: "UNSUPPORTED_FILE_TYPE",
          message: "exe не разрешён",
        },
      ],
      job_status: "draft",
    };
    render(
      <UploadProgressList
        filenames={["bad.exe"]}
        perFileProgress={{ "bad.exe": 100 }}
        inFlight={false}
        response={response}
      />,
    );
    expect(screen.getByTestId("outcome-0")).toHaveTextContent("Отклонён");
    const message = screen.getByTestId("outcome-message-0");
    expect(message).toHaveTextContent("UNSUPPORTED_FILE_TYPE");
    expect(message).toHaveTextContent("exe не разрешён");
  });

  it("renders global error banner when error is set", () => {
    render(
      <UploadProgressList
        filenames={["a.md"]}
        perFileProgress={{ "a.md": 0 }}
        inFlight={false}
        error="Сетевая ошибка"
      />,
    );
    const banner = screen.getByTestId("upload-fatal-error");
    expect(banner).toHaveTextContent("Сетевая ошибка");
  });
});
