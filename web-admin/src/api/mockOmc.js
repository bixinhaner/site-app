import request from '@/utils/request'

const baseURL = import.meta.env.VITE_MOCK_OMC_BASE || '/api/mock-omc'

const joinURL = (base, path) => {
  const b = String(base || '').replace(/\/+$/, '')
  const p = String(path || '').replace(/^\/+/, '')
  return `${b}/${p}`
}

export const mockOmcApi = {
  list() {
    return request.get(joinURL(baseURL, '/admin/devices'))
  },
  create(data) {
    return request.post(joinURL(baseURL, '/admin/devices'), data)
  },
  update(sn, data) {
    return request.put(joinURL(baseURL, `/admin/devices/${sn}`), data)
  },
  setState(sn, data) {
    return request.post(joinURL(baseURL, `/admin/devices/${sn}/state`), data)
  },
  remove(sn) {
    return request.delete(joinURL(baseURL, `/admin/devices/${sn}`))
  },
  reset() {
    return request.post(joinURL(baseURL, '/admin/reset'))
  }
}
