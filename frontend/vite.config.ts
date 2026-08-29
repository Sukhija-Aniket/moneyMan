import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    watch: {
      // Bind-mounted source in Docker doesn't reliably deliver inotify events on macOS.
      usePolling: true,
    },
  },
});
