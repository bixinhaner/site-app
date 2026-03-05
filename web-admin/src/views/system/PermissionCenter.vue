<template>
  <div class="permission-page">
    <div class="page-header">
      <h1>角色权限</h1>
      <div class="actions">
        <el-button @click="loadAll" :loading="loading">刷新</el-button>
        <el-button type="primary" @click="openCreateRole">新建角色</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="9">
        <el-card class="panel" v-loading="loading">
          <template #header>
            <div class="panel-title">角色列表</div>
          </template>
          <el-table
            :data="roles"
            highlight-current-row
            @current-change="handleRoleSelect"
            row-key="id"
            :current-row-key="selectedRoleId"
            height="640"
          >
            <el-table-column prop="name" label="角色" min-width="150">
              <template #default="{ row }">
                <div class="role-name">{{ row.name }}</div>
                <div class="role-code">{{ row.code }}</div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click.stop="openEditRole(row)">编辑</el-button>
                <el-button link type="danger" :disabled="row.is_system" @click.stop="deleteRole(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="15">
        <el-card class="panel" v-loading="loadingPermissions">
          <template #header>
            <div class="panel-title">
              <span>权限配置</span>
              <span v-if="selectedRole" class="role-hint">{{ selectedRole.name }} ({{ selectedRole.code }})</span>
            </div>
          </template>

          <el-empty v-if="!selectedRole" description="请选择左侧角色" />

          <div v-else>
            <el-alert
              v-if="selectedRole.is_system"
              type="info"
              :closable="false"
              title="系统角色可以调整权限，但不支持删除"
              class="mb12"
            />

            <el-checkbox-group v-model="checkedPermissions" class="permission-group">
              <el-card
                v-for="moduleName in sortedModules"
                :key="moduleName"
                class="module-card"
                shadow="never"
              >
                <template #header>
                  <div class="module-title">{{ moduleName }}</div>
                </template>
                <div class="module-perms">
                  <el-checkbox
                    v-for="perm in permissionModules[moduleName] || []"
                    :key="perm.code"
                    :label="perm.code"
                  >
                    {{ perm.name }}
                    <span class="perm-code">({{ perm.code }})</span>
                  </el-checkbox>
                </div>
              </el-card>
            </el-checkbox-group>

            <div class="footer-actions">
              <el-button type="primary" @click="saveRolePermissions" :loading="savingPermissions">保存权限</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="createDialogVisible" title="新建角色" width="560px" @closed="resetCreateForm">
      <el-form ref="createFormRef" :model="createForm" :rules="formRules" label-width="100px">
        <el-form-item label="角色编码" prop="code">
          <el-input v-model="createForm.code" placeholder="例如: contractor" />
        </el-form-item>
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="createForm.name" placeholder="例如: 施工队" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreateRole" :loading="submittingRole">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑角色" width="560px" @closed="resetEditForm">
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="100px">
        <el-form-item label="角色编码">
          <el-input v-model="editForm.code" disabled />
        </el-form-item>
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEditRole" :loading="submittingRole">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { authzApi } from '@/api/authz'

const loading = ref(false)
const loadingPermissions = ref(false)
const savingPermissions = ref(false)
const submittingRole = ref(false)

const roles = ref([])
const permissionModules = ref({})
const selectedRoleId = ref(null)
const checkedPermissions = ref([])

const createDialogVisible = ref(false)
const editDialogVisible = ref(false)
const createFormRef = ref()
const editFormRef = ref()

const createForm = reactive({
  code: '',
  name: '',
  description: '',
})

const editForm = reactive({
  id: null,
  code: '',
  name: '',
  description: '',
  is_active: true,
})

const formRules = {
  code: [
    { required: true, message: '请输入角色编码', trigger: 'blur' },
    { min: 2, max: 64, message: '长度 2-64', trigger: 'blur' },
  ],
  name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' },
    { min: 1, max: 100, message: '长度 1-100', trigger: 'blur' },
  ],
}

const editRules = {
  name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' },
    { min: 1, max: 100, message: '长度 1-100', trigger: 'blur' },
  ],
}

const selectedRole = computed(() => roles.value.find((r) => r.id === selectedRoleId.value) || null)
const sortedModules = computed(() => Object.keys(permissionModules.value || {}).sort((a, b) => a.localeCompare(b, 'zh-CN')))

