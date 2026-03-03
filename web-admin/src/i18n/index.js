import { createI18n } from 'vue-i18n'
import zhCN from './messages/zh-CN'
import enUS from './messages/en-US'
import { DEFAULT_LOCALE, getInitialLocale } from './locale'

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: getInitialLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
  fallbackWarn: false,
  missingWarn: false,
})

if (typeof document !== 'undefined') {
  document.documentElement.lang = i18n.global.locale.value
}

export default i18n
