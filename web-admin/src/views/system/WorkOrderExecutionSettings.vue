<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>Web工单执行配置</h1>
        <div class="page-subtitle">控制 Web 管理端是否允许接受、填写、上传照片、绑定设备、提交与撤回工单。</div>
      </div>
      <div class="header-actions">
        <el-button @click="loadConfig" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button type="primary" @click="save" :loading="saving" :disabled="!canEdit">
          <el-icon><Document /></el-icon>保存
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="!canEdit"
      class="mb16"
      type="warning"
      :closable="false"
      show-icon
      title="当前用户仅可查看配置，修改需要 Web 工单执行配置管理权限"
    />

    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>当前账号生效策略</span>
          <el-button text @click="loadEffective">刷新生效值</el-button>
        </div>
      </template>
      <div class="effective-grid">
        <div class="effective-item">
          <div class="effective-label">Web执行入口</div>
          <el-tag :type="effective.enabled ? 'success' : 'info'">{{ effective.enabled ? '启用' : '关闭' }}</el-tag>
        </div>
        <div class="effective-item">
          <div class="effective-label">照片上传</div>
          <el-tag :type="effective.allow_photo_upload ? 'success' : 'info'">{{ effective.allow_photo_upload ? '允许' : '禁止' }}</el-tag>
        </div>
        <div class="effective-item">
          <div class="effective-label">无定位本地上传</div>
          <el-tag :type="effective.allow_local_upload_without_geo ? 'warning' : 'info'">{{ effective.allow_local_upload_without_geo ? '允许' : '禁止' }}</el-tag>
        </div>
        <div class="effective-item">
          <div class="effective-label">设备绑定</div>
          <el-tag :type="effective.allow_device_binding ? 'success' : 'info'">{{ effective.allow_device_binding ? '允许' : '禁止' }}</el-tag>
        </div>
        <div class="effective-item">
          <div class="effective-label">工单提交</div>
          <el-tag :type="effective.allow_submit ? 'success' : 'info'">{{ effective.allow_submit ? '允许' : '禁止' }}</el-tag>
        </div>
        <div class="effective-item">
          <div class="effective-label">工单撤回</div>
          <el-tag :type="effective.allow_recall ? 'success' : 'info'">{{ effective.allow_recall ? '允许' : '禁止' }}</el-tag>
        </div>
      </div>
      <div class="mt12">
        <div class="effective-label">允许的工单类型</div>
        <el-space wrap>
          <el-tag v-for="type in effective.allowed_work_order_types" :key="type" effect="plain">
            {{ getTypeLabel(type) }}
          </el-tag>
          <span v-if="!effective.allowed_work_order_types.length" class="hint">当前未放开任何工单类型。</span>
        </el-space>
      </div>
    </el-card>

    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>全局默认</span>
        </div>
      </template>
      <el-form label-width="160px" :disabled="!canEdit">
        <el-form-item label="Web工单执行">
          <el-switch v-model="form.enabled.default" active-text="启用" inactive-text="关闭" />
        </el-form-item>
        <el-form-item label="照片上传">
          <el-switch v-model="form.allow_photo_upload.default" active-text="允许" inactive-text="禁止" />
        </el-form-item>
        <el-form-item label="无定位本地上传">
          <el-switch v-model="form.allow_local_upload_without_geo.default" active-text="允许" inactive-text="禁止" />
        </el-form-item>
        <el-form-item label="设备绑定/解绑">
          <el-switch v-model="form.allow_device_binding.default" active-text="允许" inactive-text="禁止" />
        </el-form-item>
        <el-form-item label="工单提交">
          <el-switch v-model="form.allow_submit.default" active-text="允许" inactive-text="禁止" />
        </el-form-item>
        <el-form-item label="工单撤回">
          <el-switch v-model="form.allow_recall.default" active-text="允许" inactive-text="禁止" />
        </el-form-item>
        <el-form-item label="允许工单类型">
          <el-select
            v-model="form.allowed_work_order_types.default"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            style="width: 100%"
          >
            <el-option v-for="type in workOrderTypeOptions" :key="type.value" :label="type.label" :value="type.value" />
          </el-select>
          <div class="hint mt8">全局关闭时，下面所有角色/用户覆盖都不会开放执行入口。</div>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>按角色覆盖</span>
        </div>
      </template>
      <el-table :data="roleRows" border size="small">
        <el-table-column prop="label" label="角色" width="140" fixed="left" />
        <el-table-column label="执行入口" width="120">
          <template #default="{ row }">
            <el-select
              :model-value="toMode(form.enabled.per_role[row.key])"
              :disabled="!canEdit"
              style="width: 100%"
              @change="value => applyRoleBoolOverride('enabled', row.key, value)"
            >
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="照片上传" width="120">
          <template #default="{ row }">
            <el-select
              :model-value="toMode(form.allow_photo_upload.per_role[row.key])"
              :disabled="!canEdit"
              style="width: 100%"
              @change="value => applyRoleBoolOverride('allow_photo_upload', row.key, value)"
            >
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="无定位本地上传" width="150">
          <template #default="{ row }">
            <el-select
              :model-value="toMode(form.allow_local_upload_without_geo.per_role[row.key])"
              :disabled="!canEdit"
              style="width: 100%"
              @change="value => applyRoleBoolOverride('allow_local_upload_without_geo', row.key, value)"
            >
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="设备绑定" width="120">
          <template #default="{ row }">
            <el-select
              :model-value="toMode(form.allow_device_binding.per_role[row.key])"
              :disabled="!canEdit"
              style="width: 100%"
              @change="value => applyRoleBoolOverride('allow_device_binding', row.key, value)"
            >
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="提交" width="120">
          <template #default="{ row }">
            <el-select
              :model-value="toMode(form.allow_submit.per_role[row.key])"
              :disabled="!canEdit"
              style="width: 100%"
              @change="value => applyRoleBoolOverride('allow_submit', row.key, value)"
            >
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="撤回" width="120">
          <template #default="{ row }">
            <el-select
              :model-value="toMode(form.allow_recall.per_role[row.key])"
              :disabled="!canEdit"
              style="width: 100%"
              @change="value => applyRoleBoolOverride('allow_recall', row.key, value)"
            >
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="允许工单类型" min-width="280">
          <template #default="{ row }">
            <el-select
              :model-value="form.allowed_work_order_types.per_role[row.key] || []"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              clearable
              :disabled="!canEdit"
              style="width: 100%"
              placeholder="留空表示跟随全局"
              @change="value => applyRoleTypeOverride(row.key, value)"
            >
              <el-option v-for="type in workOrderTypeOptions" :key="type.value" :label="type.label" :value="type.value" />
            </el-select>
          </template>
        </el-table-column>
      </el-table>
      <div class="hint mt12">角色覆盖只影响 Web 管理端执行页，不影响 App 现有工单填写流程。</div>
    </el-card>

    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>按用户覆盖</span>
        </div>
      </template>
      <div class="user-rule-form">
        <el-select
          v-model="newUserRule.user_id"
          filterable
          remote
          reserve-keyword
          placeholder="搜索用户名/姓名/邮箱"
          :remote-method="searchUsers"
          :loading="userSelectLoading"
          style="width: 260px"
          :disabled="!canEdit"
        >
          <el-option v-for="option in userOptions" :key="option.id" :label="option.label" :value="String(option.id)" />
        </el-select>
        <el-button type="primary" :disabled="!canEdit" @click="addUserRule">添加用户覆盖</el-button>
      </div>

      <el-table class="mt12" :data="form.user_overrides" border size="small" empty-text="暂无用户覆盖">
        <el-table-column label="用户" min-width="200" fixed="left">
          <template #default="{ row }">
            <div>{{ row.user_label || `用户 #${row.user_id}` }}</div>
            <div class="hint">ID: {{ row.user_id }}</div>
          </template>
        </el-table-column>
        <el-table-column label="执行入口" width="120">
          <template #default="{ row }">
            <el-select v-model="row.enabled" :disabled="!canEdit" style="width: 100%">
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="照片上传" width="120">
          <template #default="{ row }">
            <el-select v-model="row.allow_photo_upload" :disabled="!canEdit" style="width: 100%">
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="无定位本地上传" width="150">
          <template #default="{ row }">
            <el-select v-model="row.allow_local_upload_without_geo" :disabled="!canEdit" style="width: 100%">
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="设备绑定" width="120">
          <template #default="{ row }">
            <el-select v-model="row.allow_device_binding" :disabled="!canEdit" style="width: 100%">
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="提交" width="120">
          <template #default="{ row }">
            <el-select v-model="row.allow_submit" :disabled="!canEdit" style="width: 100%">
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="撤回" width="120">
          <template #default="{ row }">
            <el-select v-model="row.allow_recall" :disabled="!canEdit" style="width: 100%">
              <el-option v-for="option in boolModeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="允许工单类型" min-width="280">
          <template #default="{ row }">
            <el-select
              v-model="row.allowed_work_order_types"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              clearable
              :disabled="!canEdit"
              style="width: 100%"
              placeholder="留空表示跟随全局/角色"
            >
              <el-option v-for="type in workOrderTypeOptions" :key="type.value" :label="type.label" :value="type.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ $index }">
            <el-button type="danger" text :disabled="!canEdit" @click="removeUserRule($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Document, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { workOrderExecutionSettingsApi } from '@/api/system'
