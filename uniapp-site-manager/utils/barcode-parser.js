/**
 * 条码解析工具
 * 支持多种扫码格式解析
 */

import i18n from './i18n.js'

const t = (key, params = {}) => {
  try {
    return i18n?.global?.t ? i18n.global.t(key, params) : key
  } catch (error) {
    return key
  }
}

const BARCODE_PARSER_DEBUG_STORAGE_KEY = 'debug_barcode_parser'
let barcodeParserDebugEnabledCache = null

const normalizeBoolean = (value) => {
  if (value === true) return true
  if (value === false) return false
  if (value === 1) return true
  if (value === 0) return false
  if (typeof value === 'string') {
    const v = value.trim().toLowerCase()
    if (v === '1' || v === 'true' || v === 'yes' || v === 'on') return true
    if (v === '0' || v === 'false' || v === 'no' || v === 'off') return false
  }
  return false
}

export function isBarcodeParserDebugEnabled() {
  if (barcodeParserDebugEnabledCache !== null) return barcodeParserDebugEnabledCache
  try {
    if (typeof uni === 'undefined' || !uni.getStorageSync) {
      barcodeParserDebugEnabledCache = false
      return barcodeParserDebugEnabledCache
    }
    const raw = uni.getStorageSync(BARCODE_PARSER_DEBUG_STORAGE_KEY)
    barcodeParserDebugEnabledCache = normalizeBoolean(raw)
    return barcodeParserDebugEnabledCache
  } catch (e) {
    barcodeParserDebugEnabledCache = false
    return barcodeParserDebugEnabledCache
  }
}

export function setBarcodeParserDebugEnabled(enabled) {
  const next = Boolean(enabled)
  barcodeParserDebugEnabledCache = next
  try {
    if (typeof uni !== 'undefined' && uni.setStorageSync) {
      uni.setStorageSync(BARCODE_PARSER_DEBUG_STORAGE_KEY, next)
    }
  } catch (e) {
    // ignore
  }
  return next
}

const debugLog = (...args) => {
  if (!isBarcodeParserDebugEnabled()) return
  // eslint-disable-next-line no-console
  console.log(...args)
}

/**
 * 解析扫码结果
 * @param {string} scanResult 扫码原始结果
 * @returns {object} 解析后的结果
 */
