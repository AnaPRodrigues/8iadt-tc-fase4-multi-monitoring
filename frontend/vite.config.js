import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O painel só fala HTTP com a API do backend. Em desenvolvimento, o Vite faz proxy
// das chamadas de API para a API local (padrão http://localhost:8000), evitando
// problemas de CORS. Ajuste API_ALVO se subir a API noutra porta.
const API_ALVO = process.env.API_BASE_URL || "http://localhost:8000";

const rotasApi = ["/patients", "/uploads", "/alerts", "/evidence"];

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.FRONT_PORT) || 5173,
    proxy: Object.fromEntries(
      rotasApi.map((rota) => [rota, { target: API_ALVO, changeOrigin: true }])
    ),
  },
});