import { userAPI } from '@/api/user'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const saving = ref(false)
const userSelectLoading = ref(false)
const userOptions = ref([])

const boolModeOptions = [
  { label: '跟随默认', value: '' },
  { label: '开启/允许', value: 'allow' },
  { label: '关闭/禁止', value: 'deny' },
]

const roleRows = [
  { key: 'admin', label: '系统管理员' },
  { key: 'manager', label: '项目经理' },
  { key: 'reviewer', label: '审核人员' },
  { key: 'inspector', label: '现场工程师' },
  { key: 'surveyor', label: '勘察人员' },
  { key: 'planner', label: '规划人员' },
  { key: 'warehouse_manager', label: '仓库管理员' },
]

const workOrderTypeOptions = [
  { value: 'site_survey', label: '站点勘查' },
  { value: 'opening_inspection', label: '新站安装' },
  { value: 'equipment_replacement', label: '设备更换' },
  { value: 'ssv', label: 'SSV 验收' },
  { value: 'maintenance', label: '维护检查' },
  { value: 'power_issue', label: '断电问题' },
  { value: 'transmission_issue', label: '传输问题' },
  { value: 'gps_issue', label: 'GPS问题' },
  { value: 'signal_issue', label: '信号问题' },
]

const createBoolRule = (defaultValue) => ({
  default: defaultValue,
  per_role: {},
})

