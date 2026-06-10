/**
 * useUploadProgress (SETUP-02 / T-S02-018).
 *
 * Хук вокруг XMLHttpRequest для отправки multipart с per-file progress.
 * fetch API не поддерживает progress events; XHR — да.
 *
 * Использование:
 *   const { progress, response, error, upload, reset } = useUploadProgress();
 *   upload(url, formData, headers);
 *
 * Состояния `progress` — Map<filename, percent 0..100>. Точные per-file
 * проценты внутри одного multipart-запроса XHR не различает; обновляются
 * суммарно. Для UI мы экстраполируем равномерно по файлам, что в большинстве
 * случаев визуально достаточно.
 */
import { useCallback, useRef, useState } from "react";
import type { UploadDocumentsResponse } from "../api/types";

interface UploadProgressState {
  /** Общий percent по batch (0..100). */
  overall: number;
  /** Per-file percent. */
  perFile: Record<string, number>;
}

interface UploadHookState {
  progress: UploadProgressState;
  response: UploadDocumentsResponse | null;
  error: string | null;
  inFlight: boolean;
}

const INITIAL: UploadHookState = {
  progress: { overall: 0, perFile: {} },
  response: null,
  error: null,
  inFlight: false,
};

export function useUploadProgress(): {
  progress: UploadProgressState;
  response: UploadDocumentsResponse | null;
  error: string | null;
  inFlight: boolean;
  upload: (
    url: string,
    files: File[],
    headers: Record<string, string>,
  ) => Promise<UploadDocumentsResponse>;
  reset: () => void;
} {
  const [state, setState] = useState<UploadHookState>(INITIAL);
  const xhrRef = useRef<XMLHttpRequest | null>(null);

  const reset = useCallback(() => {
    xhrRef.current?.abort();
    xhrRef.current = null;
    setState(INITIAL);
  }, []);

  const upload = useCallback(
    (
      url: string,
      files: File[],
      headers: Record<string, string>,
    ): Promise<UploadDocumentsResponse> => {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhrRef.current = xhr;

        const formData = new FormData();
        for (const f of files) formData.append("files", f);

        const filenames = files.map((f) => f.name);
        const perFileInit: Record<string, number> = {};
        for (const name of filenames) perFileInit[name] = 0;
        setState({
          progress: { overall: 0, perFile: perFileInit },
          response: null,
          error: null,
          inFlight: true,
        });

        xhr.upload.onprogress = (e) => {
          if (!e.lengthComputable) return;
          const overall = Math.min(100, Math.round((e.loaded / e.total) * 100));
          // Равномерно распределяем по файлам (XHR не даёт per-file разбивку).
          const perFile: Record<string, number> = {};
          for (const name of filenames) perFile[name] = overall;
          setState((s) => ({ ...s, progress: { overall, perFile } }));
        };

        xhr.onerror = () => {
          setState((s) => ({
            ...s,
            inFlight: false,
            error: "Сетевая ошибка при загрузке",
          }));
          reject(new Error("Network error"));
        };

        xhr.onabort = () => {
          setState((s) => ({ ...s, inFlight: false, error: "Загрузка прервана" }));
          reject(new Error("Aborted"));
        };

        xhr.onload = () => {
          setState((s) => ({
            ...s,
            inFlight: false,
            progress: {
              overall: 100,
              perFile: Object.fromEntries(filenames.map((n) => [n, 100])),
            },
          }));
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const parsed = JSON.parse(xhr.responseText) as UploadDocumentsResponse;
              setState((s) => ({ ...s, response: parsed }));
              resolve(parsed);
            } catch {
              const e = "Не удалось разобрать ответ сервера";
              setState((s) => ({ ...s, error: e }));
              reject(new Error(e));
            }
          } else {
            // Может быть detail.error_code или detail string
            let errMessage = `HTTP ${xhr.status}`;
            try {
              const body = JSON.parse(xhr.responseText) as {
                detail?: { error_code?: string; message?: string } | string;
              };
              if (typeof body.detail === "string") errMessage = body.detail;
              else if (body.detail?.message) errMessage = body.detail.message;
            } catch {
              /* ignore parse error */
            }
            setState((s) => ({ ...s, error: errMessage }));
            reject(new Error(errMessage));
          }
        };

        xhr.open("POST", url, true);
        for (const [k, v] of Object.entries(headers)) {
          xhr.setRequestHeader(k, v);
        }
        xhr.send(formData);
      });
    },
    [],
  );

  return {
    progress: state.progress,
    response: state.response,
    error: state.error,
    inFlight: state.inFlight,
    upload,
    reset,
  };
}
