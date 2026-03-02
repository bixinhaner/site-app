import { getCurrentInstance } from 'vue/dist/vue.runtime.esm-bundler.js'

export * from 'vue/dist/vue.runtime.esm-bundler.js'

// @dcloudio/uni-app 在 CLI 构建时会从 vue 读取该符号；
// 官方 vue ESM 入口未导出，给出客户端场景下的稳定兜底值。
export const isInSSRComponentSetup = false

// 兼容 uni-app 对私有 API injectHook 的依赖。
// 仅用于 CLI 构建链，按组件实例生命周期桶注册回调。
export const injectHook = (type, hook, target = getCurrentInstance(), prepend = false) => {
  if (!target || !type || typeof hook !== 'function') return
  const hooks = target[type] || (target[type] = [])
  if (prepend) hooks.unshift(hook)
  else hooks.push(hook)
  return hook
}
