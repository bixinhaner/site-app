import { getInitialLocale } from '../i18n/locale.js'

export const CHUNK_RECOVERY_STORAGE_KEY = 'siteapp.webadmin.chunk-recovery'
export const CHUNK_RECOVERY_WINDOW_MS = 60_000

const CHUNK_ERROR_PATTERNS = [
  /failed to fetch dynamically imported module/i,
  /error loading dynamically imported module/i,
  /importing a module script failed/i,
  /failed to load module script/i,
  /unable to preload css/i,
  /chunkloaderror/i,
  /loading chunk .* failed/i,
]

const getErrorMessage = (error) => {
  if (!error) return ''
  if (typeof error === 'string') return error

  const message = String(error.message || error.name || '')
  if (error.cause && error.cause !== error) {
    return `${message} ${getErrorMessage(error.cause)}`.trim()
  }
  return message
}

export const isChunkLoadError = (error) => {
  const message = getErrorMessage(error)
  return CHUNK_ERROR_PATTERNS.some(pattern => pattern.test(message))
}

const getCurrentPath = (location) => {
  if (!location) return '/'
  return `${location.pathname || '/'}${location.search || ''}${location.hash || ''}`
}

const normalizeTargetPath = (targetPath, location) => {
  const value = String(targetPath || '')
  return value.startsWith('/') && !value.startsWith('//') ? value : getCurrentPath(location)
}

const readRecoveryState = (storage) => {
  if (!storage) return null
  try {
    const state = JSON.parse(storage.getItem(CHUNK_RECOVERY_STORAGE_KEY) || 'null')
    if (!state || typeof state.targetPath !== 'string' || !Number.isFinite(state.attemptedAt)) {
      return null
    }
    return state
  } catch {
    return null
  }
}

const writeRecoveryState = (storage, state) => {
  if (!storage) return
  try {
    storage.setItem(CHUNK_RECOVERY_STORAGE_KEY, JSON.stringify(state))
  } catch {
    // sessionStorage unavailable must not block page recovery.
  }
}

const removeRecoveryState = (storage) => {
  if (!storage) return
  try {
    storage.removeItem(CHUNK_RECOVERY_STORAGE_KEY)
  } catch {
    // Ignore restricted storage environments.
  }
}

const recoveryMessages = {
  'zh-CN': {
    title: '页面资源未能更新',
    description: '系统已尝试自动刷新，但页面仍无法加载。请检查网络后重新加载。',
    action: '重新加载',
  },
  'en-US': {
    title: 'The page could not be updated',
    description: 'The automatic refresh did not complete. Check your connection and reload the page.',
    action: 'Reload',
  },
  'id-ID': {
    title: 'Halaman tidak dapat diperbarui',
    description: 'Penyegaran otomatis belum berhasil. Periksa koneksi lalu muat ulang halaman.',
    action: 'Muat ulang',
  },
}

const showRecoveryFallback = ({ retry }) => {
  if (typeof document === 'undefined') return

  const existing = document.getElementById('chunk-recovery-overlay')
  if (existing) return

  const locale = getInitialLocale()
  const messages = recoveryMessages[locale] || recoveryMessages['zh-CN']
  const overlay = document.createElement('div')
  overlay.id = 'chunk-recovery-overlay'
  overlay.className = 'chunk-recovery-overlay'
  overlay.setAttribute('role', 'alertdialog')
  overlay.setAttribute('aria-modal', 'true')

  const panel = document.createElement('div')
  panel.className = 'chunk-recovery-panel'

  const title = document.createElement('h2')
  title.textContent = messages.title

  const description = document.createElement('p')
  description.textContent = messages.description

  const button = document.createElement('button')
  button.type = 'button'
  button.textContent = messages.action
  button.addEventListener('click', retry)

  panel.append(title, description, button)
  overlay.append(panel)
  document.body.append(overlay)
  button.focus()
}

const reloadBrowser = (targetPath, location) => {
  if (!location) return
  if (targetPath && targetPath !== getCurrentPath(location) && typeof location.replace === 'function') {
    location.replace(targetPath)
    return
  }
  location.reload()
}

export const createChunkLoadRecovery = ({
  location = typeof window !== 'undefined' ? window.location : null,
  storage = typeof window !== 'undefined' ? window.sessionStorage : null,
  now = () => Date.now(),
  reload = targetPath => reloadBrowser(targetPath, location),
  showFallback = showRecoveryFallback,
  recoveryWindowMs = CHUNK_RECOVERY_WINDOW_MS,
} = {}) => {
  let recoveryInProgress = false

  const clear = (targetPath) => {
    const state = readRecoveryState(storage)
    if (!state) return
    if (targetPath && state.targetPath !== normalizeTargetPath(targetPath, location)) return
    removeRecoveryState(storage)
  }

  const retry = (targetPath) => {
    recoveryInProgress = true
    removeRecoveryState(storage)
    reload(targetPath)
  }

  const handle = (error, { targetPath } = {}) => {
    if (!isChunkLoadError(error)) return false
    if (recoveryInProgress) return true

    const normalizedTarget = normalizeTargetPath(targetPath, location)
    const attemptedAt = now()
    const previous = readRecoveryState(storage)
    const isRepeatedFailure = previous
      && previous.targetPath === normalizedTarget
      && attemptedAt >= previous.attemptedAt
      && attemptedAt - previous.attemptedAt < recoveryWindowMs

    recoveryInProgress = true
    if (isRepeatedFailure) {
      showFallback({
        targetPath: normalizedTarget,
        retry: () => retry(normalizedTarget),
      })
      return true
    }

    writeRecoveryState(storage, {
      targetPath: normalizedTarget,
      attemptedAt,
    })
    reload(normalizedTarget)
    return true
  }

  return { clear, handle }
}

export const installChunkLoadRecovery = (router) => {
  if (typeof window === 'undefined' || !router) return null

  const recovery = createChunkLoadRecovery()
  let pendingTargetPath = ''

  router.beforeEach((to) => {
    pendingTargetPath = to.fullPath
  })

  router.afterEach((to, from, failure) => {
    pendingTargetPath = ''
    if (!failure) recovery.clear(to.fullPath)
  })

  router.onError((error, to) => {
    recovery.handle(error, {
      targetPath: to?.fullPath || pendingTargetPath,
    })
  })

  window.addEventListener('vite:preloadError', (event) => {
    if (!isChunkLoadError(event.payload)) return
    event.preventDefault()
    recovery.handle(event.payload, { targetPath: pendingTargetPath })
  })

  return recovery
}
