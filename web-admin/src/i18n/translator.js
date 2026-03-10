import i18n from './index'
import dynamicPatternsEn from './legacy-dynamic-patterns'
import dynamicPatternsId from './legacy-dynamic-patterns-id'
import dynamicOverrides from './legacy-dynamic-overrides'
import { DEFAULT_LOCALE, persistLocale, SUPPORTED_LOCALES, normalizeLocale } from './locale'

export const containsCJK = (value) => /[\u4e00-\u9fff]/.test(String(value || ''))

const normalizeText = (value) => String(value || '').replace(/\s+/g, ' ').trim()
const LEGACY_LOCALES = new Set(['en-US', 'id-ID'])

const legacyMapByLocale = {
  'en-US': {},
  'id-ID': {},
}

const mapLoadedByLocale = {
  'en-US': false,
  'id-ID': false,
}

const mapLoadingPromiseByLocale = {
  'en-US': null,
  'id-ID': null,
}

const highPriorityLiteralOverridesByLocale = {
  'en-US': {
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
  },
  'id-ID': {
    操作: 'Aksi',
    方向: 'Arah',
    仓库: 'Gudang',
    单位: 'Satuan',
    库存状态: 'Status',
    已分配: 'Ditugaskan',
    当前库存: 'Stok saat ini',
    可用库存: 'Stok tersedia',
    '单据/文件': 'Dokumen / Berkas',
    记录类型: 'Jenis catatan',
    操作类型: 'Jenis operasi',
    筛选仓库: 'Gudang',
    '筛选仓库（默认我的仓库）': 'Gudang (default milik saya)',
    '待收货（含部分）': 'Menunggu penerimaan',
    '搜索：批次号 / 退库单号 / 出库单号 / 申请人': 'Cari batch / retur / keluar / pemohon',
    '搜索单据/设备/SN': 'Cari dokumen/perangkat/SN',
    去确认: 'Konfirmasi',
    收货确认: 'Konfirmasi penerimaan',
    '收货确认（可部分）': 'Konfirmasi penerimaan (parsial)',
    出入库记录: 'Catatan masuk/keluar',
    '初勘（第1次勘察）': 'Survei awal (Putaran 1)',
  },
}

const dynamicRuleSourceByLocale = {
  'en-US': [...dynamicOverrides, ...dynamicPatternsEn],
  'id-ID': [...dynamicPatternsId],
}

const compileDynamicRules = (rules = []) => {
  const compiled = []
  for (const rule of rules) {
    try {
      const regex = rule.pattern instanceof RegExp ? rule.pattern : new RegExp(rule.pattern)
      const replace = rule.replace ?? rule.replacement ?? ''
      compiled.push({ regex, replace })
    } catch {
      // Ignore invalid generated patterns to keep translation runtime stable.
    }
  }
  return compiled
}

const compiledDynamicRulesByLocale = {
  'en-US': compileDynamicRules(dynamicRuleSourceByLocale['en-US']),
  'id-ID': compileDynamicRules(dynamicRuleSourceByLocale['id-ID']),
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

const polishByLocale = (text, locale) => {
  if (locale === 'en-US') return polishEnglishText(text)
  return text
}

const translateByDynamicRules = (text, locale) => {
  const rules = compiledDynamicRulesByLocale[locale] || []
  for (const rule of rules) {
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

export const isLegacyLocale = (locale = getCurrentLocale()) => LEGACY_LOCALES.has(normalizeLocale(locale))

const mapLoaderByLocale = {
  'en-US': () => import('./legacy-en-map'),
  'id-ID': () => import('./legacy-id-map'),
}

export const ensureLegacyMapLoaded = async (locale = getCurrentLocale()) => {
  const targetLocale = normalizeLocale(locale)
  if (!isLegacyLocale(targetLocale)) return legacyMapByLocale[targetLocale] || {}
  if (mapLoadedByLocale[targetLocale]) return legacyMapByLocale[targetLocale]

  if (!mapLoadingPromiseByLocale[targetLocale]) {
    mapLoadingPromiseByLocale[targetLocale] = mapLoaderByLocale[targetLocale]()
      .then((module) => {
        legacyMapByLocale[targetLocale] = module?.default || {}
        mapLoadedByLocale[targetLocale] = true
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('legacy-i18n-map-loaded'))
        }
        return legacyMapByLocale[targetLocale]
      })
      .catch(() => {
        legacyMapByLocale[targetLocale] = {}
        mapLoadedByLocale[targetLocale] = true
        return legacyMapByLocale[targetLocale]
      })
  }

  return mapLoadingPromiseByLocale[targetLocale]
}

export const setAppLocale = async (locale) => {
  const nextLocale = normalizeLocale(locale)
  if (isLegacyLocale(nextLocale)) {
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

  const locale = getCurrentLocale()
  if (!isLegacyLocale(locale)) return text

  const normalized = normalizeText(text)
  const localeLiteralOverrides = highPriorityLiteralOverridesByLocale[locale] || {}
  const literalOverride = localeLiteralOverrides[text] || localeLiteralOverrides[normalized]
  if (literalOverride) return restorePadding(text, literalOverride)

  const localeMap = legacyMapByLocale[locale] || {}
  const exact = localeMap[text] || localeMap[normalized]
  if (exact) return polishByLocale(exact, locale)

  const dynamic = translateByDynamicRules(text, locale)
  if (dynamic !== text) return polishByLocale(dynamic, locale)

  if (normalized && normalized !== text) {
    const normalizedDynamic = translateByDynamicRules(normalized, locale)
    if (normalizedDynamic !== normalized) {
      return polishByLocale(restorePadding(text, normalizedDynamic), locale)
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
