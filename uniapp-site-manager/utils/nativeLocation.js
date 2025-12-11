const STORAGE_KEY = 'native_location_cache_v1'
const DEFAULT_CACHE_MAX_AGE_MS = 10 * 60 * 1000 // 10分钟

let pluginInstance = null

const getNativeLocationPlugin = () => {
  try {
    if (pluginInstance) return pluginInstance
    if (typeof uni === 'undefined' || typeof uni.requireNativePlugin !== 'function') {
      console.warn('[nativeLocation] uni 或 requireNativePlugin 不可用')
      return null
    }
    const plugin = uni.requireNativePlugin('my-location-plugin')
    if (!plugin) {
      console.warn('[nativeLocation] 原生定位插件 my-location-plugin 未加载')
      return null
    }
    pluginInstance = plugin
    return pluginInstance
  } catch (error) {
    console.error('[nativeLocation] 获取原生插件失败:', error)
    return null
  }
}

const safeParseJSON = (input) => {
  if (!input) return null
  if (typeof input === 'object') return input
  if (typeof input !== 'string') return null
  try {
    return JSON.parse(input)
  } catch (error) {
    console.warn('[nativeLocation] JSON 解析失败:', error)
    return null
  }
}

const normalizeLocationData = (raw) => {
  if (!raw) return null
  const latitude = Number(raw.latitude)
  const longitude = Number(raw.longitude)
  if (!isFinite(latitude) || !isFinite(longitude)) return null
  const normalized = {
    ...raw,
    latitude,
    longitude,
  }
  return normalized
}

const isValidCoordinate = (data) => {
  if (!data) return false
  const { latitude, longitude } = data
  if (typeof latitude !== 'number' || typeof longitude !== 'number') return false
  if (!isFinite(latitude) || !isFinite(longitude)) return false
  // 排除 0,0 这种明显无效坐标
  if (latitude === 0 && longitude === 0) return false
  return true
}

const loadOfflineCache = () => {
  try {
    if (typeof uni === 'undefined' || typeof uni.getStorageSync !== 'function') return null
    const raw = uni.getStorageSync(STORAGE_KEY)
    console.log('[nativeLocation] 读取本地缓存原始值:', raw)
    const parsed = safeParseJSON(raw) || raw
    if (!parsed || typeof parsed !== 'object') return null
    if (!parsed.data) return null
    const data = normalizeLocationData(parsed.data)
    if (!isValidCoordinate(data)) return null
    const timestamp = typeof parsed.timestamp === 'number' ? parsed.timestamp : Date.now()
    return {
      data,
      address: parsed.address || null,
      timestamp,
    }
  } catch (error) {
    console.warn('[nativeLocation] 读取缓存失败:', error)
    return null
  }
}

const saveOfflineCache = (result) => {
  try {
    if (!result || !result.data) return
    if (typeof uni === 'undefined' || typeof uni.setStorageSync !== 'function') return
    const data = normalizeLocationData(result.data)
    if (!isValidCoordinate(data)) {
      console.log('[nativeLocation] 写入缓存时发现坐标无效，跳过:', data)
      return
    }
    const payload = {
      data,
      address: result.address || null,
      timestamp: Date.now(),
    }
    console.log('[nativeLocation] 写入本地缓存:', payload)
    uni.setStorageSync(STORAGE_KEY, payload)
  } catch (error) {
    console.warn('[nativeLocation] 写入缓存失败:', error)
  }
}

const isFresh = (timestamp, maxAgeMs) => {
  if (typeof timestamp !== 'number') return false
  return Date.now() - timestamp < maxAgeMs
}

const tryGetLocationSyncFromPlugin = (plugin, cacheMaxAgeMs) => {
  if (!plugin || typeof plugin.getLocationSync !== 'function') return null
  try {
    const raw = plugin.getLocationSync()
    const parsed = safeParseJSON(raw) || raw
    if (!parsed || !parsed.success || !parsed.data) return null
    const data = normalizeLocationData(parsed.data)
    if (!isValidCoordinate(data)) return null
    const time = typeof data.time === 'number' ? data.time : Date.now()
    if (!isFresh(time, cacheMaxAgeMs)) {
      console.log('[nativeLocation] 同步位置已过期，忽略')
      return null
    }
    return {
      data,
      address: null,
      timestamp: time,
    }
  } catch (error) {
    console.warn('[nativeLocation] getLocationSync 调用失败:', error)
    return null
  }
}

