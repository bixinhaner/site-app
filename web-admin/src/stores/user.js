import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '../api/auth'

const normalizeCodeList = (value) => {
  if (!Array.isArray(value)) return []
  return [...new Set(value.map(v => String(v || '').trim()).filter(Boolean))]
}

const permissionMatches = (target, grantedCodes) => {
  const code = String(target || '').trim()
  if (!code) return false
  const list = normalizeCodeList(grantedCodes)
  for (const item of list) {
    if (item === '*' || item === code) return true
    if (item.endsWith(':*') && code.startsWith(item.slice(0, -1))) return true
  }
  return false
}

const normalizeUser = (raw) => {
  if (!raw || typeof raw !== 'object') return null
  const src = raw || {}
  const roles = normalizeCodeList(src.roles)
  const role = String(src.role || '').trim() || roles[0] || null
  const normalizedRoles = roles.length > 0 ? roles : (role ? [role] : [])
  return {
    ...src,
    role,
    roles: normalizedRoles,
    permissions: normalizeCodeList(src.permissions),
  }
}

export const useUserStore = defineStore('user', () => {
  const user = ref(normalizeUser(JSON.parse(localStorage.getItem('user_info') || 'null')))
  const token = ref(localStorage.getItem('access_token'))
  const refreshToken = ref(localStorage.getItem('refresh_token'))
  const refreshing = ref(false)

  const isLoggedIn = computed(() => !!token.value && !!user.value?.id)
  const roleCodes = computed(() => normalizeCodeList(user.value?.roles || (user.value?.role ? [user.value.role] : [])))
  const permissionCodes = computed(() => normalizeCodeList(user.value?.permissions))

  const hasRole = (roleCode) => roleCodes.value.includes(String(roleCode || '').trim())
  const hasAnyRole = (roleList = []) => roleList.some(role => hasRole(role))
  const hasPermission = (permissionCode) => {
    if (hasRole('admin')) return true
    return permissionMatches(permissionCode, permissionCodes.value)
  }

  const isAdmin = computed(() => hasRole('admin'))
  const isManager = computed(() => hasRole('manager'))
  const isPlanner = computed(() => hasRole('planner'))
  const isWarehouseManager = computed(() => hasRole('warehouse_manager') || hasRole('admin'))
  const canManageEquipment = computed(() => hasPermission('inventory:equipment:write'))
  const canManagePlanning = computed(() => hasPermission('sites:lld:write'))

  const persistUser = (payload) => {
    user.value = normalizeUser(payload)
    localStorage.setItem('user_info', JSON.stringify(user.value))
  }

  async function login(credentials) {
    try {
      const response = await authApi.login(credentials.username, credentials.password)

      if (response.access_token) {
        token.value = response.access_token
        refreshToken.value = response.refresh_token
        persistUser(response.user)
        localStorage.setItem('access_token', response.access_token)
        if (response.refresh_token) localStorage.setItem('refresh_token', response.refresh_token)
        return { success: true, user: user.value }
      }
    } catch (error) {
      console.error('登录失败:', error)
      const backendDetail = error.response?.data?.detail
      const message = backendDetail || error.message || 'Login failed'
      return { success: false, error: message }
    }
  }

  async function fetchUserInfo() {
    try {
      const response = await authApi.getUserInfo()
      persistUser(response)
      return response
    } catch (error) {
      console.error('获取用户信息失败:', error)
      logout()
      throw error
    }
  }

  function logout() {
    user.value = null
    token.value = null
    refreshToken.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_info')
  }

  async function initialize() {
    if (token.value && !user.value?.id) {
      await fetchUserInfo()
    }
  }

  return {
    user,
    token,
    refreshToken,
    refreshing,
    currentUser: user,
    roleCodes,
    permissionCodes,
    isLoggedIn,
    isAdmin,
    isManager,
    isPlanner,
    isWarehouseManager,
    canManageEquipment,
    canManagePlanning,
    hasRole,
    hasAnyRole,
    hasPermission,
    can: hasPermission,
    login,
    logout,
    fetchUserInfo,
    initialize,
  }
})
