import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  define: {
    "import.meta.env.VITE_SUBSCRIPTIONS_ENABLED": JSON.stringify(mode !== "open" ? "true" : "false"),
  },
  build: {
    outDir: mode === "open" ? "dist/open" : mode === "subscription" ? "dist/subscription" : "dist",
  },
  server: {
    port: 5173,
  },
}));
