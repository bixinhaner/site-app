import request from '@/utils/request'

const TRACK_ENDPOINT = '/api/operation-logs/track'

const toPlain = (value) => {
  try {
    return JSON.parse(JSON.stringify(value ?? null))
  } catch (e) {
    return String(value ?? '')
  }
}

export const buildRouteSnapshot = (to, from) => ({
  to: {
    path: to?.path,
    fullPath: to?.fullPath,
    name: to?.name,
    params: toPlain(to?.params),
    query: toPlain(to?.query),
  },
  from: {
    path: from?.path,
    fullPath: from?.fullPath,
    name: from?.name,
  },
})

export const trackOperation = async (payload) => {
  if (!payload || !payload.action) return
  try {
    await request.post(TRACK_ENDPOINT, payload)
  } catch (e) {
    // 埋点不影响业务流转：忽略上报失败
  }
}

export const createDebouncedTracker = (waitMs = 600) => {
  let timer = null
  let lastPayload = null

  return (payload) => {
    lastPayload = payload
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      trackOperation(lastPayload)
    }, waitMs)
  }
}

