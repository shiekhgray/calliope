import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/calliope/',
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: ['dresdengray.com'],
    hmr: {
      clientPort: 443,
      protocol: 'wss',
    },
    proxy: {
      '/calliope/api': {
        target: process.env.API_URL || 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/calliope\/api/, ''),
      },
    },
  },
})
