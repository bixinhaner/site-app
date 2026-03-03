import i18n from './index'
import dynamicPatterns from './legacy-dynamic-patterns'
import dynamicOverrides from './legacy-dynamic-overrides'
import { DEFAULT_LOCALE, persistLocale, SUPPORTED_LOCALES, normalizeLocale } from './locale'

export const containsCJK = (value) => /[\u4e00-\u9fff]/.test(String(value || ''))

const normalizeText = (value) => String(value || '').replace(/\s+/g, ' ').trim()
let legacyEnMap = {}
let mapLoaded = false
let mapLoadingPromise = null
const highPriorityLiteralOverrides = {
  操作: 'Actions',
  方向: 'Direction',
  仓库: 'Warehouse',
  单位: 'Unit',
  库存状态: 'Status',
  已分配: 'Assigned',
  当前库存: 'Current stock',
  可用库存: 'Available stock',
  '单据/文件': 'Document / File',
  记录类型: 'Record type',
  操作类型: 'Operation type',
  筛选仓库: 'Warehouse',
  '筛选仓库（默认我的仓库）': 'Warehouse (default mine)',
  '待收货（含部分）': 'Awaiting receipt',
  '搜索：批次号 / 退库单号 / 出库单号 / 申请人': 'Search batch / return / outbound / applicant',
  '搜索单据/设备/SN': 'Search doc/device/SN',
  去确认: 'Confirm',
  收货确认: 'Confirm Receipt',
  '收货确认（可部分）': 'Confirm Receipt (Partial Allowed)',
  出入库记录: 'In/Out records',
  '初勘（第1次勘察）': 'Preliminary Survey (Round 1)',
}

const compiledDynamicRules = []
for (const rule of [...dynamicOverrides, ...dynamicPatterns]) {
  try {
    const regex = rule.pattern instanceof RegExp ? rule.pattern : new RegExp(rule.pattern)
    const replace = rule.replace ?? rule.replacement ?? ''
    compiledDynamicRules.push({ regex, replace })
  } catch {
    // Ignore invalid generated patterns to keep translation runtime stable.
  }
}

const polishEnglishText = (text) => {
  if (typeof text !== 'string' || !text) return text
  let output = text

  output = output
    .replace(/\b[Ss]uit\b/g, 'Package')
    .replace(/\b[Ee]xcipient\b/g, 'auxiliary material')
    .replace(/\b[Ee]xcipients\b/g, 'auxiliary materials')
    .replace(/Departure successfully:/g, 'Stock-out succeeded:')
    .replace(/Over distance (\d+) Zhang/g, 'Exceeded threshold: $1 photos')
    .replace(/receipt details/gi, 'pickup details')
    .replace(/删除/g, 'Delete')
    .replace(/启用/g, 'Enable')
    .replace(/禁用/g, 'Disable')
    .replace(/更新/g, 'Update')
    .replace(/创建/g, 'Create')
    .replace(/\bsite \(/g, 'Site (')
    .replace(/\s{2,}/g, ' ')
    .trim()

  return output
}

const translateByDynamicRules = (text) => {
  for (const rule of compiledDynamicRules) {
    if (!rule.regex.test(text)) continue
    try {
      return text.replace(rule.regex, rule.replace)
    } catch {
      return text
    }
  }
  return text
}

const restorePadding = (source, translatedCore) => {
  const leading = source.match(/^\s*/)?.[0] || ''
  const trailing = source.match(/\s*$/)?.[0] || ''
  return `${leading}${translatedCore}${trailing}`
}

export const getCurrentLocale = () => {
  const locale = i18n.global.locale.value
  return SUPPORTED_LOCALES.includes(locale) ? locale : DEFAULT_LOCALE
}

export const isEnglishLocale = () => getCurrentLocale() === 'en-US'

export const ensureLegacyMapLoaded = async (locale = getCurrentLocale()) => {
  const targetLocale = normalizeLocale(locale)
  if (targetLocale !== 'en-US') return legacyEnMap
  if (mapLoaded) return legacyEnMap

  if (!mapLoadingPromise) {
    mapLoadingPromise = import('./legacy-en-map')
      .then((module) => {
        legacyEnMap = module?.default || {}
        mapLoaded = true
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('legacy-i18n-map-loaded'))
        }
        return legacyEnMap
      })
      .catch(() => {
        legacyEnMap = {}
        mapLoaded = true
        return legacyEnMap
      })
  }

  return mapLoadingPromise
}

export const setAppLocale = async (locale) => {
  const nextLocale = normalizeLocale(locale)
  if (nextLocale === 'en-US') {
    await ensureLegacyMapLoaded(nextLocale)
  }

  i18n.global.locale.value = nextLocale
  persistLocale(nextLocale)
  if (typeof document !== 'undefined') {
    document.documentElement.lang = nextLocale
  }
}

export const translateLegacyText = (text) => {
  if (typeof text !== 'string' || !text) return text
  if (!containsCJK(text)) return text
  if (!isEnglishLocale()) return text

  const normalized = normalizeText(text)
  const literalOverride = highPriorityLiteralOverrides[text] || highPriorityLiteralOverrides[normalized]
  if (literalOverride) return restorePadding(text, literalOverride)

  const exact = legacyEnMap[text] || legacyEnMap[normalized]
  if (exact) return polishEnglishText(exact)

  const dynamic = translateByDynamicRules(text)
  if (dynamic !== text) return polishEnglishText(dynamic)

  if (normalized && normalized !== text) {
    const normalizedDynamic = translateByDynamicRules(normalized)
    if (normalizedDynamic !== normalized) {
      return polishEnglishText(restorePadding(text, normalizedDynamic))
    }
  }

  return text
}

export const resolveRouteTitle = (routeLike, fallback = '') => {
  const meta = routeLike?.meta || routeLike || {}
  const routeName = routeLike?.name || meta?.routeName

  if (routeName) {
    const routeKey = `route.${routeName}`
    if (i18n.global.te(routeKey)) {
      return i18n.global.t(routeKey)
    }
  }

  const titleKey = meta?.titleKey
  if (titleKey) {
    const translated = i18n.global.t(titleKey)
    if (translated && translated !== titleKey) return translated
  }
  if (typeof meta?.title === 'string' && meta.title) {
    return translateLegacyText(meta.title)
  }
  return fallback
}
