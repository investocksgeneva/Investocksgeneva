import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// GitHub Pages serves this project from /Investocksgeneva/, while local dev
// and preview should stay at the root.
const base = process.env.DEPLOY_TARGET === 'gh-pages' ? '/Investocksgeneva/' : '/'

// https://vite.dev/config/
export default defineConfig({
  base,
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icons/icon-32.png'],
      manifest: {
        name: 'Français — Genève',
        short_name: 'FR Genève',
        description:
          'A beginner French course for daily life in Geneva: greetings, transport, shopping, and small talk.',
        theme_color: '#c8102e',
        background_color: '#f4f2ef',
        display: 'standalone',
        orientation: 'portrait',
        start_url: base,
        scope: base,
        icons: [
          {
            src: `${base}icons/icon-192.png`,
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: `${base}icons/icon-512.png`,
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: `${base}icons/icon-512.png`,
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
})
