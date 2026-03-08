<template>
  <div class="user-form">
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
      v-loading="loading"
    >
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              :disabled="isEditing"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="邮箱" prop="email">
            <el-input
              v-model="form.email"
              placeholder="请输入邮箱地址"
              type="email"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20" v-if="!isEditing">
        <el-col :span="12">
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              placeholder="请输入密码"
              type="password"
              show-password
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              placeholder="请再次输入密码"
              type="password"
              show-password
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="姓名" prop="full_name">
            <el-input
              v-model="form.full_name"
              placeholder="请输入真实姓名"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="手机号" prop="phone">
            <el-input
              v-model="form.phone"
              placeholder="请输入国际电话号码（E.164，例如 +14155550132）"
              maxlength="20"
              show-word-limit
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="角色" prop="roles">
            <el-select
              v-model="form.roles"
              placeholder="请选择角色（可多选）"
              style="width: 100%"
              :disabled="!canChangeRole"
              multiple
              collapse-tags
              collapse-tags-tooltip
            >
              <el-option
                v-for="role in roleOptions"
                :key="role.code"
                :label="`${role.name} (${role.code})`"
                :value="role.code"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="部门" prop="department">
            <el-input
              v-model="form.department"
              placeholder="请输入所属部门"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20" v-if="showExecutionPreview">
        <el-col :span="24">
          <el-card class="execution-preview-card" shadow="never" v-loading="executionPreviewLoading">
            <template #header>
              <div class="execution-preview-header">
                <span>Web工单执行生效预览</span>
                <el-button link @click="loadExecutionPreview">刷新</el-button>
              </div>
            </template>

            <el-alert
              v-if="executionPreviewDirty"
              class="execution-preview-alert"
              type="warning"
              :closable="false"
              show-icon
              title="你已经修改了角色，但下面的结果仍按当前已保存角色计算；保存后再刷新就会更新。"
            />

            <div class="execution-preview-grid">
              <div class="execution-preview-item">
                <div class="preview-label">执行入口</div>
                <el-tag :key="`execution-entry-${executionPreview.can_open_entry}`" :type="executionPreview.can_open_entry ? 'success' : 'info'">
                  {{ executionPreview.can_open_entry ? '可进入' : '不可进入' }}
                </el-tag>
              </div>
              <div class="execution-preview-item">
                <div class="preview-label">Web 登录</div>
                <el-tag :key="`execution-web-login-${executionPreview.has_web_login_permission}`" :type="executionPreview.has_web_login_permission ? 'success' : 'warning'">
                  {{ executionPreview.has_web_login_permission ? '已具备' : '未授予' }}
                </el-tag>
              </div>
              <div class="execution-preview-item">
                <div class="preview-label">执行权限</div>
                <el-tag :key="`execution-permission-${executionPreview.has_execute_permission}`" :type="executionPreview.has_execute_permission ? 'success' : 'warning'">
                  {{ executionPreview.has_execute_permission ? '已具备' : '未授予' }}
                </el-tag>
              </div>
              <div class="execution-preview-item">
                <div class="preview-label">总开关</div>
                <el-tag :key="`execution-global-${executionPreview.global_enabled}`" :type="executionPreview.global_enabled ? 'success' : 'danger'">
                  {{ executionPreview.global_enabled ? '已开启' : '已关闭' }}
                </el-tag>
              </div>
              <div class="execution-preview-item">
                <div class="preview-label">照片上传</div>
                <el-tag :key="`execution-photo-${executionPreview.allow_photo_upload}`" :type="executionPreview.allow_photo_upload ? 'success' : 'info'">
                  {{ executionPreview.allow_photo_upload ? '允许' : '禁止' }}
                </el-tag>
              </div>
              <div class="execution-preview-item">
                <div class="preview-label">设备绑定</div>
                <el-tag :key="`execution-binding-${executionPreview.allow_device_binding}`" :type="executionPreview.allow_device_binding ? 'success' : 'info'">
                  {{ executionPreview.allow_device_binding ? '允许' : '禁止' }}
                </el-tag>
              </div>
              <div class="execution-preview-item">
                <div class="preview-label">提交</div>
                <el-tag :key="`execution-submit-${executionPreview.allow_submit}`" :type="executionPreview.allow_submit ? 'success' : 'info'">
                  {{ executionPreview.allow_submit ? '允许' : '禁止' }}
                </el-tag>
              </div>
              <div class="execution-preview-item">
                <div class="preview-label">撤回</div>
                <el-tag :key="`execution-recall-${executionPreview.allow_recall}`" :type="executionPreview.allow_recall ? 'success' : 'info'">
                  {{ executionPreview.allow_recall ? '允许' : '禁止' }}
                </el-tag>
              </div>
            </div>

            <div class="execution-preview-section">
              <div class="preview-label">Web可见工单类型</div>
              <el-space wrap>
                <el-tag
                  v-for="type in executionPreview.visible_work_order_types"
                  :key="type"
                  effect="plain"
                >
                  {{ getWorkOrderTypeLabel(type) }}
                </el-tag>
                <span v-if="!executionPreview.visible_work_order_types.length" class="preview-muted">当前未放开任何可在 Web 端查看的工单类型</span>
              </el-space>
            </div>

            <div class="execution-preview-section">
              <div class="preview-label">Web可编辑工单类型</div>
              <el-space wrap>
                <el-tag
                  v-for="type in executionPreview.editable_work_order_types"
                  :key="`editable-${type}`"
                  type="success"
                  effect="plain"
                >
                  {{ getWorkOrderTypeLabel(type) }}
                </el-tag>
                <span v-if="!executionPreview.editable_work_order_types.length" class="preview-muted">当前没有可在 Web 端填写的工单类型，进入后会以只读方式查看</span>
              </el-space>
            </div>

            <div class="execution-preview-section" v-if="executionPreview.reasons.length">
              <div class="preview-label">当前限制</div>
              <el-space wrap>
                <el-tag
                  v-for="reason in executionPreview.reasons"
                  :key="reason"
                  type="warning"
                  effect="plain"
                >
                  {{ reason }}
                </el-tag>
              </el-space>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="职位" prop="position">
            <el-input
              v-model="form.position"
              placeholder="请输入职位"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12" v-if="isEditing">
          <el-form-item label="状态" prop="is_active">
            <el-switch
              v-model="form.is_active"
              active-text="启用"
              inactive-text="禁用"
              :disabled="!canChangeStatus"
            />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <div class="form-footer">
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="loading">
        {{ isEditing ? '更新' : '创建' }}
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { userAPI } from '@/api/user'
import { authzApi } from '@/api/authz'
import { useUserStore } from '@/stores/user'

