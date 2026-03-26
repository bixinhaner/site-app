<template>
  <div ref="pageRef" class="page">
    <div class="page-header">
      <h1>LLD 规划总览</h1>
    </div>

    <el-card class="filter-card mb16">
      <el-form :inline="true" class="filter-form" size="small">
        <el-form-item label="站点状态">
          <el-select v-model="statusFilter" placeholder="全部" clearable style="width: 140px">
            <el-option label="规划中" value="planning" />
            <el-option label="规划完成" value="planned" />
            <el-option label="施工中" value="construction" />
            <el-option label="已开通" value="operational" />
            <el-option label="维护中" value="maintenance" />
          </el-select>
        </el-form-item>

        <el-form-item label="Band">
          <el-select
            v-model="bandFilter"
            placeholder="全部"
            multiple
            clearable
            filterable
            allow-create
            style="width: 220px"
          >
            <el-option v-for="b in bandOptions" :key="b" :label="b" :value="b" />
          </el-select>
        </el-form-item>

        <el-form-item label="规划更新时间">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始（规划更新时间）"
            end-placeholder="结束（规划更新时间）"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 360px"
          />
        </el-form-item>

        <el-form-item label="站点">
          <el-input
            v-model="siteKeyword"
            clearable
            placeholder="按站点编码 / 名称搜索"
            style="width: 220px"
            @keyup.enter.prevent="search"
          />
        </el-form-item>

        <el-form-item class="filter-actions">
          <el-button type="primary" :disabled="loading" @click="search">
            <el-icon><Search /></el-icon>查询
          </el-button>
          <el-button :disabled="loading" @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="content-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="规划汇总" name="summary">
          <div class="tab-toolbar">
            <div class="tab-toolbar-left">
              <span>规划汇总</span>
              <span class="hint">共 {{ summaryTotal }} 条</span>
            </div>
            <div class="tab-toolbar-actions">
              <el-button
                size="small"
                :disabled="summaryLoading"
                :loading="exportingSummary"
                @click="exportSummary"
              >
                <el-icon><Download /></el-icon>导出汇总
              </el-button>
              <el-button size="small" type="primary" :loading="loading" @click="refresh">
                <el-icon><Refresh /></el-icon>刷新
              </el-button>
            </div>
          </div>

          <div class="table-wheel-area" @wheel.capture="handleTableWheel">
            <el-table :data="summaryList" v-loading="summaryLoading" border stripe size="small">
              <el-table-column prop="site_code" label="站点编码" width="140" />
              <el-table-column prop="site_name" label="站点名称" min-width="180" />
              <el-table-column prop="site_type" label="类型" width="120" />
              <el-table-column prop="city" label="城市" width="120" />
              <el-table-column prop="status" label="状态" width="120">
                <template #default="{ row }">
                  <el-tag>{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="编辑权限" width="110">
                <template #default="{ row }">
                  <el-tooltip v-if="policyReason(row)" :content="policyReason(row)" placement="top">
                    <el-tag :type="policyTagType(row)">{{ policyText(row) }}</el-tag>
                  </el-tooltip>
                  <el-tag v-else :type="policyTagType(row)">{{ policyText(row) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="planning_version" label="LLD 版本" width="100" />
              <el-table-column prop="bands" label="Bands" min-width="140">
                <template #default="{ row }">
                  {{ formatBands(row.bands) }}
                </template>
              </el-table-column>
              <el-table-column prop="sector_count" label="扇区数" width="80" />
              <el-table-column prop="lte_cell_count" label="4G Cells" width="100" />
              <el-table-column prop="nr_cell_count" label="5G Cells" width="100" />
              <el-table-column label="机械下倾" min-width="140">
                <template #default="{ row }">
                  {{ formatRange(row.mechanical_downtilt_min, row.mechanical_downtilt_max) }}
                </template>
              </el-table-column>
              <el-table-column label="电子下倾" min-width="140">
                <template #default="{ row }">
                  {{ formatRange(row.electrical_downtilt_min, row.electrical_downtilt_max) }}
                </template>
              </el-table-column>
              <el-table-column prop="planning_updated_at" label="规划更新时间" min-width="170">
                <template #default="{ row }">
                  {{ formatDateTime(row.planning_updated_at) }}
                </template>
              </el-table-column>
              <el-table-column prop="planning_created_at" label="规划创建时间" min-width="170">
                <template #default="{ row }">
                  {{ formatDateTime(row.planning_created_at) }}
                </template>
              </el-table-column>
              <el-table-column prop="planning_notes" label="备注" min-width="160" show-overflow-tooltip />
              <el-table-column label="操作" width="160" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="openDetail(row)">查看详情</el-button>
                  <el-tooltip
                    v-if="!canEditRow(row)"
                    :content="policyReason(row) || '当前不允许编辑'"
                    placement="top"
                  >
                    <span>
                      <el-button link type="success" size="small" disabled>编辑规划</el-button>
                    </span>
                  </el-tooltip>
                  <el-button v-else link type="success" size="small" @click="openEdit(row)">编辑规划</el-button>
                </template>
              </el-table-column>
            </el-table>

            <div class="pagination">
              <el-pagination
                v-model:current-page="summaryPage"
                v-model:page-size="summarySize"
                :total="summaryTotal"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @size-change="onSummarySizeChange"
                @current-change="onSummaryPageChange"
              />
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="LLD 小区明细" name="cells">
          <div class="tab-toolbar">
            <div class="tab-toolbar-left">
              <span>LLD 小区明细</span>
              <span class="hint">共 {{ cellTotal }} 条</span>
            </div>
            <div class="tab-toolbar-actions">
              <el-button
                size="small"
                :disabled="cellLoading"
                :loading="exportingCells"
                @click="exportCells"
              >
                <el-icon><Download /></el-icon>导出可回导模板
              </el-button>
              <el-button size="small" type="primary" :loading="loading" @click="refresh">
                <el-icon><Refresh /></el-icon>刷新
              </el-button>
            </div>
          </div>

          <el-tabs v-model="cellRat" class="inner-tabs" @tab-change="handleCellRatChange">
            <el-tab-pane label="4G" name="LTE">
              <el-table
                :data="cellList"
                v-loading="cellLoading"
                border
                size="small"
                :height="cellsTableHeight"
                class="cell-table"
              >
                <el-table-column
                  v-for="h in cellHeaders"
                  :key="h"
                  :prop="h"
                  :label="h"
                  :min-width="120"
                  show-overflow-tooltip
                />
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="5G" name="NR">
              <el-table
                :data="cellList"
                v-loading="cellLoading"
                border
                size="small"
                :height="cellsTableHeight"
                class="cell-table"
              >
                <el-table-column
                  v-for="h in cellHeaders"
                  :key="h"
                  :prop="h"
                  :label="h"
                  :min-width="120"
                  show-overflow-tooltip
                />
              </el-table>
            </el-tab-pane>
          </el-tabs>

          <div class="pagination cells-pagination">
            <el-pagination
              v-model:current-page="cellPage"
              v-model:page-size="cellSize"
              :total="cellTotal"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="onCellSizeChange"
              @current-change="onCellPageChange"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Search, Download } from '@element-plus/icons-vue'
import sitePlanningApi from '@/api/sitePlanning'

const router = useRouter()

const pageRef = ref(null)
const activeTab = ref('summary')
const statusFilter = ref('')
const bandFilter = ref([])
const timeRange = ref([])
const siteKeyword = ref('')

const summaryList = ref([])
const summaryTotal = ref(0)
const summaryPage = ref(1)
const summarySize = ref(20)
const summaryLoading = ref(false)
const exportingSummary = ref(false)

const cellList = ref([])
const cellHeaders = ref([])
const cellTotal = ref(0)
const cellPage = ref(1)
const cellSize = ref(20)
const cellLoading = ref(false)
const exportingCells = ref(false)
const cellRat = ref('LTE')

const bandOptions = ['B1', 'B3', 'n41', 'n78', 'n1', 'n3']

const loading = computed(() => summaryLoading.value || cellLoading.value)

const cellsTableHeight = ref(560)

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

const getActiveCellTableEl = () => {
  const pageEl = pageRef.value
  if (!pageEl) return null
  const candidates = Array.from(pageEl.querySelectorAll('.cell-table'))
  return candidates.find((el) => el instanceof HTMLElement && el.offsetParent !== null) || null
}

const recalcCellsTableHeight = () => {
  if (activeTab.value !== 'cells') return

  const pageEl = pageRef.value
  if (!pageEl) return

  const tableEl = getActiveCellTableEl()
  if (!tableEl) return

  const layoutMain = pageEl.closest('.layout-main')
  const layoutBottom = layoutMain instanceof HTMLElement ? layoutMain.getBoundingClientRect().bottom : window.innerHeight

  const paginationEl = pageEl.querySelector('.cells-pagination')
  const paginationHeight =
    paginationEl instanceof HTMLElement ? paginationEl.getBoundingClientRect().height : 0

  const gap = 12
  const safeBottom = 12
  const nextHeight = Math.max(320, Math.floor(layoutBottom - tableEl.getBoundingClientRect().top - paginationHeight - gap - safeBottom))
  if (Number.isFinite(nextHeight)) {
    cellsTableHeight.value = nextHeight
  }
}

const formatBands = (bands) => {
  if (Array.isArray(bands) && bands.length) return bands.join(', ')
  return '-'
}

const formatRange = (minVal, maxVal) => {
  if (minVal === null || minVal === undefined) return '-'
  if (maxVal === null || maxVal === undefined) return '-'
  return `${minVal}° ~ ${maxVal}°`
}

const formatDateTime = (val) => {
  if (!val) return '-'
  const d = new Date(val)
  if (Number.isNaN(d.getTime())) return String(val)
  return d.toLocaleString('zh-CN')
}

const toUtcIsoParam = (val) => {
  if (!val) return undefined
  const d = val instanceof Date ? val : new Date(val)
  if (Number.isNaN(d.getTime())) return undefined
  return d.toISOString()
}

const formatExportDate = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const hours = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  return `${year}${month}${day}_${hours}${minutes}`
}

const downloadBlob = (blob, filename) => {
  const url = window.URL.createObjectURL(new Blob([blob]))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

const policyText = (row) => {
  const mode = row?.edit_policy?.mode
  if (mode === 'full') return '可编辑'
  if (mode === 'limited') return '受限'
  if (mode === 'readonly') return '只读'
  return '-'
}

const policyTagType = (row) => {
  const mode = row?.edit_policy?.mode
  if (mode === 'full') return 'success'
  if (mode === 'limited') return 'warning'
  if (mode === 'readonly') return 'info'
  return 'info'
}

const policyReason = (row) => row?.edit_policy?.reason || ''
const canEditRow = (row) => !!row?.edit_policy?.can_edit

const buildParams = () => {
  const params = {
    status: statusFilter.value || undefined,
    band: bandFilter.value?.length ? bandFilter.value.join(',') : undefined,
    site_keyword: siteKeyword.value.trim() || undefined,
  }
  if (Array.isArray(timeRange.value) && timeRange.value.length === 2) {
    const start = toUtcIsoParam(timeRange.value[0])
    const end = toUtcIsoParam(timeRange.value[1])
    if (start && end) {
      params.start_time = start
      params.end_time = end
    }
  }
  return params
}

const loadSummary = async () => {
  try {
    summaryLoading.value = true
    const params = buildParams()
    params.skip = (summaryPage.value - 1) * summarySize.value
    params.limit = summarySize.value
    const res = await sitePlanningApi.listLldPlanning(params)
    summaryList.value = res?.items || []
    summaryTotal.value = res?.total || 0
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '加载规划汇总失败')
  } finally {
    summaryLoading.value = false
  }
}

const loadCells = async () => {
  try {
    cellLoading.value = true
    const params = buildParams()
    params.rat = cellRat.value
    params.skip = (cellPage.value - 1) * cellSize.value
    params.limit = cellSize.value
    const res = await sitePlanningApi.listLldCellsTemplate(params)
    cellHeaders.value = res?.headers || []
    cellList.value = res?.items || []
    cellTotal.value = res?.total || 0
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '加载 LLD 小区明细失败')
  } finally {
    cellLoading.value = false
  }
}

