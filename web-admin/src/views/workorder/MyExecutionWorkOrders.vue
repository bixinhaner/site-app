<template>
  <div class="page my-execution-page" v-loading="pageLoading">
    <div class="page-header">
      <div>
        <h1>我的执行工单</h1>
      </div>
      <div class="header-actions">
        <el-button @click="refreshAll"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <el-result
      v-if="pageUnavailable.title"
      icon="info"
      :title="pageUnavailable.title"
      :sub-title="pageUnavailable.subTitle"
    >
      <template #extra>
        <el-button type="primary" @click="loadPage">重新加载</el-button>
      </template>
    </el-result>

    <template v-else>
      <div class="group-grid mb16">
        <button
          v-for="group in GROUPS"
          :key="group.key"
          class="group-card"
          :class="[`group-card--${group.key}`, { 'group-card--selected': activeGroup === group.key }]"
          @click="changeGroup(group.key)"
        >
          <span class="group-card__label">{{ group.label }}</span>
          <strong class="group-card__value">{{ countLoading ? '...' : summary[group.key] }}</strong>
        </button>
      </div>

      <el-card class="toolbar-card mb16">
        <div class="toolbar">
          <el-input
            v-model="keyword"
            clearable
            placeholder="搜索标题、站点名称、站点编码"
            style="width: 300px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-select
            v-model="typeFilter"
            clearable
            placeholder="工单类型"
            style="width: 200px"
            @change="handleFilterChange"
          >
            <el-option
              v-for="option in allowedTypeOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-select
            v-model="sortMode"
            placeholder="排序方式"
            style="width: 180px"
            @change="handleFilterChange"
          >
            <el-option
              v-for="option in sortOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
        </div>
      </el-card>

      <el-card>
        <template #header>
          <div class="table-header">
            <div>
              <div class="table-title">{{ activeGroupMeta.label }}</div>
            </div>
            <el-tag :type="activeGroupMeta.tagType" effect="plain">{{ total }} 条</el-tag>
          </div>
        </template>

        <el-table :data="items" v-loading="listLoading" stripe>
          <el-table-column prop="title" label="工单" min-width="260">
            <template #default="{ row }">
              <div class="workorder-title">
                <div class="workorder-title__main">{{ row.title }}</div>
                <div class="workorder-title__meta">
                  <span>{{ row.site_name || '-' }}</span>
                  <span v-if="row.site_code">({{ row.site_code }})</span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="type" label="类型" width="150">
            <template #default="{ row }">
              <div class="type-cell">
                <span>{{ typeText(row.type) }}</span>
                <el-tag v-if="isReadonlyType(row.type)" size="small" type="info" effect="plain">仅App执行</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="due_date" label="截止时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.due_date) || '未设置' }}</template>
          </el-table-column>
          <el-table-column prop="updated_at" label="最近更新" width="170">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) || '-' }}</template>
          </el-table-column>
          <el-table-column label="备注/驳回意见" min-width="260">
            <template #default="{ row }">
              <div class="review-comment" :class="{ 'review-comment--warning': row.status === 'REJECTED' }">
                {{ row.review_comments || row.description || '—' }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openExecute(row)">
                {{ executeActionText(row) }}
                <el-icon class="action-arrow"><ArrowRight /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-empty
          v-if="!listLoading && !items.length"
          :description="emptyDescription"
        />

        <div class="pagination">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="loadList"
            @size-change="handlePageSizeChange"
          />
        </div>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, Refresh, Search } from '@element-plus/icons-vue'

import { workOrderAPI } from '@/api/workorder'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const GROUPS = [
  { key: 'pending', label: '待接受', statuses: ['PENDING'], tagType: 'warning' },
  { key: 'active', label: '执行中', statuses: ['ACTIVE'], tagType: 'primary' },
  { key: 'submitted', label: '已提交', statuses: ['SUBMITTED', 'UNDER_REVIEW'], tagType: 'success' },
  { key: 'rejected', label: '已驳回', statuses: ['REJECTED'], tagType: 'danger' },
]

const TYPE_LABEL_MAP = {
  site_survey: '站点勘查',
  opening_inspection: '新站安装',
  equipment_replacement: '设备更换',
  ssv: 'SSV 验收',
  maintenance: '维护检查',
  power_issue: '断电问题',
  transmission_issue: '传输问题',
  gps_issue: 'GPS问题',
  signal_issue: '信号问题',
}

const STATUS_LABEL_MAP = {
  PENDING: '待接受',
  ACTIVE: '执行中',
  SUBMITTED: '已提交',
  UNDER_REVIEW: '审核中',
  REJECTED: '已驳回',
  APPROVED: '已通过',
  ACTIVATED: '已激活',
  COMPLETED: '已完成',
  VOIDED: '已作废',
}