// Props
const props = defineProps({
  user: {
    type: Object,
    default: null
  }
})

// Emits
const emit = defineEmits(['success', 'cancel'])

// 用户状态管理
const userStore = useUserStore()

// 响应式数据
const loading = ref(false)
const formRef = ref()
const roleOptions = ref([])
const executionPreviewLoading = ref(false)

// 表单数据
const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  full_name: '',
  phone: '',
  roles: ['user'],
  department: '',
  position: '',
  is_active: true
})

const createDefaultExecutionPreview = () => ({
  can_open_entry: false,
  is_user_active: true,
  has_web_login_permission: false,
  has_execute_permission: false,
  global_enabled: false,
  allow_photo_upload: true,
  allow_device_binding: true,
  allow_submit: true,
  allow_recall: true,
  allow_local_upload_without_geo: false,
  visible_work_order_types: [],
  editable_work_order_types: [],
  has_any_visible_type: false,
  has_any_editable_type: false,
  reasons: []
})

const executionPreviewState = ref(createDefaultExecutionPreview())
const executionPreview = computed(() => {
  const preview = executionPreviewState.value || createDefaultExecutionPreview()
  return {
    ...createDefaultExecutionPreview(),
    can_open_entry: Boolean(preview.can_open_entry),
    is_user_active: preview.is_user_active !== false,
    has_web_login_permission: Boolean(preview.has_web_login_permission),
    has_execute_permission: Boolean(preview.has_execute_permission),
    global_enabled: Boolean(preview.global_enabled),
    allow_photo_upload: preview.allow_photo_upload !== false,
    allow_device_binding: preview.allow_device_binding !== false,
    allow_submit: preview.allow_submit !== false,
    allow_recall: preview.allow_recall !== false,
    allow_local_upload_without_geo: Boolean(preview.allow_local_upload_without_geo),
    visible_work_order_types: normalizeCodeList(preview.visible_work_order_types),
    editable_work_order_types: normalizeCodeList(preview.editable_work_order_types),
    has_any_visible_type: Boolean(preview.has_any_visible_type),
    has_any_editable_type: Boolean(preview.has_any_editable_type),
    reasons: normalizeReasonList(preview.reasons),
  }
})

