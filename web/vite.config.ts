import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev, the Vite server proxies API calls to the FastAPI app
// (`jobwatch serve`); in production FastAPI serves the built files itself.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