const createDefaultForm = () => ({
  enabled: createBoolRule(false),
  allow_photo_upload: createBoolRule(true),
  allow_device_binding: createBoolRule(true),
  allow_submit: createBoolRule(true),
  allow_recall: createBoolRule(true),
  allow_local_upload_without_geo: createBoolRule(false),
  allowed_work_order_types: {
    default: workOrderTypeOptions.map(item => item.value),
    per_role: {},
  },
  user_overrides: [],
  config_version: 1,
})

const form = reactive(createDefaultForm())
const effective = reactive({
  enabled: false,
  allow_photo_upload: true,
  allow_device_binding: true,
  allow_submit: true,
  allow_recall: true,
  allow_local_upload_without_geo: false,
  allowed_work_order_types: [],
})

const newUserRule = reactive({
  user_id: '',
})

const canEdit = computed(() => userStore.hasPermission('system:workorder-execution-settings:write'))

const boolKeys = [
  'enabled',
  'allow_photo_upload',
  'allow_device_binding',
  'allow_submit',
  'allow_recall',
  'allow_local_upload_without_geo',
]

const getTypeLabel = (value) => workOrderTypeOptions.find(item => item.value === value)?.label || value

const toMode = (value) => {
  if (value === true) return 'allow'
  if (value === false) return 'deny'
  return ''
}

