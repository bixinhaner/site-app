const normalizeDetail = (detail) => {
  if (typeof detail === 'string') return detail.trim()

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item.trim()
        return String(item?.msg || item?.message || '').trim()
      })
      .filter(Boolean)
      .join('；')
  }

  if (detail && typeof detail === 'object') {
    return String(detail.message || detail.msg || detail.detail || '').trim()
  }

  return ''
}

export const getApiErrorStatus = (error) => {
  const rawStatus = error?.response?.status ?? error?.status ?? error?.responseStatus
  const status = Number(rawStatus)
  return Number.isFinite(status) ? status : null
}

export const getApiErrorMessage = (error, fallback = '') => {
  const candidates = [
    error?.response?.data?.detail,
    error?.response?.data?.message,
    error?.response?.data,
    error?.data?.detail,
    error?.data?.message,
    error?.detail,
  ]

  for (const candidate of candidates) {
    const message = normalizeDetail(candidate)
    if (message) return message
  }

  return String(fallback || '').trim()
}