const sortOptions = [
  { value: 'updated_desc', label: '最近更新优先', sortBy: 'updated_at', sortOrder: 'desc' },
  { value: 'due_asc', label: '截止时间优先', sortBy: 'due_date', sortOrder: 'asc' },
  { value: 'created_desc', label: '最新创建优先', sortBy: 'created_at', sortOrder: 'desc' },
]

const pageLoading = ref(false)
const listLoading = ref(false)
const countLoading = ref(false)
const pageUnavailable = ref({ title: '', subTitle: '' })

const effectiveSettings = ref({
  enabled: false,
  allow_photo_upload: false,
  allow_device_binding: false,
  allow_submit: false,
  allow_recall: false,
  visible_work_order_types: [],
  editable_work_order_types: [],
  reasons: [],
})

const keyword = ref('')
const typeFilter = ref('')
const sortMode = ref('updated_desc')
const activeGroup = ref('pending')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const items = ref([])
const summary = ref({
  pending: 0,
  active: 0,
  submitted: 0,
  rejected: 0,
})

const currentUserId = computed(() => Number(userStore.currentUser?.id || 0))
const visibleTypes = computed(() => {
  const raw = effectiveSettings.value?.visible_work_order_types
  return Array.isArray(raw) ? raw : []
})

const editableTypes = computed(() => {
  const raw = effectiveSettings.value?.editable_work_order_types
  return Array.isArray(raw) ? raw : []
})

const allowedTypeOptions = computed(() => visibleTypes.value.map((type) => ({
  value: type,
  label: TYPE_LABEL_MAP[type] || type,
})))

const activeGroupMeta = computed(() => GROUPS.find(group => group.key === activeGroup.value) || GROUPS[0])

const emptyDescription = computed(() => {
  if (keyword.value || typeFilter.value) return '当前筛选条件下没有可查看工单'
  return `当前没有${activeGroupMeta.value.label}`
})

const buildCommonParams = (groupKey) => {
  const params = {
    assigned_to: currentUserId.value,
    status_in: (GROUPS.find(group => group.key === groupKey)?.statuses || []).join(','),
    web_execution_scope: 'visible',
  }

  const text = String(keyword.value || '').trim()
  if (text) params.keyword = text

  if (typeFilter.value) {
    params.type = typeFilter.value
  } else if (visibleTypes.value.length) {
    params.type_in = visibleTypes.value.join(',')
  }

  return params
}

const formatDateTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const typeText = (type) => TYPE_LABEL_MAP[type] || type
const statusText = (status) => STATUS_LABEL_MAP[status] || status

const statusTagType = (status) => {
  if (status === 'REJECTED') return 'danger'
  if (status === 'SUBMITTED' || status === 'UNDER_REVIEW') return 'success'
  if (status === 'PENDING') return 'warning'
  return 'primary'
}

const executeActionText = (row) => {
  if (isReadonlyType(row.type)) return '只读查看'
  if (row.status === 'PENDING') return '接受并执行'
  if (row.status === 'SUBMITTED' || row.status === 'UNDER_REVIEW') return '查看执行'
  return '进入执行'
}

const isReadonlyType = (type) => visibleTypes.value.includes(type) && !editableTypes.value.includes(type)

const loadEffectiveSettings = async () => {
  const data = await userStore.refreshAuthzProfile()
  const preview = data?.work_order_execution || userStore.workOrderExecution
  effectiveSettings.value = {
    enabled: Boolean(preview?.global_enabled),
    allow_photo_upload: Boolean(preview?.allow_photo_upload),
    allow_device_binding: Boolean(preview?.allow_device_binding),
    allow_submit: Boolean(preview?.allow_submit),
    allow_recall: Boolean(preview?.allow_recall),
    visible_work_order_types: Array.isArray(preview?.visible_work_order_types) ? preview.visible_work_order_types : [],
    editable_work_order_types: Array.isArray(preview?.editable_work_order_types) ? preview.editable_work_order_types : [],
    reasons: Array.isArray(preview?.reasons) ? preview.reasons : [],
  }

  if (!effectiveSettings.value.enabled) {
    pageUnavailable.value = {
      title: '当前未开启 Web 工单执行',
      subTitle: '系统配置还没有对当前账号放开浏览器填写工单能力。',
    }
    return false
  }

  if (!effectiveSettings.value.visible_work_order_types.length) {
    pageUnavailable.value = {
      title: '当前没有可在 Web 端查看的工单类型',
      subTitle: '系统配置没有给当前账号分配任何可在浏览器里查看的工单类型。',
    }
    return false
  }

  pageUnavailable.value = { title: '', subTitle: '' }
  if (typeFilter.value && !visibleTypes.value.includes(typeFilter.value)) {
    typeFilter.value = ''
  }
  return true
}

