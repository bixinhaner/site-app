import axios from 'axios'

const baseURL = import.meta.env.VITE_MOCK_OMC_BASE || 'http://127.0.0.1:9000'
const mockReq = axios.create({ baseURL, timeout: 8000 })

export const mockOmcApi = {
  list() {
    return mockReq.get('/admin/devices')
  },
  create(data) {
    return mockReq.post('/admin/devices', data)
  },
  update(sn, data) {
    return mockReq.put(`/admin/devices/${sn}`, data)
  },
  setState(sn, data) {
    return mockReq.post(`/admin/devices/${sn}/state`, data)
  },
  remove(sn) {
    return mockReq.delete(`/admin/devices/${sn}`)
  },
  reset() {
    return mockReq.post('/admin/reset')
  }
}