export function parseBarcode(scanResult) {
  debugLog('🔍 [parseBarcode] 开始解析条码')
  debugLog('🔍 [parseBarcode] 输入scanResult:', scanResult)
  debugLog('🔍 [parseBarcode] scanResult类型:', typeof scanResult)
  
  if (!scanResult || typeof scanResult !== 'string') {
    debugLog('❌ [parseBarcode] 输入无效')
    return {
      success: false,
      error: t('stock.scanResultEmpty'),
      rawData: scanResult
    }
  }

  const result = {
    success: true,
    sn: null,
    mac1: null,
    mac2: null,
    mac3: null,
    mac4: null,
    rawData: scanResult.trim(),
    format: 'unknown'
  }

  const trimmed = scanResult.trim()
  debugLog('🔍 [parseBarcode] 处理后的字符串:', trimmed)
  debugLog('🔍 [parseBarcode] 字符串长度:', trimmed.length)

  try {
    // 格式1: SN,MAC 或 SN,MAC1,MAC2,MAC3,MAC4 (逗号分隔)
    // 例如: 1211000124233API0001,48BF742DDF43
    // 例如: 120200089725BKB0030,48BF743904E0,48BF743904FE,48BF7439051C,48BF7439053A
    debugLog('🔍 [parseBarcode] 检查格式1: SN,MAC(1-4) (逗号分隔)')
    debugLog('🔍 [parseBarcode] 包含逗号?:', trimmed.includes(','))
    debugLog('🔍 [parseBarcode] 包含冒号?:', trimmed.includes(':'))
    
    if (trimmed.includes(',') && !trimmed.includes(':')) {
      debugLog('✅ [parseBarcode] 匹配格式1')
      const parts = trimmed.split(',').map(part => part.trim())
      debugLog('🔍 [parseBarcode] 分割结果:', parts)
      debugLog('🔍 [parseBarcode] 分割数量:', parts.length)
      
      if (parts.length >= 2 && parts.length <= 5) {
        result.sn = parts[0]
        result.mac1 = parts[1] || null
        result.mac2 = parts[2] || null
        result.mac3 = parts[3] || null
        result.mac4 = parts[4] || null
        result.format = parts.length === 2 ? 'sn_mac_comma' : 'sn_mac4_comma'
        debugLog(`✅ [parseBarcode] 格式1(${parts.length}段)解析成功:`, result)
        return result
      } else {
        debugLog('❌ [parseBarcode] 格式1分割数量不正确（期望2-5）')
      }
    }

    // 格式2: MAC1:xxx, MAC2:xxx, SN:xxx (键值对格式)
    // 例如: MAC1:48BF743244E69, MAC2:48BF74324E6B, SN:12020008532555DB0002
    debugLog('🔍 [parseBarcode] 检查格式2: 键值对格式')
    if (trimmed.includes(':')) {
      debugLog('✅ [parseBarcode] 匹配格式2')
      const pairs = trimmed.split(',').map(pair => pair.trim())
      debugLog('🔍 [parseBarcode] 键值对列表:', pairs)
      
      for (const pair of pairs) {
        debugLog('🔍 [parseBarcode] 处理键值对:', pair)
        const [key, value] = pair.split(':').map(part => part.trim())
        debugLog('🔍 [parseBarcode] 键:', key, '值:', value)
        
        if (key && value) {
          switch (key.toUpperCase()) {
            case 'SN':
              result.sn = value
              debugLog('🔍 [parseBarcode] 设置SN:', value)
              break
            case 'MAC':
            case 'MAC1':
              result.mac1 = value
              debugLog('🔍 [parseBarcode] 设置MAC1:', value)
              break
            case 'MAC2':
              result.mac2 = value
              debugLog('🔍 [parseBarcode] 设置MAC2:', value)
              break
            case 'MAC3':
              result.mac3 = value
              debugLog('🔍 [parseBarcode] 设置MAC3:', value)
              break
            case 'MAC4':
              result.mac4 = value
              debugLog('🔍 [parseBarcode] 设置MAC4:', value)
              break
          }
        }
      }
      
      debugLog('🔍 [parseBarcode] 格式2解析后:', result)
      if (result.sn) {
        result.format = 'key_value_pairs'
        debugLog('✅ [parseBarcode] 格式2解析成功')
        return result
      } else {
        debugLog('❌ [parseBarcode] 格式2未找到SN')
      }
    }

    // 格式3: 纯SN (条形码Code128)
    // 例如: 12020008532555DB0002
    debugLog('🔍 [parseBarcode] 检查格式3: 纯SN')
    if (!trimmed.includes(',') && !trimmed.includes(':')) {
      debugLog('✅ [parseBarcode] 匹配格式3')
      debugLog('🔍 [parseBarcode] 长度检查:', trimmed.length, '>=8?:', trimmed.length >= 8)
      debugLog('🔍 [parseBarcode] 字符检查:', /^[A-Za-z0-9]+$/.test(trimmed))
      debugLog('🔍 [parseBarcode] 全数字?:', /^\d+$/.test(trimmed))
      
      // 简单验证SN格式（可根据实际业务规则调整）
      if (validateSerialNumber(trimmed)) {
        result.sn = trimmed
        result.format = 'pure_sn'
        debugLog('✅ [parseBarcode] 格式3解析成功:', result)
        return result
      } else if (/^\d+$/.test(trimmed) && trimmed.length >= 8) {
        // 纯数字结果直接判为无效（避免误扫）
        result.success = false
        result.error = t('stock.invalidBarcode')
        debugLog('❌ [parseBarcode] 格式3为纯数字，判为无效:', result)
        return result
      } else {
        debugLog('❌ [parseBarcode] 格式3验证失败')
      }
    }

    // 如果都不匹配，返回错误
    debugLog('❌ [parseBarcode] 所有格式都不匹配')
    result.success = false
    result.error = t('stock.barcodeFormatUnsupported')
    debugLog('❌ [parseBarcode] 返回错误结果:', result)
    return result

  } catch (error) {
    debugLog('❌ [parseBarcode] 异常:', error)
    return {
      success: false,
      error: t('stock.barcodeParseFailed', { error: error.message }),
      rawData: scanResult
    }
  }
}

