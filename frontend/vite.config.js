import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Доступ с других устройств в локальной сети
    host: true,
    // Разрешаем адреса туннеля (./dev.sh --public)
    allowedHosts: [".trycloudflare.com", ".lhr.life"],
    // API и Swagger доступны через тот же адрес, что и админка
    proxy: {
      "/api": backend,
      "/docs": backend,
      "/openapi.json": backend,
      "/health": backend
    }
  }
});
