import { API_CONFIG } from '@/config/api.js'
import { getCurrentVersion, getDeviceId, getNetworkType } from '@/utils/upgrade.js'

const BASE_STORAGE_KEY = 'mobile_client_log_queue_v1'
const CONSOLE_WRAP_MARK = '__mobileLogReporterWrapped__'
const UNI_LOG_WRAP_MARK = '__mobileLogReporterUniLogWrapped__'

const state = {
  installed: false,
  enabled: false,
  originalConsole: null,
  originalRequest: null,
  originalUniLog: null,
  flushTimer: null,
  consoleGuardTimer: null,
  uniLogGuardTimer: null,
  ensureConsoleWrapped: null,
  ensureUniLogWrapped: null,
  flushing: false,

  flushIntervalMs: 30 * 1000,
  batchSize: 200,
  maxQueueSize: 5000,

  networkType: 'unknown',
  queue: [],
  storageKey: '',
}

const getCurrentRoute = () => {
  try {
    const pages = getCurrentPages()
    const current = pages && pages.length ? pages[pages.length - 1] : null
    return current?.route || 'unknown'
  } catch (e) {
    return 'unknown'
  }
}

const getUserContext = () => {
  const userInfo = uni.getStorageSync('userInfo') || {}
  return {
    userId: userInfo?.id,
    username: userInfo?.username,
  }
}

const safeToString = (v) => {
  if (v === null || v === undefined) return String(v)
  if (typeof v === 'string') return v
  if (v instanceof Error) return v.stack || v.message || String(v)
  try {
    const seen = new WeakSet()
    const s = JSON.stringify(v, (key, value) => {
      if (typeof value === 'object' && value !== null) {
        if (seen.has(value)) return '[Circular]'
        seen.add(value)
      }
      return value
    })
    return s === undefined ? String(v) : s
  } catch (e) {
    try {
      return String(v)
    } catch (e2) {
      return '[Unserializable]'
    }
  }
}

const buildMessage = (args) => {
  const parts = (args || []).map((a) => safeToString(a))
  const msg = parts.join(' ')
  if (msg.length > 20000) return msg.slice(0, 19980) + '...(truncated)'
  return msg
}

const normalizeLevel = (level) => {
  const s = String(level || '').toUpperCase()
  if (s === 'DEBUG' || s === 'INFO' || s === 'WARN' || s === 'ERROR') return s
  return 'INFO'
}

const setConsoleMethod = (name, fn) => {
  try {
    console[name] = fn
  } catch (e) {
    // ignore
  }

  if (console[name] === fn) return true

  try {
    Object.defineProperty(console, name, {
      value: fn,
      writable: true,
      configurable: true,
    })
  } catch (e) {
    // ignore
  }

  return console[name] === fn
}

const isConsoleWrapped = (fn) => !!(fn && fn[CONSOLE_WRAP_MARK])

const setUniLog = (fn) => {
  try {
    uni.__log__ = fn
  } catch (e) {
    // ignore
  }

  if (uni.__log__ === fn) return true

  try {
    Object.defineProperty(uni, '__log__', {
      value: fn,
      writable: true,
      configurable: true,
    })
  } catch (e) {
    // ignore
  }

  return uni.__log__ === fn
}

const isUniLogWrapped = (fn) => !!(fn && fn[UNI_LOG_WRAP_MARK])

const resolveStorageKey = () => {
  if (state.storageKey) return state.storageKey
  const userInfo = uni.getStorageSync('userInfo') || {}
  const userId = userInfo?.id
  return userId ? `${BASE_STORAGE_KEY}_${userId}` : `${BASE_STORAGE_KEY}_unknown`
}

const persistQueue = () => {
  try {
    uni.setStorageSync(resolveStorageKey(), state.queue)
  } catch (e) {
    // ignore
  }
}

const restoreQueue = () => {
  try {
    const stored = uni.getStorageSync(resolveStorageKey())
    if (Array.isArray(stored) && stored.length) {
      state.queue = [...stored, ...state.queue].slice(-state.maxQueueSize)
    }
  } catch (e) {
    // ignore
  }
}