const exportSummary = async () => {
  try {
    exportingSummary.value = true
    const params = buildParams()
    const blob = await sitePlanningApi.exportLldPlanning(params)
    downloadBlob(blob, `lld_planning_summary_${formatExportDate()}.xlsx`)
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '导出汇总失败')
  } finally {
    exportingSummary.value = false
  }
}

const exportCells = async () => {
  try {
    exportingCells.value = true
    const params = buildParams()
    const blob = await sitePlanningApi.exportLldCells(params)
    downloadBlob(blob, `lld_planning_cells_${formatExportDate()}.xlsx`)
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '导出明细失败')
  } finally {
    exportingCells.value = false
  }
}

const search = () => {
  summaryPage.value = 1
  cellPage.value = 1
  loadSummary()
  if (activeTab.value === 'cells') {
    loadCells()
  }
}

const resetFilters = () => {
  statusFilter.value = ''
  bandFilter.value = []
  timeRange.value = []
  siteKeyword.value = ''
  search()
}

const refresh = () => {
  if (activeTab.value === 'cells') {
    loadCells()
  } else {
    loadSummary()
  }
}

const handleTabChange = (tabName) => {
  activeTab.value = tabName
  if (tabName === 'cells') {
    loadCells()
    nextTick(() => {
      recalcCellsTableHeight()
    })
  } else {
    loadSummary()
  }
}

