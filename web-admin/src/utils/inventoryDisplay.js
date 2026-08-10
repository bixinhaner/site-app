const INVENTORY_UNIT_KEYS = Object.freeze({
  台: 'device',
  套: 'set',
  个: 'piece',
  副: 'pair',
  米: 'meter',
  根: 'rod',
  条: 'strip',
  卷: 'roll',
  箱: 'box',
  批: 'batch',
})

export const formatInventoryUnit = (unit, t) => {
  const value = String(unit || '').trim()
  if (!value) return '-'
  const key = INVENTORY_UNIT_KEYS[value]
  return key ? t(`inventory.page.units.${key}`) : value
}
