import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// In development the frontend calls /api on the same origin and Vite forwards it to the
// FastAPI backend, so no CORS setup is needed locally. Override with VITE_API_PROXY.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: { '/api': { target: env.VITE_API_PROXY || 'http://localhost:8000', changeOrigin: true } },
    },
  }
})
