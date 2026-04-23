import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/upload-invoice": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/invoices": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/invoice": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/analytics": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/export-dataset": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
