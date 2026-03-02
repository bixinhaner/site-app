import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const useCliVueBridge = process.env.UNI_CLI_VUE_BRIDGE === '1'

export default defineConfig({
  plugins: [uni()],
  resolve: {
    alias: useCliVueBridge
      ? [{ find: /^vue$/, replacement: path.resolve(__dirname, 'config/vue-cli-bridge.js') }]
      : [],
  },
  server: {
    port: 3000,
    host: '0.0.0.0'
  }
})
