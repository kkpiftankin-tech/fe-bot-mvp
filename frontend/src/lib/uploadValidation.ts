/**
 * Client-side upload validation (SETUP-02 / T-S02-019).
 *
 * Pure functions без зависимости от React / DOM. Используется в:
 * - FileUploadPanel (немедленный feedback при drop)
 * - UploadDocumentsStep (фильтр перед отправкой на backend)
 *
 * Источник истины — backend (`src/fe_bot/setup/upload/validation.py`).
 * Эти проверки — только UX-fast-fail; backend всё равно валидирует.
 */

import type { UploadErrorCode } from "../api/types";

// ===== Конфиг (синхронизирован с schemas/common/defaults.py) =====

/** Допустимые расширения файлов (SETUP-01 §22.3 + SETUP-02 §4.3). */
export const ALLOWED_EXTENSIONS = [
  "md",
  "txt",
  "pdf",
  "docx",
  "xlsx",
  "csv",
  "json",
] as const;

/** Максимальный размер одного файла (MAX_FILE_SIZE_BYTES). */
export const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // 100 MB

/** Максимум файлов в batch (MAX_BATCH_FILES_COUNT). */
export const MAX_BATCH_FILES_COUNT = 50;

/** Максимальный суммарный размер batch (MAX_TOTAL_BATCH_SIZE_BYTES). */
export const MAX_TOTAL_BATCH_SIZE_BYTES = 500 * 1024 * 1024; // 500 MB

/** Максимальная длина filename (POSIX). */
export const MAX_FILENAME_LENGTH = 255;

// ===== Типы =====

export interface ValidationError {
  filename: string;
  error_code: UploadErrorCode;
  message: string;
  details?: Record<string, unknown>;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

// ===== Helpers =====

const FORBIDDEN_FILENAME_PARTS = ["..", "/", "\\"];

function getExtension(filename: string): string {
  const idx = filename.lastIndexOf(".");
  if (idx <= 0 || idx === filename.length - 1) return "";
  return filename.slice(idx + 1).toLowerCase();
}

function hasControlChar(s: string): boolean {
  for (const ch of s) {
    const code = ch.charCodeAt(0);
    if (code < 0x20 || code === 0x7f) return true;
  }
  return false;
}

// ===== Per-file validation =====

/**
 * Проверяет один файл. Возвращает первую найденную ошибку или null.
 * Порядок проверок зеркалит backend для одинакового UX.
 */
export function validateFile(file: File): ValidationError | null {
  const filename = file.name;

  // 1. filename safety
  if (!filename || !filename.trim()) {
    return {
      filename: filename || "(empty)",
      error_code: "INVALID_FILENAME",
      message: "Имя файла обязательно",
      details: { reason: "empty" },
    };
  }
  if (filename.length > MAX_FILENAME_LENGTH) {
    return {
      filename,
      error_code: "INVALID_FILENAME",
      message: `Имя файла слишком длинное (${filename.length} > ${MAX_FILENAME_LENGTH})`,
      details: { reason: "too_long", length: filename.length },
    };
  }
  for (const part of FORBIDDEN_FILENAME_PARTS) {
    if (filename.includes(part)) {
      return {
        filename,
        error_code: "INVALID_FILENAME",
        message: `Имя файла содержит запрещённую последовательность ${JSON.stringify(part)}`,
        details: { reason: "forbidden_sequence", sequence: part },
      };
    }
  }
  if (hasControlChar(filename)) {
    return {
      filename,
      error_code: "INVALID_FILENAME",
      message: "Имя файла содержит управляющие символы",
      details: { reason: "control_character" },
    };
  }

  // 2. empty
  if (file.size === 0) {
    return {
      filename,
      error_code: "EMPTY_FILE",
      message: "Файл пустой",
    };
  }

  // 3. size
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return {
      filename,
      error_code: "FILE_TOO_LARGE",
      message: `Файл превышает лимит ${MAX_FILE_SIZE_BYTES} байт`,
      details: { size_bytes: file.size, limit: MAX_FILE_SIZE_BYTES },
    };
  }

  // 4. extension
  const ext = getExtension(filename);
  if (!ext || !ALLOWED_EXTENSIONS.includes(ext as (typeof ALLOWED_EXTENSIONS)[number])) {
    return {
      filename,
      error_code: "UNSUPPORTED_FILE_TYPE",
      message: `Расширение ${JSON.stringify(ext || "(нет)")} не поддерживается`,
      details: {
        detected_extension: ext,
        allowed_extensions: [...ALLOWED_EXTENSIONS],
      },
    };
  }

  return null;
}

// ===== Batch validation =====

/**
 * Проверяет batch — все per-file ошибки + batch-level (count, total size,
 * filename uniqueness). Возвращает структуру с per-file errors и общим verdict.
 */
export function validateBatch(files: File[]): ValidationResult {
  const errors: ValidationError[] = [];

  // 0. batch empty?
  if (files.length === 0) {
    return {
      valid: false,
      errors: [
        {
          filename: "",
          error_code: "MISSING_FILES",
          message: "Выберите хотя бы один файл",
        },
      ],
    };
  }

  // 1. batch count
  if (files.length > MAX_BATCH_FILES_COUNT) {
    errors.push({
      filename: "",
      error_code: "BATCH_TOO_LARGE",
      message: `Batch содержит ${files.length} файл(ов); максимум ${MAX_BATCH_FILES_COUNT}`,
      details: {
        reason: "too_many_files",
        files_count: files.length,
        limit: MAX_BATCH_FILES_COUNT,
      },
    });
  }

  // 2. batch total size
  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  if (totalSize > MAX_TOTAL_BATCH_SIZE_BYTES) {
    errors.push({
      filename: "",
      error_code: "BATCH_TOO_LARGE",
      message: `Суммарный размер ${totalSize} байт превышает ${MAX_TOTAL_BATCH_SIZE_BYTES}`,
      details: {
        reason: "total_size_exceeded",
        total_size_bytes: totalSize,
        limit: MAX_TOTAL_BATCH_SIZE_BYTES,
      },
    });
  }

  // 3. filename uniqueness внутри batch
  const seen = new Set<string>();
  for (const f of files) {
    if (seen.has(f.name)) {
      errors.push({
        filename: f.name,
        error_code: "INVALID_FILENAME",
        message: `Имя файла ${JSON.stringify(f.name)} встречается несколько раз в batch`,
        details: { reason: "duplicate_in_batch", filename: f.name },
      });
    }
    seen.add(f.name);
  }

  // 4. per-file
  for (const f of files) {
    const err = validateFile(f);
    if (err !== null) errors.push(err);
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * Разделяет files на валидные и невалидные по результату validateFile.
 * Удобно для оптимистичного UI: валидные → uploading, невалидные → errors.
 */
export function partitionByValidation(files: File[]): {
  valid: File[];
  invalid: { file: File; error: ValidationError }[];
} {
  const valid: File[] = [];
  const invalid: { file: File; error: ValidationError }[] = [];
  for (const f of files) {
    const err = validateFile(f);
    if (err) invalid.push({ file: f, error: err });
    else valid.push(f);
  }
  return { valid, invalid };
}
