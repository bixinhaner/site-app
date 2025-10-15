import request from '@/utils/request'

export const authApi = {
  // 用户登录
  login: async (username, password) => {
    return await request.post('/api/auth/login', {
      username,
      password
    })
  },
  
  // 获取用户信息
  getUserInfo: () => request.get('/api/auth/me'),
  
  // 刷新token
  refreshToken: () => request.post('/api/auth/refresh')
}