const fromMode = (value) => {
  if (value === 'allow') return true
  if (value === 'deny') return false
  return undefined
}

const normalizeTypeList = (list = []) => {
  const out = []
  ;(Array.isArray(list) ? list : []).forEach((item) => {
    const value = String(item || '').trim()
    if (!value || out.includes(value)) return
    out.push(value)
  })
  return out
}

const resetForm = () => {
  Object.assign(form, createDefaultForm())
}

const buildUserOverrideRow = (userId, label = '') => ({
  user_id: String(userId || '').trim(),
  user_label: label || '',
  enabled: '',
  allow_photo_upload: '',
  allow_device_binding: '',
  allow_submit: '',
  allow_recall: '',
  allow_local_upload_without_geo: '',
  allowed_work_order_types: [],
})

const hydrateUserLabels = async (userIds = []) => {
  const ids = [...new Set((userIds || []).map(item => String(item || '').trim()).filter(Boolean))]
  await Promise.all(ids.map(async (id) => {
    try {
      const user = await userAPI.getUser(id)
      const label = user.full_name || user.username || `用户 #${id}`
      const target = form.user_overrides.find(item => item.user_id === id)
      if (target) target.user_label = label
    } catch (error) {
      const target = form.user_overrides.find(item => item.user_id === id)
      if (target && !target.user_label) target.user_label = `用户 #${id}`
    }
  }))
}

const applyRoleBoolOverride = (key, roleKey, value) => {
  const boolValue = fromMode(value)
  if (typeof boolValue === 'undefined') {
    delete form[key].per_role[roleKey]
    return
  }
  form[key].per_role[roleKey] = boolValue
}

const applyRoleTypeOverride = (roleKey, values) => {
  const list = normalizeTypeList(values)
  if (!list.length) {
    delete form.allowed_work_order_types.per_role[roleKey]
    return
  }
  form.allowed_work_order_types.per_role[roleKey] = list
}

const loadEffective = async () => {
  try {
    const data = await workOrderExecutionSettingsApi.getEffectiveSettings()
    Object.assign(effective, {
      ...data,
      allowed_work_order_types: normalizeTypeList(data?.allowed_work_order_types || []),
    })
  } catch (error) {
    console.error(error)
  }
}

const loadConfig = async () => {
  loading.value = true
  try {
    resetForm()
    const data = await workOrderExecutionSettingsApi.getSettings()
    form.config_version = Number(data?.config_version || 1)

    boolKeys.forEach((key) => {
      form[key].default = Boolean(data?.[key]?.default ?? form[key].default)
      form[key].per_role = { ...(data?.[key]?.per_role || {}) }
    })

    form.allowed_work_order_types.default = normalizeTypeList(
      data?.allowed_work_order_types?.default || form.allowed_work_order_types.default,
    )
    form.allowed_work_order_types.per_role = { ...(data?.allowed_work_order_types?.per_role || {}) }

    const userIdSet = new Set()
    const rows = []

    boolKeys.forEach((key) => {
      const perUser = data?.[key]?.per_user || {}
      Object.entries(perUser).forEach(([userId, value]) => {
        userIdSet.add(String(userId))
        let row = rows.find(item => item.user_id === String(userId))
        if (!row) {
          row = buildUserOverrideRow(userId)
          rows.push(row)
        }
        row[key] = toMode(value)
      })
    })

    Object.entries(data?.allowed_work_order_types?.per_user || {}).forEach(([userId, value]) => {
      userIdSet.add(String(userId))
      let row = rows.find(item => item.user_id === String(userId))
      if (!row) {
        row = buildUserOverrideRow(userId)
        rows.push(row)
      }
      row.allowed_work_order_types = normalizeTypeList(value || [])
    })

    form.user_overrides = rows
    await hydrateUserLabels([...userIdSet])
    await loadEffective()
  } catch (error) {
    console.error(error)
    ElMessage.error('加载 Web 工单执行配置失败')
  } finally {
    loading.value = false
  }
}

