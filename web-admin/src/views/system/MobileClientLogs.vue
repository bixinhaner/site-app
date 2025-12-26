<template>
  <div class="page">
    <div class="page-header">
      <h1>移动端日志</h1>
    </div>

    <el-alert
      v-if="!canView"
      type="warning"
      title="当前页面仅管理员/项目经理可访问"
      :closable="false"
      show-icon
      class="mb16"
    />

    <el-card class="filter-card mb16">
      <el-form :inline="true" class="filter-form" size="small">
        <el-form-item label="时间">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            style="width: 360px"
            @change="handleSearch"
          />
        </el-form-item>

        <el-form-item label="用户ID">
          <el-input
            v-model="filters.user_id"
            clearable
            placeholder="例如 1"
            style="width: 120px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
        </el-form-item>

        <el-form-item label="页面">
          <el-input
            v-model="filters.route"
            clearable
            placeholder="pages/home/home"
            style="width: 200px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
        </el-form-item>

        <el-form-item label="关键字">
          <el-input
            v-model="filters.keyword"
            clearable
            placeholder="内容/位置/页面"
            style="width: 260px"
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
            <el-button size="small" :disabled="loading || settingsLoading">
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
                <el-dropdown-item
                  command="cleanupFilters"
                  :disabled="!canView || cleaningByFilters"
                >
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
            <el-button size="small" @click="refresh" :loading="loading">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
          </div>
        </div>
      </template>

      <div class="table-wheel-area" @wheel.capture="handleTableWheel">
        <el-table :data="items" size="small" stripe border style="width: 100%">
          <el-table-column label="时间" width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.occurred_at || row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="username" label="用户" width="120" show-overflow-tooltip />
          <el-table-column prop="route" label="页面" width="180" show-overflow-tooltip />
          <el-table-column label="内容" min-width="420" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="msg">
                <div class="msg-main">{{ row.message }}</div>
                <div v-if="row.at" class="msg-at">{{ row.at }}</div>
              </div>
            </template>
          </el-table-column>
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
          <el-descriptions-item label="时间">{{ formatDateTime(detail.occurred_at || detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="用户">{{ detail.username || '-' }}</el-descriptions-item>
          <el-descriptions-item label="设备ID">{{ detail.device_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="App版本" :span="2">
            {{ (detail.app_version_name || '-') + ' / ' + (detail.app_version_code ?? '-') }}
          </el-descriptions-item>
          <el-descriptions-item label="平台">{{ detail.platform || '-' }}</el-descriptions-item>
          <el-descriptions-item label="网络">{{ detail.network_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="页面" :span="2">{{ detail.route || '-' }}</el-descriptions-item>
          <el-descriptions-item label="位置" :span="2">{{ detail.at || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.level === 'ERROR'" label="级别">{{ detail.level }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.level === 'ERROR'" label="提示">
            ERROR 级别建议优先查看 Context
          </el-descriptions-item>
          <el-descriptions-item label="内容" :span="2">{{ detail.message || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-collapse class="mt12">
          <el-collapse-item title="Context" name="ctx">
            <pre class="json-view">{{ prettyJson(detail.context) }}</pre>
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
          后台会按保留天数定期清理过期日志（以服务端入库时间为准）。
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
import { MoreFilled, Refresh, Search } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { mobileClientLogsApi } from '@/api/mobileClientLogs'

const userStore = useUserStore()
const canView = computed(() => userStore.isAdmin)

const loading = ref(false)
const settingsLoading = ref(false)
const savingSettings = ref(false)
const cleaningByRetention = ref(false)
const cleaningByFilters = ref(false)
const retentionDays = ref(7)

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)

const timeRange = ref(null)
const filters = ref({
  keyword: '',
  user_id: '',
  route: '',
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

  // 表格内部如果存在可滚动容器（例如未来设置了 table height），则优先让内部滚动
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

const buildParams = () => {
  const params = {
    page: page.value,
    page_size: pageSize.value,
    tag: 'console',
  }

  const [from, to] = Array.isArray(timeRange.value) ? timeRange.value : []
  if (from) params.date_from = from
  if (to) params.date_to = to

  if (filters.value.keyword) params.keyword = filters.value.keyword
  if (filters.value.route) params.route = filters.value.route

  const userId = String(filters.value.user_id || '').trim()
  if (userId) params.user_id = Number(userId)

  return params
}

const buildCleanupPayload = () => {
  const payload = {
    tag: 'console',
  }

  const [from, to] = Array.isArray(timeRange.value) ? timeRange.value : []
  if (from) payload.date_from = new Date(from).toISOString()
  if (to) payload.date_to = new Date(to).toISOString()

  if (filters.value.keyword) payload.keyword = filters.value.keyword
  if (filters.value.route) payload.route = filters.value.route

  const userId = String(filters.value.user_id || '').trim()
  if (userId) payload.user_id = Number(userId)

  return payload
}

const loadSettings = async () => {
  if (!canView.value) return
  settingsLoading.value = true
  try {
    const resp = await mobileClientLogsApi.getSettings()
    retentionDays.value = Number(resp?.retention_days || 7)
  } catch (e) {
    ElMessage.error('加载日志设置失败')
  } finally {
    settingsLoading.value = false
  }
}

const loadPage = async () => {
  if (!canView.value) return
  try {
    loading.value = true
    const res = await mobileClientLogsApi.page(buildParams())
    items.value = res?.items || []
    total.value = res?.total || 0
  } catch (e) {
    console.error(e)
    const detailMsg = e?.response?.data?.detail
    ElMessage.error(detailMsg || '加载移动端日志失败')
  } finally {
    loading.value = false
  }
}

const refresh = async () => {
  page.value = 1
  await Promise.all([loadSettings(), loadPage()])
}

const handleSearch = () => {
  page.value = 1
  loadPage()
}

const resetFilters = () => {
  timeRange.value = null
  filters.value = {
    keyword: '',
    user_id: '',
    route: '',
  }
  page.value = 1
  loadPage()
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
    await mobileClientLogsApi.updateSettings({
      retention_days: Number(retentionDays.value || 7),
    })
    ElMessage.success('已保存')
    settingsDialogVisible.value = false
    await loadSettings()
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
      `确认清理超过 ${retentionDays.value} 天的移动端日志？`,
      '提示',
      { type: 'warning' },
    )
  } catch (e) {
    return
  }

  cleaningByRetention.value = true
  try {
    const resp = await mobileClientLogsApi.cleanup({
      retention_days: Number(retentionDays.value || 7),
    })
    ElMessage.success(`清理完成，删除 ${resp?.deleted_count || 0} 条`)
    await refresh()
  } catch (e) {
    ElMessage.error('清理失败')
  } finally {
    cleaningByRetention.value = false
  }
}

const cleanupByFilters = async () => {
  if (!canView.value) return
  const payload = buildCleanupPayload()
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
    const resp = await mobileClientLogsApi.cleanup(payload)
    ElMessage.success(`清理完成，删除 ${resp?.deleted_count || 0} 条`)
    await refresh()
  } catch (e) {
    ElMessage.error('清理失败')
  } finally {
    cleaningByFilters.value = false
  }
}

const handlePageChange = (p) => {
  page.value = p
  loadPage()
}

const openDetail = async (id) => {
  try {
    const res = await mobileClientLogsApi.detail(id)
    detail.value = res
    detailVisible.value = true
  } catch (e) {
    console.error(e)
    const detailMsg = e?.response?.data?.detail
    ElMessage.error(detailMsg || '加载日志详情失败')
  }
}

onMounted(() => {
  refresh()
})
</script>

<style scoped>
.page {
  padding: 24px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
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
.mt12 {
  margin-top: 12px;
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
  align-items: center;
  gap: 8px;
}
.hint {
  color: #909399;
  font-size: 12px;
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
.pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.msg {
  max-width: 100%;
}
.msg-main {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.msg-at {
  color: #6b7280;
  font-size: 12px;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
}
.json-view {
  white-space: pre-wrap;
  word-break: break-word;
  background: #0b1020;
  color: #e5e7eb;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
}
.dialog-hint {
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
  padding: 0 4px;
}
</style>
