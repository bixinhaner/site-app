import { parseBarcode, isValidParseResult } from './barcode-parser.js'

export const ScanDeviceCodeError = {
  UNSUPPORTED_SCAN_TYPE: 'unsupported_scan_type',
  EMPTY_RESULT: 'empty_result',
  INVALID_BARCODE: 'invalid_barcode',
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
  'CODE_39',
  'CODE39',
  'CODE_93',
  'CODE93',
  'CODABAR',
  'ITF',
  'EAN_13',
  'EAN13',
  'EAN_8',
  'EAN8',
  'UPC_A',
  'UPCA',
  'UPC_E',
  'UPCE',
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

export function isScanCanceled(scanResult) {
  const msg = String(
    scanResult?.cause?.errMsg ||
      scanResult?.cause?.message ||
      scanResult?.errMsg ||
      scanResult?.message ||
      '',
  )
    .trim()
    .toLowerCase()
  return msg.includes('cancel')
}

export async function scanAndParseDeviceCode(options = {}) {
  const scanned = await scanDeviceCode(options)
  if (!scanned.ok) return scanned

  const parsed = parseBarcode(scanned.raw)
  if (!parsed?.success || !isValidParseResult(parsed)) {
    return {
      ok: false,
      error: ScanDeviceCodeError.INVALID_BARCODE,
      scanType: scanned.scanType || 'UNKNOWN',
      raw: scanned.raw,
      parsed,
      result: scanned.result,
    }
  }

  return {
    ok: true,
    raw: scanned.raw,
    scanType: scanned.scanType || 'UNKNOWN',
    parsed,
    sn: String(parsed.sn || '').trim(),
    result: scanned.result,
  }
}
