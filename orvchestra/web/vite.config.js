import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { VitePWA } from "vite-plugin-pwa";

// Orvchestra's FastAPI process serves this build's `dist/` directly (see
// orvchestra.webapp.app's SPA fallback route) and also serves /api, /track,
// /art on the same origin, so the built app makes same-origin requests with
// no configured API base URL and no CORS to worry about.
export default defineConfig({
  plugins: [
    svelte(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "Orvchestra",
        short_name: "Orvchestra",
        description: "A private, streaming-style player for a local music library",
        theme_color: "#0b0b0f",
        background_color: "#0b0b0f",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icons/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // Library metadata/art/audio should never be served stale from a
        // cache -- only the app shell (JS/CSS) benefits from precaching.
        globPatterns: ["**/*.{js,css,html,svg,png}"],
        navigateFallbackDenylist: [/^\/api\//, /^\/track\//, /^\/art\//],
      },
    }),
  ],
  build: {
    outDir: "dist",
  },
});