// 计算属性
const isEditing = computed(() => !!props.user)
const canChangeRole = computed(() => userStore.hasPermission('authz:manage:all'))
const canChangeStatus = computed(() => {
  if (!userStore.hasPermission('users:delete:write')) return false
  if (isEditing.value && props.user?.id === userStore.currentUser?.id) return false
  return true
})
const showExecutionPreview = computed(() => isEditing.value && canChangeRole.value && !!props.user?.id)
const executionPreviewDirty = computed(() => {
  if (!showExecutionPreview.value) return false
  const originalRoles = normalizeCodeList(props.user?.roles || (props.user?.role ? [props.user.role] : []))
  const currentRoles = normalizeCodeList(form.roles)
  return originalRoles.join('|') !== currentRoles.join('|')
})

// 表单验证规则
const rules = computed(() => {
  const baseRules = {
    username: [
      { required: true, message: '请输入用户名', trigger: 'blur' },
      { min: 3, max: 50, message: '用户名长度在 3 到 50 个字符', trigger: 'blur' },
      { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线', trigger: 'blur' }
    ],
    email: [
      { required: true, message: '请输入邮箱地址', trigger: 'blur' },
      { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
    ],
    full_name: [
      { max: 100, message: '姓名不能超过100个字符', trigger: 'blur' }
    ],
    phone: [
      {
        validator: (rule, value, callback) => {
          if (!value || value.toString().trim() === '') return callback()
          const normalized = value.toString().replace(/\s+/g, '')
          // E.164: "+" 开头，国家码非0，最多15位数字
          const ok = /^\+[1-9]\d{1,14}$/.test(normalized)
          if (!ok) return callback(new Error('请输入国际号码（E.164，例如 +14155550132）'))
          callback()
        },
        trigger: 'blur'
      }
    ],
    roles: [
      {
        validator: (rule, value, callback) => {
          if (!Array.isArray(value) || value.length === 0) {
            callback(new Error('请至少选择一个角色'))
            return
          }
          callback()
        },
        trigger: 'change'
      }
    ],
    department: [
      { max: 100, message: '部门名称不能超过100个字符', trigger: 'blur' }
    ],
    position: [
      { max: 100, message: '职位名称不能超过100个字符', trigger: 'blur' }
    ]
  }

  // 新增用户时需要密码验证
  if (!isEditing.value) {
    baseRules.password = [
      { required: true, message: '请输入密码', trigger: 'blur' },
      { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
    ]
    baseRules.confirmPassword = [
      { required: true, message: '请确认密码', trigger: 'blur' },
      {
        validator: (rule, value, callback) => {
          if (value !== form.password) {
            callback(new Error('两次输入的密码不一致'))
          } else {
            callback()
          }
        },
        trigger: 'blur'
      }
    ]
  }

  return baseRules
})

// 初始化表单数据
const initForm = () => {
  if (props.user) {
    // 编辑模式 - 填充现有数据
    form.username = props.user.username
    form.email = props.user.email
    form.full_name = props.user.full_name || ''
    form.phone = props.user.phone || ''
    const roles = Array.isArray(props.user.roles) ? props.user.roles : []
    form.roles = roles.length > 0 ? [...roles] : (props.user.role ? [props.user.role] : ['user'])
    form.department = props.user.department || ''
    form.position = props.user.position || ''
    form.is_active = props.user.is_active
  } else {
    // 新增模式 - 重置表单
    resetForm()
  }
}

const normalizeCodeList = (value) => {
  if (!Array.isArray(value)) return []
  return [...new Set(value.map(item => String(item || '').trim()).filter(Boolean))].sort()
}

const normalizeReasonList = (value) => {
  if (!Array.isArray(value)) return []
  return value.map(item => String(item || '').trim()).filter(Boolean)
}

const getWorkOrderTypeLabel = (value) => {
  const typeMap = {
    site_survey: '站点勘查',
    opening_inspection: '新站安装',
    equipment_replacement: '设备更换',
    ssv: 'SSV验收',
    maintenance: '维护检查',
    power_issue: '断电问题',
    transmission_issue: '传输问题',
    gps_issue: 'GPS问题',
    signal_issue: '信号问题'
  }
  return typeMap[value] || value
}

const resetExecutionPreview = () => {
  executionPreviewState.value = createDefaultExecutionPreview()
}

const loadExecutionPreview = async () => {
  if (!showExecutionPreview.value) {
    resetExecutionPreview()
    return
  }

  executionPreviewLoading.value = true
  try {
    const data = await authzApi.getUserEffectivePermissions(props.user.id)
    const preview = data?.work_order_execution || {}
    executionPreviewState.value = {
      ...createDefaultExecutionPreview(),
      can_open_entry: Boolean(preview.can_open_entry),
      is_user_active: preview.is_user_active !== false,
      has_web_login_permission: Boolean(preview.has_web_login_permission),
      has_execute_permission: Boolean(preview.has_execute_permission),
      global_enabled: Boolean(preview.global_enabled),
      allow_photo_upload: preview.allow_photo_upload !== false,
      allow_device_binding: preview.allow_device_binding !== false,
      allow_submit: preview.allow_submit !== false,
      allow_recall: preview.allow_recall !== false,
      allow_local_upload_without_geo: Boolean(preview.allow_local_upload_without_geo),
      visible_work_order_types: normalizeCodeList(preview.visible_work_order_types),
      editable_work_order_types: normalizeCodeList(preview.editable_work_order_types),
      has_any_visible_type: Boolean(preview.has_any_visible_type),
      has_any_editable_type: Boolean(preview.has_any_editable_type),
      reasons: normalizeReasonList(preview.reasons),
    }
  } catch (error) {
    resetExecutionPreview()
    ElMessage.error(error.response?.data?.detail || '加载 Web 工单执行预览失败')
  } finally {
    executionPreviewLoading.value = false
  }
}

// 重置表单
const resetForm = () => {
  form.username = ''
  form.email = ''
  form.password = ''
  form.confirmPassword = ''
  form.full_name = ''
  form.phone = ''
  form.roles = ['user']
  form.department = ''
  form.position = ''
  form.is_active = true
  
  formRef.value?.clearValidate()
}

// 提交表单
const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
    loading.value = true

    if (isEditing.value) {
      // 更新用户
      const updateData = {
        email: form.email,
        full_name: form.full_name || null,
        phone: form.phone ? form.phone.replace(/\s+/g, '') : null,
        department: form.department || null,
        position: form.position || null,
        is_active: form.is_active
      }

      // 角色由 authz:manage:all 控制
      if (canChangeRole.value) {
        updateData.roles = form.roles
      }

      await userAPI.updateUser(props.user.id, updateData)
      ElMessage.success('用户更新成功')
    } else {
      // 创建用户
      const createData = {
        username: form.username,
        email: form.email,
        password: form.password,
        full_name: form.full_name || null,
        phone: form.phone ? form.phone.replace(/\s+/g, '') : null,
        roles: form.roles,
        department: form.department || null,
        position: form.position || null
      }

      await userAPI.createUser(createData)
      ElMessage.success('用户创建成功')
    }

    emit('success')
  } catch (error) {
    if (error.message) {
      ElMessage.error(error.message)
    }
  } finally {
    loading.value = false
  }
}

// 取消操作
const handleCancel = () => {
  emit('cancel')
}

// 监听props变化
watch(() => props.user, initForm, { immediate: true })
watch(
  () => [props.user?.id, showExecutionPreview.value],
  () => {
    loadExecutionPreview()
  },
  { immediate: true }
)

// 组件挂载
onMounted(() => {
  loadRoleOptions()
  initForm()
})

const loadRoleOptions = async () => {
  try {
    const rows = await authzApi.listRoles()
    roleOptions.value = (rows || []).filter((r) => r.is_active !== false)
  } catch (error) {
    roleOptions.value = [
      { code: 'user', name: '普通用户' },
      { code: 'manager', name: '项目经理' },
      { code: 'warehouse_manager', name: '仓库管理员' },
      { code: 'inspector', name: '现场工程师' },
      { code: 'surveyor', name: '勘察人员' },
      { code: 'reviewer', name: '审核人员' },
      { code: 'planner', name: '规划人员' },
      { code: 'admin', name: '系统管理员' },
    ]
  }
}
</script>

<style scoped>
.user-form {
  padding: 20px;
}

.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}

.execution-preview-card {
  margin-bottom: 4px;
  border-radius: 12px;
}

.execution-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.execution-preview-alert {
  margin-bottom: 12px;
}

.execution-preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.execution-preview-item {
  padding: 12px 14px;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  background: #f8fafc;
}

.execution-preview-section {
  margin-top: 14px;
}

.preview-label {
  margin-bottom: 8px;
  color: #606266;
  font-size: 13px;
}

.preview-muted {
  color: #909399;
  font-size: 12px;
}
</style>