/**
 * 验证MAC地址格式
 * @param {string} mac MAC地址
 * @returns {boolean} 是否有效
 */
export function validateMacAddress(mac) {
  if (!mac) return false
  
  // 支持多种MAC地址格式
  const macPatterns = [
    /^[A-Fa-f0-9]{12}$/, // 12位无分隔符: 48BF742DDF43
    /^([A-Fa-f0-9]{2}[:-]){5}[A-Fa-f0-9]{2}$/, // 标准格式: 48:BF:74:2D:DF:43
    /^([A-Fa-f0-9]{4}\.){2}[A-Fa-f0-9]{4}$/ // Cisco格式: 48BF.742D.DF43
  ]
  
  return macPatterns.some(pattern => pattern.test(mac))
}

/**
 * 格式化MAC地址显示
 * @param {string} mac 原始MAC地址
 * @returns {string} 格式化后的MAC地址
 */
export function formatMacAddress(mac) {
  if (!mac) return ''
  
  // 移除所有分隔符
  const cleanMac = mac.replace(/[:\-\.]/g, '').toUpperCase()
  
  // 验证长度
  if (cleanMac.length !== 12) return mac
  
  // 格式化为 XX:XX:XX:XX:XX:XX
  return cleanMac.replace(/(.{2})/g, '$1:').slice(0, -1)
}

/**
 * 验证SN格式
 * @param {string} sn 序列号
 * @returns {boolean} 是否有效
 */
export function validateSerialNumber(sn) {
  if (!sn) return false

  const trimmed = String(sn).trim()

  // 纯SN不允许全数字（避免误扫 EAN8/EAN13 或局部二维码导致随机数字通过）
  if (/^\d+$/.test(trimmed)) return false

  // 基本验证：长度8-30位，只包含字母数字
  return trimmed.length >= 8 && trimmed.length <= 30 && /^[A-Za-z0-9]+$/.test(trimmed)
}

/**
 * 获取解析结果摘要
 * @param {object} parseResult 解析结果
 * @returns {string} 摘要文本
 */
export function getParseResultSummary(parseResult) {
  if (!parseResult.success) {
    return parseResult.error || '解析失败'
  }

  const parts = []
  
  if (parseResult.sn) {
    parts.push(`SN: ${parseResult.sn}`)
  }
  
  if (parseResult.mac1) {
    parts.push(`MAC1: ${formatMacAddress(parseResult.mac1)}`)
  }
  
  if (parseResult.mac2) {
    parts.push(`MAC2: ${formatMacAddress(parseResult.mac2)}`)
  }

  if (parseResult.mac3) {
    parts.push(`MAC3: ${formatMacAddress(parseResult.mac3)}`)
  }

  if (parseResult.mac4) {
    parts.push(`MAC4: ${formatMacAddress(parseResult.mac4)}`)
  }

  return parts.join(' | ') || '无有效数据'
}

/**
 * 检查是否为有效的扫码结果
 * @param {object} parseResult 解析结果
 * @returns {boolean} 是否有效
 */
export function isValidParseResult(parseResult) {
  return parseResult.success && 
         parseResult.sn && 
         validateSerialNumber(parseResult.sn)
}
