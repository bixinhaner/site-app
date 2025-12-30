import axios from 'axios'
import config from '@/config/env.js'

const MAX_CACHE_ENTRIES = 120

const blobCache = new Map()
const inflight = new Map()

const isAbsoluteUrl = (url) => /^https?:\/\//i.test(url)

export const resolveImageUrl = (input) => {
  const s = String(input ?? '').trim()
  if (!s) return ''
  if (s.startsWith('data:') || s.startsWith('blob:') || isAbsoluteUrl(s)) return s

  const base = String(config?.API_BASE_URL || (typeof window !== 'undefined' ? window.location.origin : '')).replace(/\/$/, '')
  if (!base) return s

  if (s.startsWith('/')) return `${base}${s}`
  return `${base}/${s}`
}

const getAuthToken = () => {
  try {
    return localStorage.getItem('access_token') || ''
  } catch (e) {
    return ''
  }
}

const touchCache = (key) => {
  if (!blobCache.has(key)) return
  const entry = blobCache.get(key)
  blobCache.delete(key)
  blobCache.set(key, entry)
}

const setCache = (key, entry) => {
  if (!key) return
  if (blobCache.has(key)) blobCache.delete(key)
  blobCache.set(key, entry)
  while (blobCache.size > MAX_CACHE_ENTRIES) {
    const oldestKey = blobCache.keys().next().value
    blobCache.delete(oldestKey)
  }
}

const computePercent = (progressEvent) => {
  const total = Number(progressEvent?.total) || 0
  const loaded = Number(progressEvent?.loaded) || 0
  if (total <= 0) return 0
  const percent = Math.floor((loaded / total) * 100)
  return Math.min(100, Math.max(0, percent))
}

const createInflightEntry = () => {
  return {
    progress: 0,
    subscribers: new Set(),
    notify(p) {
      this.progress = p
      this.subscribers.forEach((cb) => {
        try { cb(p) } catch (e) { /* ignore */ }
      })
    },
  }
}

const attachSubscriber = (entry, onProgress) => {
  if (!entry || typeof onProgress !== 'function') return
  entry.subscribers.add(onProgress)
  if (typeof entry.progress === 'number') onProgress(entry.progress)
}

const requestImageBlob = async ({ url, useAuth, onProgress }) => {
  const headers = {}
  if (useAuth) {
    const token = getAuthToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  const resp = await axios.get(url, {
    responseType: 'blob',
    timeout: 60000,
    headers,
    onDownloadProgress: (evt) => {
      if (typeof onProgress !== 'function') return
      onProgress(computePercent(evt))
    },
    validateStatus: (status) => status >= 200 && status < 300,
  })

  return resp?.data
}

export const loadImageBlob = async ({ url, onProgress } = {}) => {
  const resolvedUrl = resolveImageUrl(url)
  if (!resolvedUrl) return { ok: false, reason: 'empty_url' }

  if (blobCache.has(resolvedUrl)) {
    touchCache(resolvedUrl)
    if (typeof onProgress === 'function') onProgress(100)
    return {
      ok: true,
      blob: blobCache.get(resolvedUrl).blob,
      fromCache: true,
      usedAuth: blobCache.get(resolvedUrl).usedAuth,
    }
  }

  if (inflight.has(resolvedUrl)) {
    const entry = inflight.get(resolvedUrl)
    attachSubscriber(entry, onProgress)
    return entry.promise
  }

  const inflightEntry = createInflightEntry()
  attachSubscriber(inflightEntry, onProgress)

  inflightEntry.promise = (async () => {
    try {
      inflightEntry.notify(0)

      // 1) 默认不带 Authorization
      try {
        const blob = await requestImageBlob({
          url: resolvedUrl,
          useAuth: false,
          onProgress: (p) => inflightEntry.notify(p),
        })
        inflightEntry.notify(100)
        setCache(resolvedUrl, { blob, usedAuth: false, savedAt: Date.now() })
        return { ok: true, blob, fromCache: false, usedAuth: false }
      } catch (e) {
        const status = e?.response?.status
        // 2) 401/403 才尝试带 token 重试
        if (status !== 401 && status !== 403) throw e
      }

      inflightEntry.notify(0)
      const blob = await requestImageBlob({
        url: resolvedUrl,
        useAuth: true,
        onProgress: (p) => inflightEntry.notify(p),
      })
      inflightEntry.notify(100)
      setCache(resolvedUrl, { blob, usedAuth: true, savedAt: Date.now() })
      return { ok: true, blob, fromCache: false, usedAuth: true }
    } catch (error) {
      return { ok: false, reason: 'download_failed', error }
    } finally {
      inflight.delete(resolvedUrl)
    }
  })()

  inflight.set(resolvedUrl, inflightEntry)
  return inflightEntry.promise
}

export const createObjectUrl = (blob) => {
  if (!blob) return ''
  try {
    return URL.createObjectURL(blob)
  } catch (e) {
    return ''
  }
}

export const revokeObjectUrl = (url) => {
  const s = String(url ?? '').trim()
  if (!s) return
  try {
    URL.revokeObjectURL(s)
  } catch (e) {
    // ignore
  }
}

