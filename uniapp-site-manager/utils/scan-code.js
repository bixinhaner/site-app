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

function toPositiveInt(value, fallback, min = 1, max = 20) {
  const num = Number(value)
  if (!Number.isFinite(num)) return fallback
  const intVal = Math.trunc(num)
  if (intVal < min) return min
  if (intVal > max) return max
  return intVal
}

function attachScanMeta(payload, meta) {
  return {
    ...payload,
    attempts: meta.attempts,
    failureCount: meta.failureCount,
    stableHitCount: meta.stableHitCount,
    requiredStableSnCount: meta.requiredStableSnCount,
    maxInvalidAttempts: meta.maxInvalidAttempts,
    failureSignature: meta.failureSignature || '',
  }
}

function buildFailureSignature(result) {
  const error = String(result?.error || '').trim()
  if (!error) return ''

  if (error === ScanDeviceCodeError.UNSUPPORTED_SCAN_TYPE) {
    return `unsupported:${normalizeScanType(result?.scanType) || 'UNKNOWN'}`
  }

  if (error === ScanDeviceCodeError.EMPTY_RESULT) {
    return 'empty_result'
  }

  if (error === ScanDeviceCodeError.INVALID_BARCODE) {
    const raw = String(result?.raw || '').trim().toUpperCase()
    const sn = String(result?.parsed?.sn || '').trim().toUpperCase()
    const format = String(result?.parsed?.format || '').trim().toUpperCase()
    const parseError = String(result?.parsed?.error || '').trim()
    return `invalid:${raw}|sn:${sn}|fmt:${format}|err:${parseError}`
  }

  if (error === ScanDeviceCodeError.SCAN_FAILED) {
    const msg = String(
      result?.cause?.errMsg ||
        result?.cause?.message ||
        result?.errMsg ||
        result?.message ||
        '',
    )
      .trim()
      .toLowerCase()
    return `scan_failed:${msg || 'unknown'}`
  }

  return `other:${error}`
}

export async function scanAndParseDeviceCode(options = {}) {
  const maxInvalidAttempts = toPositiveInt(options?.maxInvalidAttempts, 3, 1, 20)
  const requiredStableSnCount = toPositiveInt(options?.requiredStableSnCount, 1, 1, 5)
  const maxAttemptsRaw = Number(options?.maxAttempts)
  const hasMaxAttempts = Number.isFinite(maxAttemptsRaw) && maxAttemptsRaw > 0
  const maxAttempts = hasMaxAttempts ? toPositiveInt(maxAttemptsRaw, 20, 1, 200) : 0
  const scanOptions = {
    ...options,
  }
  delete scanOptions.maxInvalidAttempts
  delete scanOptions.requiredStableSnCount
  delete scanOptions.maxAttempts

  let attempts = 0
  let failureCount = 0 // 连续相同失败次数
  let stableHitCount = 0
  let previousSn = ''
  let lastFailureSignature = ''
  let lastFailure = null
  let lastParsedSuccess = null

  const shouldStopOnFailure = () => failureCount >= maxInvalidAttempts

  const registerFailure = (failureResult) => {
    const signature = buildFailureSignature(failureResult)
    if (signature && signature === lastFailureSignature) {
      failureCount += 1
    } else {
      lastFailureSignature = signature
      failureCount = 1
    }
    lastFailure = failureResult
    return signature
  }

  const resetFailureState = () => {
    failureCount = 0
    lastFailureSignature = ''
  }

  while (!hasMaxAttempts || attempts < maxAttempts) {
    attempts += 1
    const scanned = await scanDeviceCode(scanOptions)
    if (!scanned.ok) {
      if (scanned.error === ScanDeviceCodeError.SCAN_FAILED && isScanCanceled(scanned)) {
        return attachScanMeta(scanned, {
          attempts,
          failureCount,
          stableHitCount,
          requiredStableSnCount,
          maxInvalidAttempts,
          failureSignature: 'scan_failed:cancel',
        })
      }

      // scanCode 调用本身失败（权限/设备异常）直接上抛，避免无休止重试
      if (scanned.error === ScanDeviceCodeError.SCAN_FAILED) {
        const signature = buildFailureSignature(scanned)
        return attachScanMeta(scanned, {
          attempts,
          failureCount,
          stableHitCount,
          requiredStableSnCount,
          maxInvalidAttempts,
          failureSignature: signature,
        })
      }

      const signature = registerFailure(scanned)
      if (shouldStopOnFailure()) {
        return attachScanMeta(scanned, {
          attempts,
          failureCount,
          stableHitCount,
          requiredStableSnCount,
          maxInvalidAttempts,
          failureSignature: signature,
        })
      }

      continue
    }

    const parsed = parseBarcode(scanned.raw)
    if (!parsed?.success || !isValidParseResult(parsed)) {
      const invalidResult = {
        ok: false,
        error: ScanDeviceCodeError.INVALID_BARCODE,
        scanType: scanned.scanType || 'UNKNOWN',
        raw: scanned.raw,
        parsed,
        result: scanned.result,
      }
      const signature = registerFailure(invalidResult)
      if (shouldStopOnFailure()) {
        return attachScanMeta(invalidResult, {
          attempts,
          failureCount,
          stableHitCount,
          requiredStableSnCount,
          maxInvalidAttempts,
          failureSignature: signature,
        })
      }
      continue
    }

    const sn = String(parsed.sn || '').trim()
    if (!sn) {
      const invalidResult = {
        ok: false,
        error: ScanDeviceCodeError.INVALID_BARCODE,
        scanType: scanned.scanType || 'UNKNOWN',
        raw: scanned.raw,
        parsed,
        result: scanned.result,
      }
      const signature = registerFailure(invalidResult)
      if (shouldStopOnFailure()) {
        return attachScanMeta(invalidResult, {
          attempts,
          failureCount,
          stableHitCount,
          requiredStableSnCount,
          maxInvalidAttempts,
          failureSignature: signature,
        })
      }
      continue
    }

    resetFailureState()
    lastParsedSuccess = {
      ok: true,
      raw: scanned.raw,
      scanType: scanned.scanType || 'UNKNOWN',
      parsed,
      sn,
      result: scanned.result,
    }

    if (requiredStableSnCount <= 1) {
      return attachScanMeta(lastParsedSuccess, {
        attempts,
        failureCount,
        stableHitCount: 1,
        requiredStableSnCount,
        maxInvalidAttempts,
        failureSignature: '',
      })
    }

    if (sn === previousSn) {
      stableHitCount += 1
    } else {
      previousSn = sn
      stableHitCount = 1
    }

    if (stableHitCount >= requiredStableSnCount) {
      return attachScanMeta(lastParsedSuccess, {
        attempts,
        failureCount,
        stableHitCount,
        requiredStableSnCount,
        maxInvalidAttempts,
        failureSignature: '',
      })
    }
  }

  if (lastFailure) {
    return attachScanMeta(lastFailure, {
      attempts,
      failureCount,
      stableHitCount,
      requiredStableSnCount,
      maxInvalidAttempts,
      failureSignature: lastFailureSignature,
    })
  }

  if (lastParsedSuccess) {
    return attachScanMeta(lastParsedSuccess, {
      attempts,
      failureCount,
      stableHitCount,
      requiredStableSnCount,
      maxInvalidAttempts,
      failureSignature: '',
    })
  }

  return {
    ok: false,
    error: ScanDeviceCodeError.SCAN_FAILED,
    scanType: 'UNKNOWN',
    attempts,
    failureCount,
    stableHitCount,
    requiredStableSnCount,
    maxInvalidAttempts,
  }
}