const enqueue = (entry) => {
  state.queue.push(entry)
  if (state.queue.length > state.maxQueueSize) {
    const overflow = state.queue.length - state.maxQueueSize
    state.queue.splice(0, overflow)
    state.queue.push({
      ts: new Date().toISOString(),
      level: 'WARN',
      tag: 'mobileLogReporter',
      message: `日志队列已满，丢弃最旧 ${overflow} 条`,
      route: getCurrentRoute(),
      device_id: getDeviceId(),
      ...getCommonFields(),
    })
  }
  persistQueue()

  if (state.queue.length >= state.batchSize) {
    flush().catch(() => {})
  }
}

const getCommonFields = () => {
  const version = getCurrentVersion()
  return {
    device_id: getDeviceId(),
    app_version_name: version.versionName,
    app_version_code: version.versionCode,
    platform: uni.getSystemInfoSync().platform,
    network_type: state.networkType,
    env: uni.getStorageSync('env') || '',
  }
}

const install = () => {
  if (state.installed) return
  state.installed = true

  state.originalUniLog = typeof uni.__log__ === 'function' ? uni.__log__ : null

  const wrapUniLog = (original) => {
    const wrapped = (level, at, ...args) => {
      try {
        if (state.enabled) {
          const l = String(level || '').toLowerCase()
          const mappedLevel = l === 'error' ? 'ERROR' : l === 'warn' ? 'WARN' : l === 'debug' ? 'DEBUG' : 'INFO'
          const msg = buildMessage(args)
          const message = msg && msg.trim() ? msg : `[${String(level || 'log')}]`
          enqueue({
            ts: new Date().toISOString(),
            level: mappedLevel,
            tag: 'console',
            message,
            route: getCurrentRoute(),
            context: {
              at: at ? String(at) : '',
              level: String(level || ''),
              args: (args || []).map((a) => {
                const s = safeToString(a)
                return s.length > 2000 ? s.slice(0, 1980) + '...(truncated)' : s
              }),
            },
            ...getCommonFields(),
          })
        }
      } catch (e) {
        // ignore
      }

      try {
        return original(level, at, ...args)
      } catch (e) {
        return
      }
    }
    wrapped[UNI_LOG_WRAP_MARK] = true
    return wrapped
  }

  const applyUniLogWrapper = () => {
    if (typeof state.originalUniLog !== 'function') return false
    return setUniLog(wrapUniLog(state.originalUniLog))
  }

  const ensureUniLogWrapped = () => {
    if (typeof uni.__log__ !== 'function') return false
    if (state.originalUniLog == null) {
      state.originalUniLog = uni.__log__
    }
    if (isUniLogWrapped(uni.__log__)) return true
    return applyUniLogWrapper()
  }

  state.ensureUniLogWrapped = ensureUniLogWrapped
  // 优先拦截 uni.__log__（uni-app 编译后 console.* 通常会走这里）
  ensureUniLogWrapped()

  state.originalConsole = {
    log: console.log,
    info: console.info,
    warn: console.warn,
    error: console.error,
    debug: console.debug || console.log,
  }

  const wrapConsole = (level, original) => {
    const wrapped = (...args) => {
      try {
        if (state.enabled) {
          const entry = {
            ts: new Date().toISOString(),
            level: normalizeLevel(level),
            tag: 'console',
            message: buildMessage(args),
            route: getCurrentRoute(),
            context: {
              args: (args || []).map((a) => {
                const s = safeToString(a)
                return s.length > 2000 ? s.slice(0, 1980) + '...(truncated)' : s
              }),
            },
            ...getCommonFields(),
          }
          enqueue(entry)
        }
      } catch (e) {
        // ignore
      }
      return original.apply(console, args)
    }
    wrapped[CONSOLE_WRAP_MARK] = true
    return wrapped
  }

  const applyConsoleWrappers = () => {
    return [
      setConsoleMethod('log', wrapConsole('INFO', state.originalConsole.log)),
      setConsoleMethod('info', wrapConsole('INFO', state.originalConsole.info)),
      setConsoleMethod('warn', wrapConsole('WARN', state.originalConsole.warn)),
      setConsoleMethod('error', wrapConsole('ERROR', state.originalConsole.error)),
      setConsoleMethod('debug', wrapConsole('DEBUG', state.originalConsole.debug)),
    ].every(Boolean)
  }

  const ensureConsoleWrapped = () => {
    const ok =
      isConsoleWrapped(console.log) &&
      isConsoleWrapped(console.info) &&
      isConsoleWrapped(console.warn) &&
      isConsoleWrapped(console.error) &&
      isConsoleWrapped(console.debug)
    if (ok) return true
    return applyConsoleWrappers()
  }

  state.ensureConsoleWrapped = ensureConsoleWrapped

  const wrappedOk = ensureConsoleWrapped()
  if (!wrappedOk) {
    enqueue({
      ts: new Date().toISOString(),
      level: 'WARN',
      tag: 'mobileLogReporter',
      message: 'console 方法无法拦截：将只能记录 uni.__log__ 输出',
      route: getCurrentRoute(),
      ...getCommonFields(),
    })
  }

  // 仅采集 uni.__log__ / console 输出，不采集 API 请求日志
  state.originalRequest = state.originalRequest || uni.request
}

