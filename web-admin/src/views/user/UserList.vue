<template>
  <div class="user-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1>用户管理</h1>
      <div class="header-actions">
        <el-button type="primary" @click="showCreateDialog = true" v-if="canCreate">
          <el-icon><Plus /></el-icon>
          新增用户
        </el-button>
        <el-button @click="loadUserList" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 搜索和筛选 -->
    <el-card class="search-card">
      <div class="search-row">
        <div class="search-left">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索用户名、姓名或邮箱"
            style="width: 300px"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          
          <el-select
            v-model="filterRole"
            placeholder="角色"
            style="width: 150px"
            clearable
            @change="handleSearch"
          >
            <el-option label="管理员" value="admin" />
            <el-option label="项目经理" value="manager" />
            <el-option label="现场工程师" value="inspector" />
            <el-option label="勘察人员" value="surveyor" />
            <el-option label="普通用户" value="user" />
          </el-select>
          
          <el-select
            v-model="filterStatus"
            placeholder="状态"
            style="width: 120px"
            clearable
            @change="handleSearch"
          >
            <el-option label="活跃" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>

          <el-input
            v-model="filterDepartment"
            placeholder="部门"
            style="width: 150px"
            clearable
            @keyup.enter="handleSearch"
          />
        </div>
        
        <div class="search-right">
          <el-button type="primary" @click="handleSearch" :loading="loading">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetSearch">
            <el-icon><RefreshRight /></el-icon>
            重置
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 批量操作工具栏 -->
    <el-card class="batch-toolbar" v-if="selectedUsers.length > 0">
      <div class="batch-actions">
        <span class="batch-info">已选择 {{ selectedUsers.length }} 个用户</span>
        <el-button-group>
          <el-button type="success" size="small" @click="batchActivate" v-if="canBatchOperate">
            <el-icon><Check /></el-icon>
            批量启用
          </el-button>
          <el-button type="warning" size="small" @click="batchDeactivate" v-if="canBatchOperate">
            <el-icon><Close /></el-icon>
            批量禁用
          </el-button>
        </el-button-group>
      </div>
    </el-card>

    <!-- 用户列表 -->
    <el-card class="table-card">
      <el-table
        :data="userList"
        v-loading="loading"
        @selection-change="handleSelectionChange"
        stripe
        style="width: 100%"
      >
        <el-table-column type="selection" width="55" v-if="canBatchOperate" />
        
        <el-table-column prop="id" label="ID" width="80" />
        
        <el-table-column prop="username" label="用户名" width="120">
          <template #default="{ row }">
            <span class="username-text">{{ row.username }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="full_name" label="姓名" width="120">
          <template #default="{ row }">
            <span>{{ row.full_name || '-' }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="email" label="邮箱" width="200" />
        
        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="getRoleTagType(row.role)">{{ getRoleLabel(row.role) }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="department" label="部门" width="120">
          <template #default="{ row }">
            <span>{{ row.department || '-' }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="position" label="职位" width="120">
          <template #default="{ row }">
            <span>{{ row.position || '-' }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '活跃' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span>{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button type="primary" size="small" @click="viewUser(row)" link>
                <el-icon><View /></el-icon>
                查看
              </el-button>
              <el-button type="warning" size="small" @click="editUser(row)" link v-if="canEdit(row)">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button type="info" size="small" @click="resetPassword(row)" link v-if="canResetPassword">
                <el-icon><Key /></el-icon>
                重置密码
              </el-button>
              <el-button
                type="danger"
                size="small"
                @click="toggleUserStatus(row)"
                link
                v-if="canToggleStatus(row)"
              >
                <el-icon><Switch /></el-icon>
                {{ row.is_active ? '禁用用户' : '启用用户' }}
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 用户详情抽屉 -->
    <el-drawer v-model="showDetailDrawer" title="用户详情" size="600px">
      <user-detail
        v-if="selectedUser"
        :user="selectedUser"
        @refresh="loadUserList"
      />
    </el-drawer>

    <!-- 新增/编辑用户对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingUser ? '编辑用户' : '新增用户'"
      width="600px"
      @close="resetForm"
    >
      <user-form
        :user="editingUser"
        @success="handleFormSuccess"
        @cancel="showCreateDialog = false"
      />
    </el-dialog>

    <!-- 密码重置对话框 -->
    <el-dialog v-model="showPasswordDialog" title="重置密码" width="400px">
      <el-form :model="passwordForm" :rules="passwordRules" ref="passwordFormRef">
        <el-form-item label="新密码" prop="password">
          <el-input
            v-model="passwordForm.password"
            type="password"
            placeholder="请输入新密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="passwordForm.confirmPassword"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" @click="handlePasswordReset" :loading="passwordLoading">
          确认重置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Refresh, Search, RefreshRight, View, Edit, Key, Switch,
  Check, Close
} from '@element-plus/icons-vue'
import { userAPI } from '@/api/user'
import { useUserStore } from '@/stores/user'
import { trackOperation } from '@/utils/operationTrack'
import UserDetail from './components/UserDetail.vue'
import UserForm from './components/UserForm.vue'

// 用户状态管理
const userStore = useUserStore()

// 响应式数据
const loading = ref(false)
const userList = ref([])
const selectedUsers = ref([])

// 搜索筛选
const searchKeyword = ref('')
const filterRole = ref('')
const filterStatus = ref(null)
const filterDepartment = ref('')

// 分页
const pagination = reactive({
  page: 1,
  size: 20,
  total: 0,
  pages: 0
})

// 对话框和抽屉
const showDetailDrawer = ref(false)
const showCreateDialog = ref(false)
const showPasswordDialog = ref(false)
const selectedUser = ref(null)
const editingUser = ref(null)

// 密码重置表单
const passwordForm = reactive({
  password: '',
  confirmPassword: ''
})
const passwordLoading = ref(false)
const passwordFormRef = ref()
const resetUserId = ref(null)

// 密码验证规则
const passwordRules = {
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 权限计算（将 manager 视为 admin 等同）
const canCreate = computed(() => userStore.isAdmin)
const canBatchOperate = computed(() => userStore.isAdmin)
const canResetPassword = computed(() => userStore.isAdmin)

const canEdit = (user) => {
  const currentUser = userStore.currentUser
  return userStore.isAdmin || currentUser?.id === user.id
}

const canToggleStatus = (user) => {
  return userStore.isAdmin && userStore.currentUser?.id !== user.id
}

// 角色相关
const getRoleLabel = (role) => {
  const roleMap = {
    admin: '管理员',
    manager: '项目经理', 
    inspector: '现场工程师',
    user: '普通用户'
  }
  return roleMap[role] || role
}

const getRoleTagType = (role) => {
  const typeMap = {
    admin: 'danger',
    manager: 'warning',
    inspector: 'primary',
    user: 'info'
  }
  return typeMap[role] || 'info'
}

// 时间格式化
const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

// 加载用户列表
const loadUserList = async () => {
  loading.value = true
  try {
    const params = {
      keyword: searchKeyword.value || null,
      role: filterRole.value || null,
      department: filterDepartment.value || null,
      is_active: filterStatus.value,
      skip: (pagination.page - 1) * pagination.size,
      limit: pagination.size
    }
    
    const response = await userAPI.searchUsers(params)
    userList.value = response.users
    pagination.total = response.total
    pagination.pages = response.pages
  } catch (error) {
    ElMessage.error('加载用户列表失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 搜索处理
const handleSearch = () => {
  pagination.page = 1
  trackOperation({
    module: '用户管理',
    action: '查询',
    object_type: '用户',
    data: {
      keyword: searchKeyword.value || undefined,
      role: filterRole.value || undefined,
      department: filterDepartment.value || undefined,
      is_active: filterStatus.value === null ? undefined : filterStatus.value,
    },
  })
  loadUserList()
}

const resetSearch = () => {
  searchKeyword.value = ''
  filterRole.value = ''
  filterStatus.value = null
  filterDepartment.value = ''
  pagination.page = 1
  trackOperation({
    module: '用户管理',
    action: '重置筛选',
    object_type: '用户',
  })
  loadUserList()
}

// 分页处理
const handleSizeChange = (size) => {
  pagination.size = size
  pagination.page = 1
  loadUserList()
}

const handleCurrentChange = (page) => {
  pagination.page = page
  loadUserList()
}

// 选择处理
const handleSelectionChange = (selection) => {
  selectedUsers.value = selection
}

// 用户操作
const viewUser = (user) => {
  selectedUser.value = user
  showDetailDrawer.value = true
}

const editUser = (user) => {
  editingUser.value = { ...user }
  showCreateDialog.value = true
}

const toggleUserStatus = async (user) => {
  try {
    const action = user.is_active ? '禁用' : '启用'
    await ElMessageBox.confirm(
      `确定要${action}用户 "${user.username}" 吗？`,
      `确认${action}`,
      {
        confirmButtonText: action,
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await userAPI.updateUser(user.id, {
      is_active: !user.is_active
    })
    ElMessage.success(`${action}成功`)
    loadUserList()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(`操作失败: ${error.message}`)
    }
  }
}

const resetPassword = (user) => {
  resetUserId.value = user.id
  passwordForm.password = ''
  passwordForm.confirmPassword = ''
  showPasswordDialog.value = true
}

// 密码重置处理
const handlePasswordReset = async () => {
  try {
    await passwordFormRef.value?.validate()
    passwordLoading.value = true
    
    await userAPI.resetPassword(resetUserId.value, passwordForm.password)
    ElMessage.success('密码重置成功')
    showPasswordDialog.value = false
  } catch (error) {
    if (error.message) {
      ElMessage.error('密码重置失败: ' + error.message)
    }
  } finally {
    passwordLoading.value = false
  }
}

// 批量操作
const batchActivate = async () => {
  try {
    const userIds = selectedUsers.value.map(user => user.id)
    await userAPI.batchOperation(userIds, 'activate')
    ElMessage.success(`成功启用 ${userIds.length} 个用户`)
    selectedUsers.value = []
    loadUserList()
  } catch (error) {
    ElMessage.error('批量启用失败: ' + error.message)
  }
}

const batchDeactivate = async () => {
  try {
    const userIds = selectedUsers.value.map(user => user.id)
    await userAPI.batchOperation(userIds, 'deactivate')
    ElMessage.success(`成功禁用 ${userIds.length} 个用户`)
    selectedUsers.value = []
    loadUserList()
  } catch (error) {
    ElMessage.error('批量禁用失败: ' + error.message)
  }
}

// 表单处理
const handleFormSuccess = () => {
  showCreateDialog.value = false
  loadUserList()
}

const resetForm = () => {
  editingUser.value = null
}

// 页面初始化
onMounted(() => {
  loadUserList()
})
</script>

<style scoped>
.user-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.search-card {
  margin-bottom: 20px;
}

.search-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
}

.search-left {
  display: flex;
  gap: 15px;
  flex: 1;
}

.search-right {
  display: flex;
  gap: 10px;
}

.batch-toolbar {
  margin-bottom: 20px;
  background-color: #f8f9fa;
}

.batch-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.batch-info {
  color: #f97316;
  font-weight: 500;
}

.table-card {
  margin-bottom: 20px;
}

.username-text {
  font-weight: 500;
  color: #f97316;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
</style>
