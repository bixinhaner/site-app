<template>
  <div class="user-detail">
    <el-card class="user-info-card">
      <template #header>
        <div class="card-header">
          <span>基本信息</span>
          <el-button type="primary" size="small" @click="editUser" v-if="canEdit">
            <el-icon><Edit /></el-icon>
            编辑
          </el-button>
        </div>
      </template>
      
      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户ID">
          {{ user.id }}
        </el-descriptions-item>
        
        <el-descriptions-item label="用户名">
          <span class="username-text">{{ user.username }}</span>
        </el-descriptions-item>
        
        <el-descriptions-item label="姓名">
          {{ user.full_name || '-' }}
        </el-descriptions-item>
        
        <el-descriptions-item label="邮箱">
          <el-link :href="`mailto:${user.email}`" type="primary">
            {{ user.email }}
          </el-link>
        </el-descriptions-item>
        
        <el-descriptions-item label="手机号">
          {{ user.phone || '-' }}
        </el-descriptions-item>
        
        <el-descriptions-item label="角色">
          <el-tag :type="getRoleTagType(user.role)">
            {{ getRoleLabel(user.role) }}
          </el-tag>
        </el-descriptions-item>
        
        <el-descriptions-item label="部门">
          {{ user.department || '-' }}
        </el-descriptions-item>
        
        <el-descriptions-item label="职位">
          {{ user.position || '-' }}
        </el-descriptions-item>
        
        <el-descriptions-item label="状态">
          <el-tag :type="user.is_active ? 'success' : 'danger'">
            {{ user.is_active ? '活跃' : '禁用' }}
          </el-tag>
        </el-descriptions-item>
        
        <el-descriptions-item label="创建时间">
          {{ formatDateTime(user.created_at) }}
        </el-descriptions-item>
        
        <el-descriptions-item label="更新时间" v-if="user.updated_at">
          {{ formatDateTime(user.updated_at) }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 操作按钮 -->
    <el-card class="actions-card" v-if="hasActions">
      <template #header>
        <span>操作</span>
      </template>
      
      <div class="action-buttons">
        <el-button type="success" @click="toggleUserStatus" v-if="canToggleStatus">
          <el-icon><Switch /></el-icon>
          {{ user.is_active ? '禁用用户' : '启用用户' }}
        </el-button>
        
        <el-button type="warning" @click="resetPassword" v-if="canResetPassword">
          <el-icon><Key /></el-icon>
          重置密码
        </el-button>
        
        <el-button type="danger" @click="deleteUser" v-if="canDelete">
          <el-icon><Delete /></el-icon>
          删除用户
        </el-button>
      </div>
    </el-card>

    <!-- 用户统计信息 -->
    <el-card class="stats-card" v-loading="statsLoading">
      <template #header>
        <span>统计信息</span>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="8">
          <div class="stat-item">
            <div class="stat-number">{{ userStats.loginCount || 0 }}</div>
            <div class="stat-label">登录次数</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="stat-item">
            <div class="stat-number">{{ userStats.lastLoginDays || '-' }}</div>
            <div class="stat-label">最后登录</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="stat-item">
            <div class="stat-number">{{ userStats.workOrderCount || 0 }}</div>
            <div class="stat-label">处理工单</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 编辑用户对话框 -->
    <el-dialog v-model="showEditDialog" title="编辑用户" width="600px">
      <user-form
        :user="user"
        @success="handleEditSuccess"
        @cancel="showEditDialog = false"
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Switch, Key, Delete } from '@element-plus/icons-vue'
import { userAPI } from '@/api/user'
import { useUserStore } from '@/stores/user'
import UserForm from './UserForm.vue'

// Props
const props = defineProps({
  user: {
    type: Object,
    required: true
  }
})

// Emits
const emit = defineEmits(['refresh'])

// 用户状态管理
const userStore = useUserStore()

// 响应式数据
const showEditDialog = ref(false)
const showPasswordDialog = ref(false)
const passwordLoading = ref(false)
const statsLoading = ref(false)
const passwordFormRef = ref()

// 用户统计数据
const userStats = reactive({
  loginCount: 0,
  lastLoginDays: '-',
  workOrderCount: 0
})

// 密码重置表单
const passwordForm = reactive({
  password: '',
  confirmPassword: ''
})

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

// 权限计算
const canEdit = computed(() => {
  const currentUser = userStore.currentUser
  return userStore.isAdmin || currentUser?.id === props.user.id
})

const canToggleStatus = computed(() => {
  return userStore.isAdmin && userStore.currentUser?.id !== props.user.id
})

const canResetPassword = computed(() => userStore.isAdmin)

const canDelete = computed(() => {
  return userStore.isAdmin && userStore.currentUser?.id !== props.user.id
})

const hasActions = computed(() => {
  return canToggleStatus.value || canResetPassword.value || canDelete.value
})

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

// 用户操作
const editUser = () => {
  showEditDialog.value = true
}

const toggleUserStatus = async () => {
  try {
    const action = props.user.is_active ? '禁用' : '启用'
    await ElMessageBox.confirm(
      `确定要${action}用户 "${props.user.username}" 吗？`,
      `确认${action}`,
      {
        confirmButtonText: action,
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await userAPI.updateUser(props.user.id, {
      is_active: !props.user.is_active
    })
    
    ElMessage.success(`${action}成功`)
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(`操作失败: ${error.message}`)
    }
  }
}

const resetPassword = () => {
  passwordForm.password = ''
  passwordForm.confirmPassword = ''
  showPasswordDialog.value = true
}

const deleteUser = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${props.user.username}" 吗？删除后用户将被禁用。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await userAPI.deleteUser(props.user.id)
    ElMessage.success('删除成功')
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + error.message)
    }
  }
}

// 密码重置处理
const handlePasswordReset = async () => {
  try {
    await passwordFormRef.value?.validate()
    passwordLoading.value = true
    
    await userAPI.resetPassword(props.user.id, passwordForm.password)
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

// 编辑成功处理
const handleEditSuccess = () => {
  showEditDialog.value = false
  emit('refresh')
}

// 加载用户统计数据（模拟数据）
const loadUserStats = async () => {
  statsLoading.value = true
  try {
    // 这里可以调用实际的统计API
    // const stats = await userAPI.getUserStats(props.user.id)
    
    // 模拟数据
    await new Promise(resolve => setTimeout(resolve, 500))
    userStats.loginCount = Math.floor(Math.random() * 100) + 1
    userStats.lastLoginDays = Math.floor(Math.random() * 30) + '天前'
    userStats.workOrderCount = Math.floor(Math.random() * 50)
  } catch (error) {
    console.error('加载统计数据失败:', error)
  } finally {
    statsLoading.value = false
  }
}

// 组件挂载
onMounted(() => {
  loadUserStats()
})
</script>

<style scoped>
.user-detail {
  padding: 20px;
}

.user-info-card,
.actions-card,
.stats-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.username-text {
  font-weight: 500;
  color: #f97316;
}

.action-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.stat-item {
  text-align: center;
  padding: 20px;
  background-color: #f8f9fa;
  border-radius: 8px;
}

.stat-number {
  font-size: 24px;
  font-weight: bold;
  color: #f97316;
  margin-bottom: 5px;
}

.stat-label {
  font-size: 14px;
  color: #666;
}
</style>
