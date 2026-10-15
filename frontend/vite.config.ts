import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// In development the React app calls relative /api URLs and Vite proxies them to FastAPI,
// so the browser never needs CORS. Set VITE_API_BASE_URL to call the API directly instead.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: { '/api': { target, changeOrigin: true } },
    },
    preview: {
      port: 4173,
      proxy: { '/api': { target, changeOrigin: true } },
    },
    test: {
      environment: 'node',
    },
  }
})
