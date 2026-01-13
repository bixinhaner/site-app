export const toPercentInt = (value) => {
  const normalizedValue = typeof value === 'string' ? value.replace(/%/g, '').trim() : value
  const num = Number(normalizedValue)
  if (!Number.isFinite(num)) return 0

  const intValue = Math.trunc(num)
  if (intValue < 0) return 0
  if (intValue > 100) return 100
  return intValue
}

export const formatPercentInt = (value) => `${toPercentInt(value)}%`
