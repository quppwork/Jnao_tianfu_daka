import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const upstream = "http://127.0.0.1:8010";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    host: "0.0.0.0",
    port: 5185,
    proxy: {
      "/api": { target: "http://127.0.0.1:8011", changeOrigin: true },
      "/chat": { target: upstream, changeOrigin: true },
      "/config": { target: upstream, changeOrigin: true },
      "/feedback": { target: upstream, changeOrigin: true },
      "/health": { target: upstream, changeOrigin: true },
      "/ingest": { target: upstream, changeOrigin: true, timeout: 300_000 },
      "/debug": { target: upstream, changeOrigin: true },
      "/admin/feedback": { target: upstream, changeOrigin: true },
    },
  },
});
