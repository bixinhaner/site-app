import i18n from '@/utils/i18n.js'

// 供 store / 工具函数等非组件代码使用的翻译函数（与界面当前语言保持一致）
export const t = (key, params = {}) => i18n.global.t(key, params)
