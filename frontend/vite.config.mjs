import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE_PATH ?? (process.env.VITE_INCIDENT_LENS_DEMO === "1" ? "/incident-lens/" : "/"),
  server: { proxy: { "/v1": "http://localhost:8000", "/health": "http://localhost:8000" } },
});
