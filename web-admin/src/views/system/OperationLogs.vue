<template>
  <div class="page">
    <div class="page-header">
      <h1>操作日志</h1>
    </div>

    <el-alert
      v-if="!canView"
      type="warning"
      title="当前页面仅管理员/项目经理可访问"
      :closable="false"
      show-icon
      class="mb16"
    />

    <el-card class="filter-card mb16" v-loading="settingsLoading">
      <el-form :inline="true" class="filter-form" size="small">
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            @change="handleSearch"
          />
        </el-form-item>
        <el-form-item label="来源端">
          <el-select v-model="filters.client" clearable placeholder="全部" style="width: 150px" @change="handleSearch">
            <el-option v-for="c in options.clients" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="模块">
          <el-select v-model="filters.module" clearable placeholder="全部" style="width: 160px" @change="handleSearch">
            <el-option v-for="m in options.modules" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="filters.action" clearable placeholder="全部" style="width: 160px" @change="handleSearch">
            <el-option v-for="a in options.actions" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="结果">
          <el-select v-model="filters.is_success" clearable placeholder="全部" style="width: 120px" @change="handleSearch">
            <el-option label="成功" :value="true" />
            <el-option label="失败" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字">
          <el-input
            v-model="filters.keyword"
            clearable
            placeholder="用户名/描述/对象/路径"
            style="width: 240px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
        </el-form-item>

        <el-form-item class="filter-actions">
          <el-button type="primary" :disabled="loading" @click="handleSearch">
            <el-icon><Search /></el-icon>查询
          </el-button>
          <el-button :disabled="loading" @click="resetFilters">重置</el-button>

          <el-dropdown trigger="click" @command="handleMoreCommand">
            <el-button :disabled="loading || settingsLoading" size="small">
              <el-icon><MoreFilled /></el-icon>更多
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="settings" :disabled="!canView">保留天数设置</el-dropdown-item>
                <el-dropdown-item
                  command="cleanupRetention"
                  divided
                  :disabled="!canView || cleaningByRetention"
                >
                  按保留天数清理
                </el-dropdown-item>
                <el-dropdown-item command="cleanupFilters" :disabled="!canView || cleaningByFilters">
                  按当前筛选条件清理
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <div class="card-header-left">
            <span>日志列表</span>
            <span class="hint">共 {{ total }} 条</span>
          </div>
          <div class="header-actions">
            <el-button size="small" @click="refresh" :loading="loading || settingsLoading">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
            <el-button size="small" type="primary" @click="exportExcel" :loading="exporting">
              <el-icon><Download /></el-icon>导出Excel
            </el-button>
          </div>
        </div>
      </template>

      <div class="table-wheel-area" @wheel.capture="handleTableWheel">
        <el-table :data="items" size="small" stripe border style="width: 100%">
          <el-table-column label="时间" width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.occurred_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="username" label="用户" width="120" show-overflow-tooltip />
          <el-table-column prop="user_role" label="角色" width="90" show-overflow-tooltip />
          <el-table-column prop="ip" label="IP" width="130" show-overflow-tooltip />
          <el-table-column prop="client" label="来源端" width="100" show-overflow-tooltip />
          <el-table-column prop="module" label="模块" width="110" show-overflow-tooltip />
          <el-table-column prop="action" label="动作" width="110" show-overflow-tooltip />
          <el-table-column label="结果" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.is_success" type="success">成功</el-tag>
              <el-tag v-else type="danger">失败</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="operation_desc" label="可读描述" min-width="280" show-overflow-tooltip />
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row.id)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination" v-if="total > pageSize">
          <el-pagination
            background
            layout="prev, pager, next, jumper"
            :page-size="pageSize"
            :current-page="page"
            :total="total"
            @current-change="handlePageChange"
          />
        </div>
      </div>
    </el-card>

    <el-drawer v-model="detailVisible" title="日志详情" size="55%">
      <div v-if="detail" class="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="时间">{{ formatDateTime(detail.occurred_at) }}</el-descriptions-item>
          <el-descriptions-item label="结果">
            <el-tag v-if="detail.is_success" type="success">成功</el-tag>
            <el-tag v-else type="danger">失败</el-tag>
            <span class="ml8">HTTP {{ detail.status_code }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="用户">{{ detail.username || '匿名' }}</el-descriptions-item>
          <el-descriptions-item label="角色">{{ detail.user_role || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源端">{{ detail.client || '-' }}</el-descriptions-item>
          <el-descriptions-item label="模块/动作">{{ (detail.module || '-') + ' / ' + (detail.action || '-') }}</el-descriptions-item>
          <el-descriptions-item label="对象">{{ buildObjectText(detail) }}</el-descriptions-item>
          <el-descriptions-item label="IP">{{ detail.ip || '-' }}</el-descriptions-item>
          <el-descriptions-item label="路径">{{ (detail.request_method || '-') + ' ' + (detail.request_path || '-') }}</el-descriptions-item>
          <el-descriptions-item label="可读描述" :span="2">{{ detail.operation_desc || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.error_message" label="错误信息" :span="2">
            <span class="error">{{ detail.error_message }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-collapse class="mt12">
          <el-collapse-item title="路径参数 / 查询参数" name="params">
            <pre class="json-view">{{ prettyJson({ path_params: detail.path_params, query_params: detail.query_params }) }}</pre>
          </el-collapse-item>
          <el-collapse-item title="提交变更值（请求体）" name="body">
            <pre class="json-view">{{ prettyJson(detail.request_body) }}</pre>
          </el-collapse-item>
          <el-collapse-item title="User-Agent" name="ua">
            <pre class="json-view">{{ detail.user_agent || '-' }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-drawer>

    <el-dialog
      v-model="settingsDialogVisible"
      title="保留天数设置"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form label-width="90px" size="small">
        <el-form-item label="保留天数">
          <el-input-number v-model="retentionDays" :min="1" :max="3650" />
        </el-form-item>
        <div class="dialog-hint">
          后台会按保留天数定期清理过期日志（以服务端记录时间为准）。
        </div>
      </el-form>
      <template #footer>
        <el-button size="small" @click="settingsDialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="savingSettings" @click="saveSettings">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, MoreFilled, Refresh, Search } from '@element-plus/icons-vue'
import { operationLogsApi } from '@/api/operationLogs'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const canView = computed(() => userStore.isAdmin)

const loading = ref(false)
const exporting = ref(false)
const settingsLoading = ref(false)
const savingSettings = ref(false)
const cleaningByRetention = ref(false)
const cleaningByFilters = ref(false)

const retentionDays = ref(90)

const options = ref({ modules: [], actions: [], clients: [] })

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const timeRange = ref(null)
const filters = ref({
  keyword: '',
  module: '',
  action: '',
  client: '',
  is_success: null,
})

const detailVisible = ref(false)
const detail = ref(null)

const settingsDialogVisible = ref(false)

const formatDateTime = (v) => {
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleString()
}

const prettyJson = (obj) => {
  try {
    return JSON.stringify(obj ?? null, null, 2)
  } catch (e) {
    return String(obj ?? '')
  }
}

const isScrollableY = (el) => {
  if (!el || !(el instanceof HTMLElement)) return false
  const style = window.getComputedStyle(el)
  const overflowY = style.overflowY
  if (overflowY !== 'auto' && overflowY !== 'scroll') return false
  return el.scrollHeight > el.clientHeight + 1
}

const findScrollableWithin = (startEl, stopEl) => {
  let el = startEl instanceof Element ? startEl : null
  while (el && el !== stopEl && el !== document.body) {
    if (isScrollableY(el)) return el
    el = el.parentElement
  }
  return null
}

const handleTableWheel = (e) => {
  if (e.ctrlKey) return
  const absX = Math.abs(e.deltaX || 0)
  const absY = Math.abs(e.deltaY || 0)
  if (absY <= absX) return

  const currentTarget = e.currentTarget
  if (!currentTarget || !(currentTarget instanceof HTMLElement)) return

  const internalScrollable = findScrollableWithin(e.target, currentTarget)
  if (internalScrollable) return

  const scrollEl = currentTarget.closest('.layout-main')
  if (!scrollEl) return

  const maxTop = scrollEl.scrollHeight - scrollEl.clientHeight
  if (maxTop <= 0) return

  const prev = scrollEl.scrollTop
  const next = Math.max(0, Math.min(maxTop, prev + e.deltaY))
  if (next === prev) return

  scrollEl.scrollTop = next
  e.preventDefault()
}

const buildObjectText = (row) => {
  const parts = []
  if (row.object_type) parts.push(row.object_type)
  if (row.object_name) parts.push(`名称:${row.object_name}`)
  if (row.object_id) parts.push(`ID:${row.object_id}`)
  return parts.length ? parts.join('，') : '-'
}

const buildQueryParams = () => {
  const params = {
    page: page.value,
    page_size: pageSize.value,
    keyword: filters.value.keyword || undefined,
    module: filters.value.module || undefined,
    action: filters.value.action || undefined,
    client: filters.value.client || undefined,
    is_success: filters.value.is_success === null ? undefined : filters.value.is_success,
  }
  if (Array.isArray(timeRange.value) && timeRange.value.length === 2) {
    const [dateFrom, dateTo] = timeRange.value
    if (dateFrom) params.date_from = new Date(dateFrom).toISOString()
    if (dateTo) params.date_to = new Date(dateTo).toISOString()
  }
  return params
}

const loadOptions = async () => {
  try {
    const resp = await operationLogsApi.options({ days: 365 })
    options.value = resp || { modules: [], actions: [], clients: [] }
  } catch (e) {
    options.value = { modules: [], actions: [], clients: [] }
  }
}

const loadSettings = async () => {
  settingsLoading.value = true
  try {
    const resp = await operationLogsApi.getSettings()
    retentionDays.value = Number(resp?.retention_days || 90)
  } catch (e) {
    ElMessage.error('加载日志设置失败')
  } finally {
    settingsLoading.value = false
  }
}

const loadList = async () => {
  loading.value = true
  try {
    const resp = await operationLogsApi.page(buildQueryParams())
    items.value = resp?.items || []
    total.value = resp?.total || 0
  } catch (e) {
    ElMessage.error('加载操作日志失败')
  } finally {
    loading.value = false
  }
}

const refresh = async () => {
  await Promise.all([loadOptions(), loadSettings()])
  await loadList()
}

const handleSearch = async () => {
  page.value = 1
  await loadList()
}

const handlePageChange = async (p) => {
  page.value = p
  await loadList()
}

const resetFilters = async () => {
  filters.value = { keyword: '', module: '', action: '', client: '', is_success: null }
  timeRange.value = null
  await handleSearch()
}

const handleMoreCommand = async (cmd) => {
  if (cmd === 'settings') {
    settingsDialogVisible.value = true
    return
  }
  if (cmd === 'cleanupRetention') {
    try {
      await cleanupByRetention()
    } catch (e) {
      // ignore
    }
    return
  }
  if (cmd === 'cleanupFilters') {
    try {
      await cleanupByFilters()
    } catch (e) {
      // ignore
    }
  }
}

const saveSettings = async () => {
  if (!canView.value) return
  savingSettings.value = true
  try {
    await operationLogsApi.updateSettings({ retention_days: retentionDays.value })
    ElMessage.success('已保存')
    settingsDialogVisible.value = false
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    savingSettings.value = false
  }
}

const cleanupByRetention = async () => {
  if (!canView.value) return
  try {
    await ElMessageBox.confirm(
      `确认清理超过 ${retentionDays.value} 天的操作日志？`,
      '提示',
      { type: 'warning' },
    )
  } catch (e) {
    return
  }

  cleaningByRetention.value = true
  try {
    const resp = await operationLogsApi.cleanup({ retention_days: retentionDays.value })
    ElMessage.success(`清理完成，删除 ${resp?.deleted_count || 0} 条`)
    await loadList()
  } catch (e) {
    ElMessage.error('清理失败')
  } finally {
    cleaningByRetention.value = false
  }
}

const cleanupByFilters = async () => {
  if (!canView.value) return
  const params = buildQueryParams()
  try {
    await ElMessageBox.confirm(
      '确认按当前筛选条件清理日志？此操作不可恢复。',
      '提示',
      { type: 'warning' },
    )
  } catch (e) {
    return
  }

  cleaningByFilters.value = true
  try {
    const payload = {
      keyword: params.keyword,
      module: params.module,
      action: params.action,
      client: params.client,
      is_success: params.is_success,
      date_from: params.date_from,
      date_to: params.date_to,
    }
    const resp = await operationLogsApi.cleanup(payload)
    ElMessage.success(`清理完成，删除 ${resp?.deleted_count || 0} 条`)
    await loadList()
  } catch (e) {
    ElMessage.error('清理失败')
  } finally {
    cleaningByFilters.value = false
  }
}

const exportExcel = async () => {
  exporting.value = true
  try {
    const params = buildQueryParams()
    // 导出不带分页参数
    delete params.page
    delete params.page_size

    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (tz) params.tz = tz
    params.tz_offset = new Date().getTimezoneOffset()

    const blob = await operationLogsApi.exportExcel(params)
    const url = window.URL.createObjectURL(new Blob([blob]))
    const a = document.createElement('a')
    a.href = url
    a.download = `operation_logs_${Date.now()}.xlsx`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    const detail = e?.response?.data?.detail
    ElMessage.error(detail || '导出失败')
  } finally {
    exporting.value = false
  }
}

const openDetail = async (id) => {
  detailVisible.value = true
  detail.value = null
  try {
    const resp = await operationLogsApi.detail(id)
    detail.value = resp
  } catch (e) {
    ElMessage.error('加载详情失败')
  }
}

onMounted(refresh)
</script>

<style scoped>
.page {
  padding: 24px;
}
.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 0;
  border-bottom: none;
}
.page-header h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.mb16 {
  margin-bottom: 12px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.filter-card :deep(.el-card__body) {
  padding: 12px 12px 10px;
}
.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
}
.filter-form :deep(.el-form-item) {
  margin: 0;
}
.filter-form :deep(.el-form-item__label) {
  padding-right: 6px;
}
.filter-actions {
  margin-left: auto;
}
.table-wheel-area {
  width: 100%;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.detail {
  padding-bottom: 12px;
}
.dialog-hint {
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
  padding: 0 4px;
}
.json-view {
  background: #0b1021;
  color: #d6deeb;
  padding: 12px;
  border-radius: 8px;
  overflow: auto;
  font-size: 12px;
}
.error {
  color: #f56c6c;
}
.ml8 {
  margin-left: 8px;
}
.mt12 {
  margin-top: 12px;
}
</style>