const updateNetworkType = async () => {
  try {
    state.networkType = await getNetworkType()
  } catch (e) {
    state.networkType = 'unknown'
  }
}

export const flush = async () => {
  if (!state.enabled) return
  if (state.flushing) return

  const token = uni.getStorageSync('token')
  if (!token) return

  state.flushing = true
  try {
    while (state.queue.length > 0) {
      const batch = state.queue.slice(0, state.batchSize)
      const res = await state.originalRequest.call(uni, {
        url: `${API_CONFIG.BASE_URL}/api/mobile-logs/batch`,
        method: 'POST',
        header: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          'X-Client': 'uniapp',
        },
        data: { logs: batch },
        timeout: 15000,
      })

      if (res?.statusCode === 200 && res?.data?.success) {
        state.queue.splice(0, batch.length)
        persistQueue()
        continue
      }
      break
    }
  } catch (e) {
    // keep queue
  } finally {
    state.flushing = false
    persistQueue()
  }
}

export const startMobileLogReporter = async (opts = {}) => {
  state.flushIntervalMs = typeof opts.flushIntervalMs === 'number' ? opts.flushIntervalMs : state.flushIntervalMs
  state.batchSize = typeof opts.batchSize === 'number' ? opts.batchSize : state.batchSize
  state.maxQueueSize = typeof opts.maxQueueSize === 'number' ? opts.maxQueueSize : state.maxQueueSize

  install()

  const userInfo = uni.getStorageSync('userInfo') || {}
  state.storageKey = userInfo?.id ? `${BASE_STORAGE_KEY}_${userInfo.id}` : `${BASE_STORAGE_KEY}_unknown`
  state.queue = []
  restoreQueue()

  state.enabled = true

  await updateNetworkType()
  try {
    uni.onNetworkStatusChange((res) => {
      state.networkType = res?.networkType || (res?.isConnected ? 'unknown' : 'none')
      if (state.enabled) {
        flush().catch(() => {})
      }
    })
  } catch (e) {
    // ignore
  }

  if (state.flushTimer) clearInterval(state.flushTimer)
  state.flushTimer = setInterval(() => {
    flush().catch(() => {})
  }, state.flushIntervalMs)

  if (state.consoleGuardTimer) clearInterval(state.consoleGuardTimer)
  state.consoleGuardTimer = setInterval(() => {
    try {
      state.ensureConsoleWrapped && state.ensureConsoleWrapped()
    } catch (e) {
      // ignore
    }
  }, 5000)

  if (state.uniLogGuardTimer) clearInterval(state.uniLogGuardTimer)
  state.uniLogGuardTimer = setInterval(() => {
    try {
      state.ensureUniLogWrapped && state.ensureUniLogWrapped()
    } catch (e) {
      // ignore
    }
  }, 5000)

  enqueue({
    ts: new Date().toISOString(),
    level: 'INFO',
    tag: 'mobileLogReporter',
    message: '移动端日志采集已启动（登录后）',
    route: getCurrentRoute(),
    ...getCommonFields(),
  })

  flush().catch(() => {})
}

export const stopMobileLogReporter = async () => {
  state.enabled = false
  if (state.flushTimer) {
    clearInterval(state.flushTimer)
    state.flushTimer = null
  }
  if (state.consoleGuardTimer) {
    clearInterval(state.consoleGuardTimer)
    state.consoleGuardTimer = null
  }
  if (state.uniLogGuardTimer) {
    clearInterval(state.uniLogGuardTimer)
    state.uniLogGuardTimer = null
  }
  persistQueue()
}