const loadCounts = async () => {
  countLoading.value = true
  try {
    const results = await Promise.all(
      GROUPS.map(group => workOrderAPI.searchWorkOrders({
        ...buildCommonParams(group.key),
        skip: 0,
        limit: 1,
      })),
    )
    summary.value = GROUPS.reduce((accumulator, group, index) => {
      accumulator[group.key] = Number(results[index]?.total || 0)
      return accumulator
    }, {})
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '加载工单分组统计失败')
  } finally {
    countLoading.value = false
  }
}

const loadList = async () => {
  listLoading.value = true
  try {
    const sortConfig = sortOptions.find(option => option.value === sortMode.value) || sortOptions[0]
    const response = await workOrderAPI.searchWorkOrders({
      ...buildCommonParams(activeGroup.value),
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
      sort_by: sortConfig.sortBy,
      sort_order: sortConfig.sortOrder,
    })
    items.value = Array.isArray(response?.work_orders) ? response.work_orders : []
    total.value = Number(response?.total || 0)
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '加载我的执行工单失败')
  } finally {
    listLoading.value = false
  }
}

const refreshAll = async () => {
  if (pageUnavailable.value.title) {
    await loadPage()
    return
  }
  await Promise.all([loadCounts(), loadList()])
}

const loadPage = async () => {
  pageLoading.value = true
  try {
    const enabled = await loadEffectiveSettings()
    if (!enabled) {
      items.value = []
      total.value = 0
      summary.value = { pending: 0, active: 0, submitted: 0, rejected: 0 }
      return
    }
    await Promise.all([loadCounts(), loadList()])
  } catch (error) {
    console.error(error)
    pageUnavailable.value = {
      title: '我的执行工单暂不可用',
      subTitle: error.response?.data?.detail || '加载当前账号的 Web 工单执行策略失败，请稍后重试。',
    }
  } finally {
    pageLoading.value = false
  }
}

const handleSearch = async () => {
  currentPage.value = 1
  await Promise.all([loadCounts(), loadList()])
}

const handleFilterChange = async () => {
  currentPage.value = 1
  await Promise.all([loadCounts(), loadList()])
}

const handlePageSizeChange = async () => {
  currentPage.value = 1
  await loadList()
}

const changeGroup = async (groupKey) => {
  if (groupKey === activeGroup.value) return
  activeGroup.value = groupKey
  currentPage.value = 1
  await loadList()
}

const openExecute = (row) => {
  router.push({ name: 'WorkOrderExecute', params: { id: row.id } })
}

onMounted(() => {
  loadPage()
})
</script>

<style scoped>
.page {
  padding: 24px;
  box-sizing: border-box;
}

.my-execution-page {
  min-height: calc(100vh - 120px);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.mb16 {
  margin-bottom: 16px;
}

.group-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.group-card {
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  background: #fff;
  padding: 14px 18px;
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.group-card:hover,
.group-card--selected {
  transform: translateY(-2px);
  box-shadow: 0 12px 26px rgba(15, 23, 42, 0.08);
}

.group-card--pending.group-card--selected {
  border-color: #f59e0b;
}

.group-card--active.group-card--selected {
  border-color: #3b82f6;
}

.group-card--submitted.group-card--selected {
  border-color: #10b981;
}

.group-card--rejected.group-card--selected {
  border-color: #ef4444;
}

.group-card__label {
  display: block;
  color: #6b7280;
  font-size: 13px;
}

.group-card__value {
  display: block;
  margin-top: 8px;
  font-size: 28px;
  line-height: 1;
  color: #111827;
}

.toolbar-card {
  border-radius: 18px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.table-title {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
}

.workorder-title__main {
  font-weight: 600;
  color: #111827;
}

.workorder-title__meta {
  margin-top: 6px;
  color: #6b7280;
  font-size: 12px;
}

.review-comment {
  color: #4b5563;
  line-height: 1.6;
}

.review-comment--warning {
  color: #b91c1c;
}

.action-arrow {
  margin-left: 4px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 1200px) {
  .group-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .page {
    padding: 16px;
  }

  .group-grid {
    grid-template-columns: 1fr;
  }

  .toolbar {
    flex-direction: column;
  }

  .toolbar :deep(.el-input),
  .toolbar :deep(.el-select),
  .toolbar :deep(.el-button) {
    width: 100% !important;
  }

  .table-header {
    flex-direction: column;
  }
}
</style>