const pickOfflineFallback = (syncLoc, cachedLoc, cacheMaxAgeMs) => {
  const freshSync = syncLoc && isValidCoordinate(syncLoc.data) && isFresh(syncLoc.timestamp, cacheMaxAgeMs)
  const freshCache = cachedLoc && isValidCoordinate(cachedLoc.data) && isFresh(cachedLoc.timestamp, cacheMaxAgeMs)

  if (freshSync) {
    const data = syncLoc.data
    const address = freshCache ? cachedLoc.address || null : null
    console.log('[nativeLocation] 命中同步离线位置:', {
      data,
      hasCachedAddress: !!address,
    })
    return {
      success: true,
      code: 0,
      data,
      address,
      message: freshCache ? '使用缓存地址的离线位置' : '使用离线位置(无地址)',
      source: 'offline',
    }
  }

  if (freshCache) {
    console.log('[nativeLocation] 命中历史缓存位置:', {
      data: cachedLoc.data,
      hasAddress: !!cachedLoc.address,
    })
    return {
      success: true,
      code: 0,
      data: cachedLoc.data,
      address: cachedLoc.address || null,
      message: '使用历史缓存位置',
      source: 'offline',
    }
  }

  return null
}

const buildSuccessResult = (data, address, message, source) => {
  return {
    success: true,
    code: 0,
    data,
    address: address || null,
    message,
    source: source || 'online',
  }
}

/**
 * 离线优先 + 在线获取地址（整体15秒超时）
 * 在线：getLocation + reverseGeocode
 * 离线：getLocationSync + 本地缓存
 */
