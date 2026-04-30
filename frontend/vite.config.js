import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/socket.io': {
        target: 'http://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    lib: {
      entry: resolve(__dirname, 'src/main.js'),
      name: 'smart-serviceWidget',
      formats: ['iife'],
      fileName: () => 'chat-widget.js',
    },
    rollupOptions: {
      external: [],
      output: {
        intro: 'window.process = {env: {}};',
        globals: {},
        assetFileNames: () => 'chat-widget.css',
      },
    },
  },
})
