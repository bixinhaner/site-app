export const DEFAULT_LOCALE = 'zh-CN'
export const SUPPORTED_LOCALES = ['zh-CN', 'en-US', 'id-ID']
export const LOCALE_STORAGE_KEY = 'siteapp.webadmin.locale'

const hasWindow = typeof window !== 'undefined'

export const normalizeLocale = (input) => {
  const value = String(input || '').toLowerCase()
  if (!value) return DEFAULT_LOCALE
  if (value.startsWith('en')) return 'en-US'
  if (value.startsWith('id') || value.startsWith('in')) return 'id-ID'
  if (value.startsWith('zh')) return 'zh-CN'
  return DEFAULT_LOCALE
}

const getStoredLocale = () => {
  if (!hasWindow) return ''
  return window.localStorage.getItem(LOCALE_STORAGE_KEY) || ''
}

const getBrowserLocale = () => {
  if (!hasWindow) return DEFAULT_LOCALE
  const browserLocale = navigator.language || navigator.languages?.[0] || ''
  return normalizeLocale(browserLocale)
}

export const getInitialLocale = () => {
  const stored = normalizeLocale(getStoredLocale())
  if (SUPPORTED_LOCALES.includes(stored)) return stored
  return getBrowserLocale()
}

export const persistLocale = (locale) => {
  if (!hasWindow) return
  window.localStorage.setItem(LOCALE_STORAGE_KEY, normalizeLocale(locale))
}