export const getLocationWithAddressOfflineFirst = async (options = {}) => {
  const timeoutMs = typeof options.timeoutMs === 'number' ? options.timeoutMs : 15000
  const cacheMaxAgeMs = typeof options.cacheMaxAgeMs === 'number' ? options.cacheMaxAgeMs : DEFAULT_CACHE_MAX_AGE_MS

  const plugin = getNativeLocationPlugin()
  console.log('[nativeLocation] 调用封装开始:', { timeoutMs, cacheMaxAgeMs, hasPlugin: !!plugin })
  const cachedLoc = loadOfflineCache()
  const syncLoc = tryGetLocationSyncFromPlugin(plugin, cacheMaxAgeMs)
  const offlineFallback = pickOfflineFallback(syncLoc, cachedLoc, cacheMaxAgeMs)
  console.log('[nativeLocation] 离线候选结果:', {
    hasSync: !!syncLoc,
    hasCached: !!cachedLoc,
    useOfflineFallback: !!offlineFallback,
  })

  let timeoutId

  const onlinePromise = new Promise((resolve) => {
    if (!plugin || typeof plugin.getLocation !== 'function') {
      console.warn('[nativeLocation] 原生插件不可用或不支持 getLocation')
      resolve(null)
      return
    }

    let settled = false
    const safeResolve = (val) => {
      if (settled) return
      settled = true
      resolve(val)
    }

    try {
      plugin.getLocation((locationResult) => {
        if (settled) return
        const parsed = safeParseJSON(locationResult) || locationResult
        if (!parsed || !parsed.success || !parsed.data) {
          console.warn('[nativeLocation] 在线 getLocation 失败:', parsed)
          safeResolve(null)
          return
        }

        const data = normalizeLocationData(parsed.data)
        if (!isValidCoordinate(data)) {
          console.warn('[nativeLocation] 在线 getLocation 返回坐标无效:', data)
          safeResolve(null)
          return
        }

        if (!plugin.reverseGeocode || typeof plugin.reverseGeocode !== 'function') {
          const result = buildSuccessResult(data, null, '获取位置成功，地址解析接口不可用', 'online')
          saveOfflineCache(result)
          safeResolve(result)
          return
        }

        try {
          plugin.reverseGeocode(
            {
              latitude: data.latitude,
              longitude: data.longitude,
            },
            (addressResult) => {
              if (settled) return
              const parsedAddr = safeParseJSON(addressResult) || addressResult
              let address = null
              let message = '获取位置成功'

              if (parsedAddr && parsedAddr.success && parsedAddr.data) {
                address = parsedAddr.data
                message = '获取位置和地址成功'
              } else {
                message = '获取位置成功，地址解析失败'
              }

              const finalResult = buildSuccessResult(data, address, message, 'online')
              saveOfflineCache(finalResult)
              safeResolve(finalResult)
            },
          )
        } catch (error) {
          console.warn('[nativeLocation] reverseGeocode 调用异常:', error)
          const result = buildSuccessResult(data, null, '获取位置成功，地址解析异常', 'online')
          saveOfflineCache(result)
          safeResolve(result)
        }
      })
    } catch (error) {
      console.error('[nativeLocation] getLocation 调用异常:', error)
      safeResolve(null)
    }
  })

  const timeoutPromise = new Promise((resolve) => {
    timeoutId = setTimeout(() => {
      resolve(null)
    }, timeoutMs)
  })

  const onlineWithTimeout = Promise.race([onlinePromise, timeoutPromise])

  // 如果有离线结果，优先立刻返回离线结果，同时在后台执行在线刷新
  if (offlineFallback && offlineFallback.success && isValidCoordinate(offlineFallback.data)) {
    console.log('[nativeLocation] 立即返回离线结果，并在后台刷新在线定位:', {
      offlineData: offlineFallback.data,
      hasAddress: !!offlineFallback.address,
    })
    onlineWithTimeout
      .then((onlineResult) => {
        clearTimeout(timeoutId)

        // 在线获取成功，更新缓存；如无地址则提示，但不影响已完成的流程
        if (onlineResult && onlineResult.success && isValidCoordinate(onlineResult.data)) {
          console.log('[nativeLocation] 后台在线刷新成功:', {
            data: onlineResult.data,
            hasAddress: !!onlineResult.address,
          })
          if (!onlineResult.address) {
            try {
              uni.showToast({
                title: '地址获取失败，已使用GPS坐标',
                icon: 'none',
                duration: 2000,
              })
            } catch (error) {
              console.warn('[nativeLocation] toast 调用失败:', error)
            }
          }
        } else {
          // 在线获取失败或超时，仅提示，不阻塞已经使用离线结果的流程
          console.log('[nativeLocation] 后台在线刷新失败或超时:', onlineResult)
          try {
            const title = offlineFallback.address
              ? '在线定位失败，已使用上次位置'
              : '在线定位失败，已使用上次GPS坐标'
            uni.showToast({
              title,
              icon: 'none',
              duration: 2000,
            })
          } catch (error) {
            console.warn('[nativeLocation] toast 调用失败:', error)
          }
        }
      })
      .catch((error) => {
        console.warn('[nativeLocation] 在线刷新异常:', error)
      })

    return offlineFallback
  }

  // 没有离线结果，必须等待本次在线结果（最多15秒）
  const onlineResult = await onlineWithTimeout
  clearTimeout(timeoutId)

  if (onlineResult && onlineResult.success && isValidCoordinate(onlineResult.data)) {
    console.log('[nativeLocation] 无离线命中，使用本次在线结果:', {
      data: onlineResult.data,
      hasAddress: !!onlineResult.address,
    })
    if (!onlineResult.address) {
      try {
        uni.showToast({
          title: '地址获取失败，已使用GPS坐标',
          icon: 'none',
          duration: 2000,
        })
      } catch (error) {
        console.warn('[nativeLocation] toast 调用失败:', error)
      }
    }
    return onlineResult
  }

  return {
    success: false,
    code: -1,
    message: '无法获取GPS坐标，请检查定位权限和系统定位开关',
    error: 'no_location',
  }
}
