import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '../api/auth'
import { authzApi } from '../api/authz'

const normalizeCodeList = (value) => {
  if (!Array.isArray(value)) return []
  return [...new Set(value.map(v => String(v || '').trim()).filter(Boolean))]
}

const normalizeIdList = (value) => {
  if (!Array.isArray(value)) return []
  return [...new Set(value.map(v => Number(v)).filter(v => Number.isInteger(v) && v > 0))]
}

const normalizeDataScopes = (value) => {
  if (!value || typeof value !== 'object') return {}
  return Object.entries(value).reduce((out, [resource, scope]) => {
    const resourceCode = String(resource || '').trim()
    const scopeCode = String(scope || '').trim()
    if (!resourceCode || !scopeCode) return out
    out[resourceCode] = scopeCode
    return out
  }, {})
}

const normalizeWorkOrderExecution = (value) => {
  const src = value && typeof value === 'object' ? value : {}
  const normalizeLocalUploadPolicy = (raw, fallback = 'deny') => {
    const policy = String(raw || '').trim()
    if (policy === 'allow_with_watermark' || policy === 'allow_without_watermark' || policy === 'deny') {
      return policy
    }
    return fallback
  }
  const normalizeTypeList = (raw) => {
    if (!Array.isArray(raw)) return []
    return [...new Set(raw.map(item => String(item || '').trim()).filter(Boolean))]
  }
  const normalizeReasonList = (raw) => {
    if (!Array.isArray(raw)) return []
    return raw.map(item => String(item || '').trim()).filter(Boolean)
  }
  const localUploadPolicy = normalizeLocalUploadPolicy(
    src.local_upload_without_geo_policy,
    src.allow_local_upload_without_geo ? 'allow_with_watermark' : 'deny',
  )

  return {
    can_open_entry: Boolean(src.can_open_entry),
    is_user_active: src.is_user_active !== false,
    has_web_login_permission: Boolean(src.has_web_login_permission),
    has_execute_permission: Boolean(src.has_execute_permission),
    global_enabled: Boolean(src.global_enabled),
    allow_photo_upload: src.allow_photo_upload !== false,
    allow_device_binding: src.allow_device_binding !== false,
    allow_submit: src.allow_submit !== false,
    allow_recall: src.allow_recall !== false,
    local_upload_without_geo_policy: localUploadPolicy,
    allow_local_upload_without_geo: localUploadPolicy !== 'deny',
    visible_work_order_types: normalizeTypeList(src.visible_work_order_types),
    editable_work_order_types: normalizeTypeList(src.editable_work_order_types),
    has_any_visible_type: Boolean(src.has_any_visible_type),
    has_any_editable_type: Boolean(src.has_any_editable_type),
    reasons: normalizeReasonList(src.reasons),
  }
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
    data_scopes: normalizeDataScopes(src.data_scopes),
    inventory_scope: String(src.inventory_scope || '').trim() || 'self',
    managed_warehouse_ids: normalizeIdList(src.managed_warehouse_ids),
    managed_warehouse_count: Math.max(0, Number(src.managed_warehouse_count || 0) || 0),
    has_managed_warehouses: Boolean(src.has_managed_warehouses),
    work_order_execution: normalizeWorkOrderExecution(src.work_order_execution),
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
  const dataScopeMap = computed(() => normalizeDataScopes(user.value?.data_scopes))
  const inventoryScope = computed(() => String(user.value?.inventory_scope || 'self').trim() || 'self')
  const managedWarehouseIds = computed(() => normalizeIdList(user.value?.managed_warehouse_ids))
  const hasManagedWarehouses = computed(() => {
    if (inventoryScope.value === 'managed') return managedWarehouseIds.value.length > 0
    return Boolean(user.value?.has_managed_warehouses)
  })
  const hasGlobalInventoryAccess = computed(() => inventoryScope.value === 'all')
  const hasManagedInventoryAccess = computed(() => hasGlobalInventoryAccess.value || hasManagedWarehouses.value)
  const canViewInventoryHistory = computed(() => hasPermission('inventory:history:read') || hasManagedInventoryAccess.value)
  const workOrderExecution = computed(() => normalizeWorkOrderExecution(user.value?.work_order_execution))

  const hasRole = (roleCode) => roleCodes.value.includes(String(roleCode || '').trim())
  const hasAnyRole = (roleList = []) => roleList.some(role => hasRole(role))
  const hasPermission = (permissionCode) => {
    if (hasRole('admin')) return true
    return permissionMatches(permissionCode, permissionCodes.value)
  }
  const getDataScope = (resourceCode) => dataScopeMap.value[String(resourceCode || '').trim()] || null

  const isAdmin = computed(() => hasRole('admin'))
  const isManager = computed(() => hasRole('manager'))
  const isPlanner = computed(() => hasRole('planner'))
  const isWarehouseManager = computed(() => hasRole('warehouse_manager') || hasRole('admin'))
  const canManageEquipment = computed(() => hasPermission('inventory:equipment:write'))
  const canManagePlanning = computed(() => hasPermission('sites:lld:write'))
  const canAccessMyExecutionWorkOrders = computed(() => Boolean(workOrderExecution.value?.can_open_entry))

  const persistUser = (payload) => {
    user.value = normalizeUser(payload)
    localStorage.setItem('user_info', JSON.stringify(user.value))
  }

  async function refreshAuthzProfile() {
    if (!token.value) return user.value
    const response = await authzApi.getMyEffectivePermissions()
    const merged = {
      ...(user.value || {}),
      roles: response?.roles,
      permissions: response?.permissions,
      data_scopes: response?.data_scopes,
      inventory_scope: response?.inventory_scope,
      managed_warehouse_ids: response?.managed_warehouse_ids,
      managed_warehouse_count: response?.managed_warehouse_count,
      has_managed_warehouses: response?.has_managed_warehouses,
      work_order_execution: response?.work_order_execution,
    }
    persistUser(merged)
    return merged
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
        try {
          await refreshAuthzProfile()
        } catch (profileError) {
          console.error('刷新权限画像失败:', profileError)
        }
        return { success: true, user: user.value }
      }
    } catch (error) {
      console.error('登录失败:', error)
      const backendDetail = error.response?.data?.detail
      const errorCode = String(backendDetail || '').trim() || 'LOGIN_FAILED'
      return {
        success: false,
        errorCode,
        error: backendDetail || error.message || 'Login failed',
      }
    }
  }

  async function fetchUserInfo() {
    try {
      const response = await authApi.getUserInfo()
      persistUser(response)
      try {
        await refreshAuthzProfile()
      } catch (profileError) {
        console.error('刷新权限画像失败:', profileError)
      }
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
    dataScopeMap,
    inventoryScope,
    managedWarehouseIds,
    hasManagedWarehouses,
    hasGlobalInventoryAccess,
    hasManagedInventoryAccess,
    canViewInventoryHistory,
    workOrderExecution,
    isLoggedIn,
    isAdmin,
    isManager,
    isPlanner,
    isWarehouseManager,
    canManageEquipment,
    canManagePlanning,
    canAccessMyExecutionWorkOrders,
    hasRole,
    hasAnyRole,
    hasPermission,
    getDataScope,
    can: hasPermission,
    login,
    logout,
    fetchUserInfo,
    refreshAuthzProfile,
    initialize,
  }
})
