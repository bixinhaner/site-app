export const ScanDeviceCodeError = {
  UNSUPPORTED_SCAN_TYPE: 'unsupported_scan_type',
  EMPTY_RESULT: 'empty_result',
  SCAN_FAILED: 'scan_failed',
}

export function normalizeScanType(value) {
  return String(value || '')
    .trim()
    .toUpperCase()
    .replace(/[-\\s]/g, '_')
}

export const DEVICE_ALLOWED_SCAN_TYPES = new Set([
  'QR_CODE',
  'QRCODE',
  'QR',
  'CODE_128',
  'CODE128',
])

export function isAllowedDeviceScanType(scanType) {
  const normalized = normalizeScanType(scanType)
  return Boolean(normalized) && DEVICE_ALLOWED_SCAN_TYPES.has(normalized)
}

export async function scanDeviceCode(options = {}) {
  const scanType = Array.isArray(options?.scanType) ? options.scanType : ['barCode', 'qrCode']
  try {
    const res = await new Promise((resolve, reject) => {
      uni.scanCode({
        scanType,
        success: resolve,
        fail: reject,
      })
    })

    const normalizedType = normalizeScanType(res?.scanType)
    if (!isAllowedDeviceScanType(normalizedType)) {
      return {
        ok: false,
        error: ScanDeviceCodeError.UNSUPPORTED_SCAN_TYPE,
        scanType: normalizedType || 'UNKNOWN',
        result: res,
      }
    }

    const raw = String(res?.result || '').trim()
    if (!raw) {
      return {
        ok: false,
        error: ScanDeviceCodeError.EMPTY_RESULT,
        scanType: normalizedType || 'UNKNOWN',
        result: res,
      }
    }

    return {
      ok: true,
      raw,
      scanType: normalizedType || 'UNKNOWN',
      result: res,
    }
  } catch (e) {
    return {
      ok: false,
      error: ScanDeviceCodeError.SCAN_FAILED,
      scanType: 'UNKNOWN',
      cause: e,
    }
  }
}