const buildPayload = () => {
  const payload = {
    config_version: form.config_version,
    allowed_work_order_types: {
      default: normalizeTypeList(form.allowed_work_order_types.default),
      per_role: {},
      per_user: {},
    },
  }

  boolKeys.forEach((key) => {
    payload[key] = {
      default: Boolean(form[key].default),
      per_role: {},
      per_user: {},
    }

    Object.entries(form[key].per_role || {}).forEach(([roleKey, value]) => {
      if (typeof value === 'boolean') payload[key].per_role[roleKey] = value
    })
  })

  Object.entries(form.allowed_work_order_types.per_role || {}).forEach(([roleKey, list]) => {
    const normalized = normalizeTypeList(list || [])
    if (normalized.length) payload.allowed_work_order_types.per_role[roleKey] = normalized
  })

  ;(form.user_overrides || []).forEach((row) => {
    const userId = String(row.user_id || '').trim()
    if (!userId) return

    boolKeys.forEach((key) => {
      const value = fromMode(row[key])
      if (typeof value === 'boolean') payload[key].per_user[userId] = value
    })

    const types = normalizeTypeList(row.allowed_work_order_types || [])
    if (types.length) payload.allowed_work_order_types.per_user[userId] = types
  })

  return payload
}

const save = async () => {
  saving.value = true
  try {
    const payload = buildPayload()
    const saved = await workOrderExecutionSettingsApi.updateSettings(payload)
    form.config_version = Number(saved?.config_version || form.config_version)
    ElMessage.success('Web 工单执行配置已保存')
    await loadConfig()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '保存配置失败')
  } finally {
    saving.value = false
  }
}

const searchUsers = async (query) => {
  const keyword = String(query || '').trim()
  if (!keyword) {
    userOptions.value = []
    return
  }
  userSelectLoading.value = true
  try {
    const res = await userAPI.searchUsers({ keyword, limit: 20 })
    userOptions.value = (res?.users || []).map((user) => ({
      id: String(user.id),
      label: user.full_name || user.username || `用户 #${user.id}`,
    }))
  } catch (error) {
    console.error(error)
    userOptions.value = []
  } finally {
    userSelectLoading.value = false
  }
}

const addUserRule = () => {
  const userId = String(newUserRule.user_id || '').trim()
  if (!userId) {
    ElMessage.warning('请选择用户')
    return
  }
  if (form.user_overrides.some(item => item.user_id === userId)) {
    ElMessage.warning('该用户已存在覆盖配置')
    return
  }
  const option = userOptions.value.find(item => item.id === userId)
  form.user_overrides.push(buildUserOverrideRow(userId, option?.label || ''))
  newUserRule.user_id = ''
}

const removeUserRule = (index) => {
  form.user_overrides.splice(index, 1)
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.page {
  padding: 24px;
  box-sizing: border-box;
}

.page-subtitle {
  color: #909399;
  font-size: 13px;
  margin-top: 6px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.mb16 {
  margin-bottom: 16px;
}

.mt8 {
  margin-top: 8px;
}

.mt12 {
  margin-top: 12px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hint {
  color: #909399;
  font-size: 12px;
}

.effective-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.effective-item {
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 14px 16px;
  background: linear-gradient(180deg, #fcfdff 0%, #f7f9fc 100%);
}

.effective-label {
  color: #606266;
  font-size: 13px;
  margin-bottom: 8px;
}

.user-rule-form {
  display: flex;
  align-items: center;
  gap: 12px;
}

@media (max-width: 900px) {
  .page {
    padding: 16px;
  }

  .page-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }

  .header-actions,
  .user-rule-form {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>
