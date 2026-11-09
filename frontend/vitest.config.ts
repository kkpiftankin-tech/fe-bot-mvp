import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // tsc -b в этом репо эмитит дублирующие .js рядом с .tsx. Берём только TS-источники.
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
