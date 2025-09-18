import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '../api/auth'

export const useUserStore = defineStore('user', () => {
  const user = ref(JSON.parse(localStorage.getItem('user_info') || 'null'))
  const token = ref(localStorage.getItem('access_token'))

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isManager = computed(() => user.value?.role === 'manager')
  const isPlanner = computed(() => user.value?.role === 'planner')
  const isWarehouseManager = computed(() => 
    user.value?.role === 'admin' || user.value?.role === 'warehouse_manager'
  )
  const canManageEquipment = computed(() => 
    user.value?.role === 'admin' || user.value?.role === 'warehouse_manager'
  )
  const canManagePlanning = computed(() => ['admin', 'manager', 'planner'].includes(user.value?.role))

  // 登录
  async function login(credentials) {
    try {
      const response = await authApi.login(credentials.username, credentials.password)
      
      if (response.access_token) {
        token.value = response.access_token
        user.value = response.user
        localStorage.setItem('access_token', response.access_token)
        localStorage.setItem('user_info', JSON.stringify(response.user))
        return { success: true, user: response.user }
      }
    } catch (error) {
      console.error('登录失败:', error)
      return { success: false, error: error.message }
    }
  }

  // 获取用户信息
  async function fetchUserInfo() {
    try {
      const response = await authApi.getUserInfo()
      user.value = response
      localStorage.setItem('user_info', JSON.stringify(response))
      return response
    } catch (error) {
      console.error('获取用户信息失败:', error)
      logout()
      throw error
    }
  }

  // 登出
  function logout() {
    user.value = null
    token.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
  }

  // 初始化 - 如果有token尝试获取用户信息
  async function initialize() {
    if (token.value && !user.value) {
      await fetchUserInfo()
    }
  }

  return {
    user,
    token,
    isLoggedIn,
    isAdmin,
    isManager,
    isPlanner,
    isWarehouseManager,
    canManageEquipment,
    canManagePlanning,
    login,
    logout,
    fetchUserInfo,
    initialize
  }
})
