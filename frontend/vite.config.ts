import { readFileSync } from 'node:fs'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// In development the frontend calls /api on the same origin and Vite forwards it to the
// FastAPI backend, so no CORS setup is needed locally. Override with VITE_API_PROXY.
//
// Testing on a phone over Wi-Fi: browsers open the camera only on https:// (or http://localhost), so
// http://<pc-ip>:5173 gets no camera. Set VITE_DEV_HTTPS_CERT and VITE_DEV_HTTPS_KEY (e.g. made with mkcert, see
// README) to serve https://<pc-ip>:5173. VITE_LIVEKIT_PROXY (e.g. ws://localhost:7880) also forwards OpenVidu's
// signalling (/rtc) through this server, so an https page can reach it as wss://<pc-ip>:5173.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const https = env.VITE_DEV_HTTPS_CERT && env.VITE_DEV_HTTPS_KEY
    ? { cert: readFileSync(env.VITE_DEV_HTTPS_CERT), key: readFileSync(env.VITE_DEV_HTTPS_KEY) }
    : undefined
  // Camera and microphone for this site only (the same header a production web server should send, see
  // docs/DEPLOY_HTTPS.md). Pages from other sites embedded here, if any, get neither.
  const headers = { 'Permissions-Policy': 'camera=(self), microphone=(self), display-capture=()' }
  return {
    plugins: [react(), tailwindcss()],
    preview: { headers },
    server: {
      headers,
      https,
      proxy: {
        '/api': { target: env.VITE_API_PROXY || 'http://localhost:8000', changeOrigin: true },
        ...(env.VITE_LIVEKIT_PROXY ? { '/rtc': { target: env.VITE_LIVEKIT_PROXY, ws: true, changeOrigin: true } } : {}),
      },
    },
  }
})