const handleCellRatChange = (tabName) => {
  cellRat.value = tabName
  cellPage.value = 1
  loadCells()
  nextTick(() => {
    recalcCellsTableHeight()
  })
}

const onSummarySizeChange = (size) => {
  summarySize.value = size
  summaryPage.value = 1
  loadSummary()
}

const onSummaryPageChange = (page) => {
  summaryPage.value = page
  loadSummary()
}

const onCellSizeChange = (size) => {
  cellSize.value = size
  cellPage.value = 1
  loadCells()
}

const onCellPageChange = (page) => {
  cellPage.value = page
  loadCells()
}

const openDetail = (row) => {
  if (!row?.site_id) return
  router.push({ name: 'SitePlanningLld', params: { id: row.site_id } })
}

const openEdit = (row) => {
  if (!row?.site_id) return
  router.push({ name: 'SitePlanningLld', params: { id: row.site_id }, query: { edit: '1' } })
}

onMounted(() => {
  loadSummary()
})

watch(
  () => activeTab.value,
  async (v) => {
    if (v !== 'cells') return
    await nextTick()
    recalcCellsTableHeight()
  },
)

watch(
  () => cellRat.value,
  async () => {
    if (activeTab.value !== 'cells') return
    await nextTick()
    recalcCellsTableHeight()
  },
)

const handleResize = () => {
  recalcCellsTableHeight()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped lang="scss">
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

  h1 {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
    color: #303133;
  }
}

.mb16 {
  margin-bottom: 12px;
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

.content-card :deep(.el-card__body) {
  padding: 12px;
}

.content-card :deep(.el-tabs__header) {
  margin: 0 0 8px;
}

.tab-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.tab-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  color: #303133;
}

.tab-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hint {
  font-weight: 400;
  color: #909399;
  font-size: 12px;
}

.table-wheel-area {
  width: 100%;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.cell-table {
  width: 100%;
}
</style>
