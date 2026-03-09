import * as UniH5Vue from '@dcloudio/uni-h5-vue/dist/vue.runtime.esm.js'

export * from '@dcloudio/uni-h5-vue/dist/vue.runtime.esm.js'

// H5 fallback 启动链仍按 `createSSRApp` 读取入口，这里显式对齐到 uni-h5 的 createVueApp。
export const createSSRApp = UniH5Vue.createVueApp
