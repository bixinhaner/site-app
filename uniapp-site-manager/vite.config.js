import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const useCliVueBridge = process.env.UNI_CLI_VUE_BRIDGE === '1'

export default defineConfig({
  plugins: [uni()],
  define: {
    __UNI_FEATURE_I18N_EN__: true,
    __UNI_FEATURE_I18N_ES__: false,
    __UNI_FEATURE_I18N_FR__: false,
    __UNI_FEATURE_I18N_LOCALE__: true,
    __UNI_FEATURE_I18N_ZH_HANS__: true,
    __UNI_FEATURE_I18N_ZH_HANT__: false,
    __UNI_FEATURE_LEFTWINDOW__: false,
    __UNI_FEATURE_LONGPRESS__: false,
    __UNI_FEATURE_NAVIGATIONBAR_BUTTONS__: false,
    __UNI_FEATURE_NAVIGATIONBAR_SEARCHINPUT__: false,
    __UNI_FEATURE_NAVIGATIONBAR_TRANSPARENT__: false,
    __UNI_FEATURE_NAVIGATIONBAR__: true,
    __UNI_FEATURE_PAGES__: true,
    __UNI_FEATURE_PULL_DOWN_REFRESH__: true,
    __UNI_FEATURE_RESPONSIVE__: false,
    __UNI_FEATURE_RIGHTWINDOW__: false,
    __UNI_FEATURE_ROUTER_MODE__: JSON.stringify('hash'),
    __UNI_FEATURE_TABBAR_MIDBUTTON__: false,
    __UNI_FEATURE_TABBAR__: false,
    __UNI_FEATURE_TOPWINDOW__: false,
    __UNI_FEATURE_UNI_CLOUD__: false,
    __UNI_FEATURE_WXS__: false,
    __UNI_FEATURE_WX__: false,
  },
  optimizeDeps: {
    exclude: ['@dcloudio/uni-h5', '@dcloudio/uni-h5-vue'],
  },
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
