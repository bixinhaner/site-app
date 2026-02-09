/**
 * 定位策略工具
 *
 * 支持两种模式：
 * - native：使用原生插件封装（getLocationWithAddressOfflineFirst）
 * - baidu：使用 uni.getLocation(wgs84) + 后端百度逆地理接口
 *
 * 模式由后端 SystemConfig(key='mobile_settings') 控制：
 *   - location_mode.default: 全局默认
 *   - location_mode.per_role: 按角色覆盖
 *   - location_mode.per_user: 按用户覆盖
 *
 * APP 侧：
 *   - 启动时可通过 GET /api/system/location-mode 读取“全局默认模式”作为兜底
 *   - 登录后建议由 userStore 调用 /api/system/mobile-settings/effective，
 *     并使用 setLocationMode 更新为“对当前用户生效”的模式。
 *
 * 默认模式为 'baidu'。调用方只需使用 getLocationWithAddressStrategy 即可，
 * 无需关心底层实现或生效范围。
 */

import { buildApiUrl } from '@/config/api.js'
import { getLocationWithAddressOfflineFirst } from './nativeLocation.js'

// 当前定位模式，默认 baidu
let locationMode = 'baidu'
// 是否允许检查详情本地上传图片，默认允许
let allowLocalPhotoUpload = true
// 检查详情“本地/相册上传”照片水印是否携带经纬度和地址，默认携带（沿用现状）
let localUploadWatermarkWithGeo = true
// 是否启用“实拍坐标 vs 规划坐标”距离比对
let enablePhotoLocationDistanceCheck = true
// 超距是否阻断上传
let distanceExceedBlockUpload = false
// 超距阈值（米）
let photoLocationDistanceThresholdM = 100

export const getLocationMode = () => locationMode

export const setLocationMode = (mode) => {
  const value = (mode || '').trim().toLowerCase()
  if (value === 'native' || value === 'baidu') {
    locationMode = value
  } else {
    console.warn('[locationStrategy] 非法模式，忽略:', mode)
  }
}

export const getAllowLocalPhotoUpload = () => allowLocalPhotoUpload

export const setAllowLocalPhotoUpload = (flag) => {
  // 任何非严格 false 的传入都视为允许，避免因为后端缺字段导致意外禁用
  allowLocalPhotoUpload = flag !== false
}

export const getLocalUploadWatermarkWithGeo = () => localUploadWatermarkWithGeo

export const setLocalUploadWatermarkWithGeo = (flag) => {
  // 任何非严格 false 的传入都视为携带，避免因为后端缺字段导致意外禁用
  localUploadWatermarkWithGeo = flag !== false
}

export const getEnablePhotoLocationDistanceCheck = () => enablePhotoLocationDistanceCheck

export const setEnablePhotoLocationDistanceCheck = (flag) => {
  enablePhotoLocationDistanceCheck = flag !== false
}

export const getDistanceExceedBlockUpload = () => distanceExceedBlockUpload

export const setDistanceExceedBlockUpload = (flag) => {
  distanceExceedBlockUpload = flag === true
}

export const getPhotoLocationDistanceThresholdM = () => photoLocationDistanceThresholdM

export const setPhotoLocationDistanceThresholdM = (value) => {
  const parsed = Number(value)
  if (!isFinite(parsed)) {
    photoLocationDistanceThresholdM = 100
    return
  }
  const rounded = Math.round(parsed)
  photoLocationDistanceThresholdM = Math.max(1, Math.min(10000, rounded))
}

/**
 * 在 App 启动时调用，向后端拉取“全局默认定位模式”作为兜底。
 * 登录后，userStore 会根据当前用户再调用 /mobile-settings/effective
 * 覆盖为对该用户生效的模式。
 */
export const initLocationMode = async () => {
  try {
    const url = buildApiUrl('/api/system/location-mode')
    console.log('[locationStrategy] 初始化定位模式, 请求:', url)

    const res = await new Promise((resolve, reject) => {
      uni.request({
        url,
        method: 'GET',
        success: resolve,
        fail: reject,
      })
    })

    if (res.statusCode === 200 && res.data && res.data.mode) {
      const mode = String(res.data.mode || '').trim().toLowerCase()
      if (mode === 'native' || mode === 'baidu') {
        locationMode = mode
        console.log('[locationStrategy] 成功获取定位模式:', mode)
      } else {
        console.warn('[locationStrategy] 后端返回的定位模式非法，使用默认 baidu:', res.data)
      }
    } else {
      console.warn('[locationStrategy] 获取定位模式失败，HTTP状态:', res.statusCode, res.data)
    }
  } catch (error) {
    console.warn('[locationStrategy] 初始化定位模式失败，使用默认 baidu:', error)
  }
}

const buildErrorResult = (message, code = -1, error = null) => {
  return {
    success: false,
    code,
    message: message || '无法获取GPS坐标，请检查定位权限和系统定位开关',
    error: error || 'no_location',
  }
}

