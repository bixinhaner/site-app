import request from '@/utils/request'

export const authzApi = {
  listPermissions: () => request.get('/api/authz/permissions'),
  listPermissionModules: () => request.get('/api/authz/permissions/modules'),
  listDataScopeDefinitions: () => request.get('/api/authz/data-scopes/definitions'),
  listRoles: () => request.get('/api/authz/roles'),
  createRole: (payload) => request.post('/api/authz/roles', payload),
  updateRole: (roleId, payload) => request.put(`/api/authz/roles/${roleId}`, payload),
  deleteRole: (roleId) => request.delete(`/api/authz/roles/${roleId}`),
  setRolePermissions: (roleId, permissions) =>
    request.put(`/api/authz/roles/${roleId}/permissions`, { permissions }),
  setRoleDataScopes: (roleId, data_scopes) =>
    request.put(`/api/authz/roles/${roleId}/data-scopes`, { data_scopes }),
  getUserRoles: (userId) => request.get(`/api/authz/users/${userId}/roles`),
  setUserRoles: (userId, roles) => request.put(`/api/authz/users/${userId}/roles`, { roles }),
  getUserEffectivePermissions: (userId) => request.get(`/api/authz/users/${userId}/effective-permissions`),
  getMyEffectivePermissions: () => request.get('/api/authz/me/effective-permissions'),
}

export default authzApi