const applySelectedRolePermissions = () => {
  const perms = selectedRole.value?.permissions || []
  checkedPermissions.value = [...new Set(perms.map((x) => String(x || '').trim()).filter(Boolean))]
}

const loadRoles = async () => {
  const rows = await authzApi.listRoles()
  roles.value = Array.isArray(rows) ? rows : []
  if (!selectedRoleId.value && roles.value.length > 0) {
    selectedRoleId.value = roles.value[0].id
  }
  if (selectedRoleId.value && !roles.value.some((r) => r.id === selectedRoleId.value)) {
    selectedRoleId.value = roles.value[0]?.id || null
  }
  applySelectedRolePermissions()
}

const loadPermissionModules = async () => {
  loadingPermissions.value = true
  try {
    const modules = await authzApi.listPermissionModules()
    permissionModules.value = modules || {}
  } finally {
    loadingPermissions.value = false
  }
}

const loadAll = async () => {
  loading.value = true
  try {
    await Promise.all([loadRoles(), loadPermissionModules()])
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载权限配置失败')
  } finally {
    loading.value = false
  }
}

const handleRoleSelect = (row) => {
  selectedRoleId.value = row?.id || null
  applySelectedRolePermissions()
}

const saveRolePermissions = async () => {
  if (!selectedRole.value) return
  try {
    savingPermissions.value = true
    await authzApi.setRolePermissions(selectedRole.value.id, checkedPermissions.value)
    ElMessage.success('权限保存成功')
    await loadRoles()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '保存权限失败')
  } finally {
    savingPermissions.value = false
  }
}

const openCreateRole = () => {
  createDialogVisible.value = true
}

const resetCreateForm = () => {
  createForm.code = ''
  createForm.name = ''
  createForm.description = ''
  createFormRef.value?.clearValidate()
}

const submitCreateRole = async () => {
  try {
    await createFormRef.value?.validate()
    submittingRole.value = true
    await authzApi.createRole({
      code: String(createForm.code || '').trim(),
      name: String(createForm.name || '').trim(),
      description: String(createForm.description || '').trim() || null,
      permissions: [],
    })
    ElMessage.success('角色创建成功')
    createDialogVisible.value = false
    await loadRoles()
  } catch (error) {
    if (error?.message) {
      ElMessage.error(error?.response?.data?.detail || error.message)
    }
  } finally {
    submittingRole.value = false
  }
}

const openEditRole = (row) => {
  editForm.id = row.id
  editForm.code = row.code
  editForm.name = row.name
  editForm.description = row.description || ''
  editForm.is_active = row.is_active !== false
  editDialogVisible.value = true
}

const resetEditForm = () => {
  editForm.id = null
  editForm.code = ''
  editForm.name = ''
  editForm.description = ''
  editForm.is_active = true
  editFormRef.value?.clearValidate()
}

const submitEditRole = async () => {
  if (!editForm.id) return
  try {
    await editFormRef.value?.validate()
    submittingRole.value = true
    await authzApi.updateRole(editForm.id, {
      name: String(editForm.name || '').trim(),
      description: String(editForm.description || '').trim() || null,
      is_active: !!editForm.is_active,
    })
    ElMessage.success('角色更新成功')
    editDialogVisible.value = false
    await loadRoles()
  } catch (error) {
    if (error?.message) {
      ElMessage.error(error?.response?.data?.detail || error.message)
    }
  } finally {
    submittingRole.value = false
  }
}

const deleteRole = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除角色 ${row.name} (${row.code}) 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await authzApi.deleteRole(row.id)
    ElMessage.success('角色删除成功')
    await loadRoles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.response?.data?.detail || '删除角色失败')
    }
  }
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.permission-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h1 {
  margin: 0;
  font-size: 22px;
}

.actions {
  display: flex;
  gap: 8px;
}

.panel {
  min-height: 720px;
}

.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-weight: 600;
}

.role-name {
  font-weight: 500;
}

.role-code {
  color: #909399;
  font-size: 12px;
}

.role-hint {
  font-size: 12px;
  color: #606266;
}

.permission-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.module-card {
  border-color: #ebeef5;
}

.module-title {
  font-weight: 600;
}

.module-perms {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 16px;
}

.perm-code {
  color: #909399;
  margin-left: 4px;
}

.footer-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.mb12 {
  margin-bottom: 12px;
}
</style>
