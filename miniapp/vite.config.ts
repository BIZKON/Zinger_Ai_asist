import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/miniapp/",
  build: {
    outDir: "dist",
  },
  server: {
    port: 5173,
    // Проксируем API-запросы на backend (порт 8001)
    proxy: {
      "/api": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});
