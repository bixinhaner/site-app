import request from '@/utils/request'

// 用户API
export const userAPI = {
  // 搜索用户（带分页和筛选）
  searchUsers: (params = {}) => {
    const searchParams = new URLSearchParams()
    
    Object.keys(params).forEach(key => {
      if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
        searchParams.append(key, params[key])
      }
    })
    
    return request.get(`/api/users/search?${searchParams.toString()}`)
  },

  // 获取用户列表
  getUsers: (skip = 0, limit = 100) => {
    return request.get(`/api/users/?skip=${skip}&limit=${limit}`)
  },

  // 创建用户
  createUser: (userData) => {
    return request.post('/api/users/', userData)
  },

  // 获取用户详情
  getUser: (userId) => {
    return request.get(`/api/users/${userId}`)
  },

  // 更新用户信息
  updateUser: (userId, userData) => {
    return request.put(`/api/users/${userId}`, userData)
  },

  // 删除用户（软删除）
  deleteUser: (userId) => {
    return request.delete(`/api/users/${userId}`)
  },

  // 重置用户密码
  resetPassword: (userId, newPassword) => {
    return request.post('/api/users/reset-password', {
      user_id: userId,
      new_password: newPassword
    })
  },

  // 批量操作用户
  batchOperation: (userIds, operation, value = null) => {
    return request.post('/api/users/batch-operation', {
      user_ids: userIds,
      operation: operation,
      value: value
    })
  },

  // 获取用户统计信息
  getUserStats: () => {
    return request.get('/api/users/stats/summary')
  }
}

export default userAPI