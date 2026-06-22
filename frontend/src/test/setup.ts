import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./msw";

// Node 25 предоставляет пустой stub globalThis.localStorage (фича WebStorage без
// --localstorage-file), который перекрывает реализацию jsdom. Подменяем на
// in-memory Storage-совместимый объект, чтобы zustand persist работал в тестах.
function createMemoryStorage(): Storage {
  const map = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key) => (map.has(key) ? map.get(key)! : null),
    setItem: (key, value) => {
      map.set(key, String(value));
    },
    removeItem: (key) => {
      map.delete(key);
    },
    key: (index) => Array.from(map.keys())[index] ?? null,
  };
  return storage;
}

const memoryLocal = createMemoryStorage();
const memorySession = createMemoryStorage();
Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: memoryLocal,
});
Object.defineProperty(globalThis, "sessionStorage", {
  configurable: true,
  value: memorySession,
});
if (typeof window !== "undefined") {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: memoryLocal,
  });
  Object.defineProperty(window, "sessionStorage", {
    configurable: true,
    value: memorySession,
  });
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  memoryLocal.clear();
  memorySession.clear();
});
afterAll(() => server.close());
