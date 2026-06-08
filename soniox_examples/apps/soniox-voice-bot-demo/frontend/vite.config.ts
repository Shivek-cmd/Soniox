import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Dev proxy: forward /store-api/* → store-api service on port 8766
      "/store-api": {
        target: "http://localhost:8766",
        rewrite: path => path.replace(/^\/store-api/, ""),
        changeOrigin: true,
      },
    },
  },
});
