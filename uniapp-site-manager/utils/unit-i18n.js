const UNIT_TRANSLATION_KEY_MAP = {
  '台': 'unitTai',
  '臺': 'unitTai',
  'unit': 'unitTai',
  'units': 'unitTai',

  '套': 'unitSet',
  'set': 'unitSet',
  'sets': 'unitSet',

  '个': 'unitPiece',
  '個': 'unitPiece',
  'pc': 'unitPiece',
  'pcs': 'unitPiece',
  'piece': 'unitPiece',
  'pieces': 'unitPiece',

  '副': 'unitPair',
  'pair': 'unitPair',
  'pairs': 'unitPair',

  '米': 'unitMeter',
  'm': 'unitMeter',
  'meter': 'unitMeter',
  'meters': 'unitMeter',
}

const normalizeUnit = (unit) => String(unit || '').trim()

export const resolveStockUnitKey = (unit) => {
  const raw = normalizeUnit(unit)
  if (!raw) return ''
  return UNIT_TRANSLATION_KEY_MAP[raw] || UNIT_TRANSLATION_KEY_MAP[raw.toLowerCase()] || ''
}

export const getLocalizedStockUnit = (unit, t) => {
  const raw = normalizeUnit(unit)
  if (!raw) return ''

  const key = resolveStockUnitKey(raw)
  if (!key || typeof t !== 'function') return raw

  const i18nKey = `stock.${key}`
  const translated = t(i18nKey)
  if (!translated || translated === i18nKey) return raw
  return translated
}
