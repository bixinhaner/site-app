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
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('/element-plus/') || id.includes('/@element-plus/')) {
            return 'element-plus-vendor'
          }
          if (
            id.includes('/@vue/')
            || id.includes('/vue/')
            || id.includes('/vue-router/')
            || id.includes('/vue-i18n/')
            || id.includes('/pinia/')
          ) {
            return 'vue-vendor'
          }
          if (id.includes('/axios/')) return 'http-vendor'
          return undefined
        },
      },
    },
  },
  server: {
    port: 3030,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
