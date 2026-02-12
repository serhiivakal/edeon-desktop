import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// https://v2.tauri.app/start/frontend/vite/
const host = process.env.TAURI_DEV_HOST;

export default defineConfig(async () => ({
  plugins: [react()],

  // Vite options tailored for Tauri development
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // Tell vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
  },

  // Force esbuild to pre-bundle ngl using the UMD build for consistent default-export wrapping
  // in both dev and production (ngl's ESM build has no named exports, only bare imports)
  optimizeDeps: {
    include: ['ngl'],
  },
  resolve: {
    // Redirect the ngl ESM build to the UMD build so Rollup uses the same CJS/UMD format
    // that esbuild wraps consistently into a synthetic default export in all environments
    alias: {
      'ngl': fileURLToPath(new URL('./node_modules/ngl/dist/ngl.umd.js', import.meta.url)),
    },
  },
}));
