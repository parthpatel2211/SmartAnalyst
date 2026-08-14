/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  // GitHub Pages serves a project site from /<repo>/, so assets need that
  // prefix. Left as "/" everywhere else, including local dev and any host
  // that serves from a domain root.
  base: process.env.VITE_BASE_PATH ?? "/",
  plugins: [react()],
  server: { port: 5173 },
  // No manualChunks here on purpose. Naming a chunk for Recharts makes it part
  // of the entry's preload graph, so Vite emits a modulepreload link for it and
  // it downloads on first paint -- which is exactly what lazily importing
  // ChartView is meant to avoid. Left alone, Rollup splits along the dynamic
  // import and the charting code is fetched only when a chart is first shown.
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.ts",
  },
});
