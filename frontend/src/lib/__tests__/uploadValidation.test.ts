/**
 * Тесты client-side validation (SETUP-02 / T-S02-019).
 */
import { describe, expect, it } from "vitest";
import {
  MAX_BATCH_FILES_COUNT,
  MAX_FILE_SIZE_BYTES,
  MAX_FILENAME_LENGTH,
  partitionByValidation,
  validateBatch,
  validateFile,
} from "../uploadValidation";

function mkFile(
  name: string,
  content: string = "x",
  type: string = "text/markdown",
): File {
  return new File([content], name, { type });
}

function mkBigFile(name: string, size: number, type: string = "text/markdown"): File {
  // Создаём File с искусственным size, не выделяя реальные байты.
  const f = new File(["x"], name, { type });
  Object.defineProperty(f, "size", { value: size });
  return f;
}

describe("validateFile", () => {
  describe("filename safety", () => {
    it("rejects empty filename", () => {
      const err = validateFile(mkFile(""));
      expect(err?.error_code).toBe("INVALID_FILENAME");
      expect(err?.details?.reason).toBe("empty");
    });

    it("rejects path traversal", () => {
      const err = validateFile(mkFile("../etc/passwd"));
      expect(err?.error_code).toBe("INVALID_FILENAME");
      expect(err?.details?.reason).toBe("forbidden_sequence");
    });

    it("rejects backslash separator", () => {
      const err = validateFile(mkFile("a\\b.md"));
      expect(err?.error_code).toBe("INVALID_FILENAME");
    });

    it("rejects null byte", () => {
      const err = validateFile(mkFile("bad\x00name.md"));
      expect(err?.error_code).toBe("INVALID_FILENAME");
      expect(err?.details?.reason).toBe("control_character");
    });

    it("rejects too-long filename", () => {
      const longName = "a".repeat(MAX_FILENAME_LENGTH) + "b.md";
      const err = validateFile(mkFile(longName));
      expect(err?.error_code).toBe("INVALID_FILENAME");
      expect(err?.details?.reason).toBe("too_long");
    });

    it("accepts Russian + spaces + parens in filename", () => {
      expect(validateFile(mkFile("Доклад (final) v1.docx", "x", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))).toBeNull();
    });
  });

  describe("size limits", () => {
    it("rejects empty file (0 bytes)", () => {
      const err = validateFile(mkFile("empty.md", ""));
      expect(err?.error_code).toBe("EMPTY_FILE");
    });

    it("rejects too-large file", () => {
      const err = validateFile(mkBigFile("big.md", MAX_FILE_SIZE_BYTES + 1));
      expect(err?.error_code).toBe("FILE_TOO_LARGE");
    });

    it("accepts file at exact limit", () => {
      // Создаём File с size==MAX через моканный объект (быстрее чем 100MB Uint8Array).
      const fakeFile = new File(["x"], "ok.md", { type: "text/markdown" });
      Object.defineProperty(fakeFile, "size", { value: MAX_FILE_SIZE_BYTES });
      expect(validateFile(fakeFile)).toBeNull();
    });
  });

  describe("extension allowlist", () => {
    it("rejects .exe", () => {
      const err = validateFile(mkFile("bad.exe", "x", "application/x-msdownload"));
      expect(err?.error_code).toBe("UNSUPPORTED_FILE_TYPE");
      expect(err?.details?.detected_extension).toBe("exe");
    });

    it("rejects file without extension", () => {
      const err = validateFile(mkFile("noext", "x"));
      expect(err?.error_code).toBe("UNSUPPORTED_FILE_TYPE");
    });

    it.each([
      ["doc.md", "text/markdown"],
      ["data.csv", "text/csv"],
      ["meta.json", "application/json"],
      ["report.pdf", "application/pdf"],
    ])("accepts %s", (name, type) => {
      expect(validateFile(mkFile(name, "x", type))).toBeNull();
    });

    it("is case-insensitive for extension", () => {
      expect(validateFile(mkFile("DOC.MD", "x", "text/markdown"))).toBeNull();
    });
  });
});

describe("validateBatch", () => {
  it("rejects empty batch", () => {
    const result = validateBatch([]);
    expect(result.valid).toBe(false);
    expect(result.errors[0]?.error_code).toBe("MISSING_FILES");
  });

  it("rejects too many files", () => {
    const files = Array.from({ length: MAX_BATCH_FILES_COUNT + 1 }, (_, i) =>
      mkFile(`f${i}.md`),
    );
    const result = validateBatch(files);
    expect(result.valid).toBe(false);
    expect(
      result.errors.some(
        (e) => e.error_code === "BATCH_TOO_LARGE" && e.details?.reason === "too_many_files",
      ),
    ).toBe(true);
  });

  it("detects duplicate filenames in batch", () => {
    const result = validateBatch([mkFile("same.md"), mkFile("same.md")]);
    expect(
      result.errors.some(
        (e) =>
          e.error_code === "INVALID_FILENAME" &&
          e.details?.reason === "duplicate_in_batch",
      ),
    ).toBe(true);
  });

  it("collects per-file errors alongside batch-level", () => {
    const result = validateBatch([
      mkFile("good.md", "x", "text/markdown"),
      mkFile("bad.exe", "x", "application/x-msdownload"),
    ]);
    expect(result.valid).toBe(false);
    const codes = result.errors.map((e) => e.error_code).sort();
    expect(codes).toContain("UNSUPPORTED_FILE_TYPE");
    // good.md не должен дать ошибку.
    expect(codes).not.toContain("EMPTY_FILE");
  });

  it("returns valid=true when all files are good", () => {
    const result = validateBatch([
      mkFile("a.md", "x", "text/markdown"),
      mkFile("b.txt", "x", "text/plain"),
    ]);
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });
});

describe("partitionByValidation", () => {
  it("splits valid and invalid files", () => {
    const { valid, invalid } = partitionByValidation([
      mkFile("good.md", "x", "text/markdown"),
      mkFile("bad.exe", "x", "application/x-msdownload"),
      mkFile("empty.md", ""),
    ]);
    expect(valid.map((f) => f.name)).toEqual(["good.md"]);
    expect(invalid.map((x) => x.file.name).sort()).toEqual(
      ["bad.exe", "empty.md"].sort(),
    );
    expect(invalid.find((x) => x.file.name === "bad.exe")?.error.error_code).toBe(
      "UNSUPPORTED_FILE_TYPE",
    );
    expect(invalid.find((x) => x.file.name === "empty.md")?.error.error_code).toBe(
      "EMPTY_FILE",
    );
  });
});
