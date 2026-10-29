import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Forward API calls to the FastAPI backend so the client never needs CORS
      // or a hardcoded origin.
      "/api": "http://localhost:8000",
    },
  },
});
