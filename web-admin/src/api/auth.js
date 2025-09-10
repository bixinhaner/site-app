import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000'

// 创建axios实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 添加token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器 - 处理401错误
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.reload()
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  // 用户登录
  login: async (username, password) => {
    return await apiClient.post('/api/auth/login', {
      username,
      password
    })
  },
  
  // 获取用户信息
  getUserInfo: () => apiClient.get('/api/auth/me')
}

export default apiClient