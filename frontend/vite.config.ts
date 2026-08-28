import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const API_TARGET = 'http://127.0.0.1:8000'

// The production build is written straight into the Python package so that a
// wheel (and later a PyInstaller bundle) ships the UI as ordinary static
// files. Nothing Node-related is needed at runtime.
export default defineConfig({
  plugins: [react()],
  // Relative asset URLs keep the bundle position-independent, which matters
  // once it is served from inside a packaged app rather than a web root.
  base: './',
  build: {
    outDir: '../src/sarmesh/web/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
      // SSE: buffering would defeat the point of a live position stream.
      '/events': { target: API_TARGET, changeOrigin: true, ws: false },
      '/tiles': { target: API_TARGET, changeOrigin: true },
    },
  },
})