const normalizeBaiduAddress = (payload) => {
  if (!payload) return null

  const address = payload.address || ''
  const comp = payload.address_component || {}

  return {
    formattedAddress: address,
    country: comp.country || '',
    province: comp.province || '',
    city: comp.city || '',
    district: comp.district || '',
    street: comp.street || '',
    // 统一为 streetNumber，方便与原生插件返回结构共用
    streetNumber: comp.street_number || comp.streetNumber || '',
  }
}

/**
 * 使用 Baidu 模式获取位置和地址：
 * - uni.getLocation(type='wgs84', geocode: false) 获取坐标
 * - 后端 /api/geo/baidu-reverse 获取地址
 *
 * 返回结构与 getLocationWithAddressOfflineFirst 尽量保持一致：
 * {
 *   success: true,
 *   code: 0,
 *   data: { latitude, longitude, accuracy, altitude, speed, provider },
 *   address: { formattedAddress, country, province, city, district, street, streetNumber },
 *   message: '...',
 *   source: 'online'
 * }
 */
const getLocationWithBaidu = async (options = {}) => {
  const timeoutMs = typeof options.timeoutMs === 'number' ? options.timeoutMs : 15000

  try {
    console.log('[locationStrategy] 使用 Baidu 模式获取位置...')

    const loc = await new Promise((resolve, reject) => {
      uni.getLocation({
        type: 'wgs84',
        geocode: false,
        success: resolve,
        fail: reject,
      })
    })

    const latitude = Number(loc.latitude)
    const longitude = Number(loc.longitude)

    if (!isFinite(latitude) || !isFinite(longitude) || (latitude === 0 && longitude === 0)) {
      console.warn('[locationStrategy] Baidu 模式返回坐标无效:', { latitude, longitude })
      return buildErrorResult('无法获取GPS坐标，请检查定位权限和系统定位开关')
    }

    const baseData = {
      latitude,
      longitude,
      accuracy: Number(loc.accuracy || 0),
      altitude: Number(loc.altitude || 0),
      speed: Number(loc.speed || 0),
      provider: 'baidu',
    }

    // 调用后端 Baidu 逆地理接口
    let addressObj = null
    let message = '获取位置成功，地址信息不可用'

    try {
      const url = buildApiUrl('/api/geo/baidu-reverse')
      console.log('[locationStrategy] 调用后端 Baidu 逆地理:', url, {
        lat: latitude,
        lng: longitude,
      })

      const resp = await new Promise((resolve, reject) => {
        uni.request({
          url,
          method: 'GET',
          timeout: timeoutMs,
          data: {
            lat: latitude,
            lng: longitude,
          },
          success: resolve,
          fail: reject,
        })
      })

      if (resp.statusCode === 200 && resp.data) {
        addressObj = normalizeBaiduAddress(resp.data)
        if (addressObj && addressObj.formattedAddress) {
          message = '获取位置和地址成功'
        } else {
          message = '获取位置成功，地址解析结果为空'
        }
      } else {
        console.warn('[locationStrategy] Baidu 逆地理失败:', resp.statusCode, resp.data)
        message = '获取位置成功，地址解析失败'
      }
    } catch (geoError) {
      console.warn('[locationStrategy] Baidu 逆地理调用异常:', geoError)
      message = '获取位置成功，地址解析异常'
    }

    return {
      success: true,
      code: 0,
      data: baseData,
      address: addressObj,
      message,
      source: 'online',
    }
  } catch (error) {
    console.error('[locationStrategy] Baidu 模式定位失败:', error)
    const errMsg = error && (error.errMsg || error.message)
    return buildErrorResult(errMsg, -1, errMsg || error)
  }
}

/**
 * 统一定位入口。
 *
 * - 当 mode = 'native' 时，直接委托给 getLocationWithAddressOfflineFirst
 * - 当 mode = 'baidu' 时，使用 uni.getLocation + 后端 Baidu 逆地理
 *
 * 调用方请遵循与 getLocationWithAddressOfflineFirst 相同的使用方式：
 *
 * const result = await getLocationWithAddressStrategy()
 * if (!result.success || !result.data) throw new Error(result.message)
 */
export const getLocationWithAddressStrategy = async (options = {}) => {
  const mode = locationMode === 'native' ? 'native' : 'baidu'
  console.log('[locationStrategy] 当前定位模式:', mode)

  if (mode === 'native') {
    try {
      const result = await getLocationWithAddressOfflineFirst(options)
      return result
    } catch (error) {
      console.error('[locationStrategy] 原生模式定位异常:', error)
      const msg = error && error.message ? error.message : '原生定位失败'
      return buildErrorResult(msg, -1, msg)
    }
  }

  // mode === 'baidu'
  return await getLocationWithBaidu(options)
}
