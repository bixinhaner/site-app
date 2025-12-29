/**
 * AI 能力 API（独立可复用）
 */

import request from '@/utils/request'
import config from '@/config/env.js'

const API_BASE = '/api/ai'

export const aiAPI = {
  async translate(payload) {
    return request.post(`${API_BASE}/translate`, payload, { timeout: config.LONG_REQUEST_TIMEOUT })
  },
  async translateBatch(payload) {
    return request.post(`${API_BASE}/translate/batch`, payload, { timeout: config.LONG_REQUEST_TIMEOUT })
  },
}
