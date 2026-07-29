const normalizeBaseUrl = (rawUrl) => String(rawUrl || '').trim().replace(/\/+$/, '')

export const bindVersionInfoToSource = (versionInfo, sourceBaseUrl) => {
  if (!versionInfo || typeof versionInfo !== 'object') return versionInfo || null

  const sourceBase = normalizeBaseUrl(sourceBaseUrl)
  const rawDownloadUrl = String(versionInfo.download_url || '').trim()
  let downloadUrl = rawDownloadUrl

  if (rawDownloadUrl && !/^https?:\/\//i.test(rawDownloadUrl) && sourceBase) {
    const path = rawDownloadUrl.startsWith('/') ? rawDownloadUrl : `/${rawDownloadUrl}`
    downloadUrl = `${sourceBase}${path}`
  }

  return {
    ...versionInfo,
    download_url: downloadUrl,
    download_source_base_url: sourceBase,
  }
}

export const isSameUpgradeSource = (checkedBaseUrl, currentBaseUrl) => {
  const checked = normalizeBaseUrl(checkedBaseUrl)
  const current = normalizeBaseUrl(currentBaseUrl)
  return !!checked && !!current && checked === current
}
