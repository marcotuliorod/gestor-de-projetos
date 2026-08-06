import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'prompt', // não recarrega sozinho — Layout.tsx mostra um toast
      injectRegister: false, // registro manual via useRegisterSW em Layout.tsx
      devOptions: { enabled: false }, // testar via `npm run build && npm run preview`
      manifest: {
        name: 'Gestor de Projetos',
        short_name: 'Gestor',
        description: 'Painel de gestão de projetos e agentes',
        theme_color: '#000000',
        background_color: '#000000',
        display: 'standalone',
        icons: [
          { src: 'pwa-64x64.png', sizes: '64x64', type: 'image/png' },
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          { src: 'maskable-icon-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        navigateFallback: '/index.html',
        // Sem runtimeCaching para /api/* — chamadas de API continuam
        // NetworkOnly por omissão. O Board/Fila/Run mostram dados ao vivo;
        // cachear respostas de API mostraria estado desatualizado como se
        // fosse real.
      },
    }),
  ],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
