<template>
  <div class="page">
    <div class="page-header">
      <h1>LLD 规划总览</h1>
      <div class="header-actions">
        <el-button v-if="activeTab === 'summary'" @click="exportSummary" :loading="exportingSummary">
          <el-icon><Download /></el-icon>
          导出汇总
        </el-button>
        <el-button v-else @click="exportCells" :loading="exportingCells">
          <el-icon><Download /></el-icon>
          导出可回导模板
        </el-button>
        <el-button @click="refresh" :loading="loading" type="primary">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-card class="mb16">
      <div class="filter-row">
        <el-select v-model="statusFilter" placeholder="站点状态" clearable style="width: 140px">
          <el-option label="规划中" value="planning" />
          <el-option label="规划完成" value="planned" />
          <el-option label="施工中" value="construction" />
          <el-option label="已开通" value="operational" />
          <el-option label="维护中" value="maintenance" />
        </el-select>
        <el-select
          v-model="bandFilter"
          placeholder="Band"
          multiple
          clearable
          filterable
          allow-create
          style="width: 220px"
        >
          <el-option v-for="b in bandOptions" :key="b" :label="b" :value="b" />
        </el-select>
        <el-date-picker
          v-model="timeRange"
          type="datetimerange"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          range-separator="至"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width: 340px"
        />
        <el-button type="primary" @click="search">
          <el-icon><Search /></el-icon>
          查询
        </el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
      <div class="filter-tip">时间筛选基于规划更新时间</div>
    </el-card>

    <el-card>
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="规划汇总" name="summary">
          <el-table :data="summaryList" v-loading="summaryLoading" border stripe>
            <el-table-column prop="site_code" label="站点编码" width="140" />
            <el-table-column prop="site_name" label="站点名称" min-width="180" />
            <el-table-column prop="site_type" label="类型" width="120" />
            <el-table-column prop="city" label="城市" width="120" />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag>{{ row.status }}</el-tag>
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
            <el-table-column prop="planning_updated_at" label="规划更新时间" min-width="170" />
            <el-table-column prop="planning_created_at" label="规划创建时间" min-width="170" />
            <el-table-column prop="planning_notes" label="备注" min-width="160" show-overflow-tooltip />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openDetail(row)">
                  查看详情
                </el-button>
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
        </el-tab-pane>

        <el-tab-pane label="LLD 小区明细" name="cells">
          <el-tabs v-model="cellRat" class="inner-tabs" @tab-change="handleCellRatChange">
            <el-tab-pane label="4G" name="LTE">
              <el-table
                :data="cellList"
                v-loading="cellLoading"
                border
                size="small"
                height="560"
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
                height="560"
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

          <div class="pagination">
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Search, Download } from '@element-plus/icons-vue'
import sitePlanningApi from '@/api/sitePlanning'

const router = useRouter()

const activeTab = ref('summary')
const statusFilter = ref('')
const bandFilter = ref([])
const timeRange = ref([])

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

const formatBands = (bands) => {
  if (Array.isArray(bands) && bands.length) return bands.join(', ')
  return '-'
}

const formatRange = (minVal, maxVal) => {
  if (minVal === null || minVal === undefined) return '-'
  if (maxVal === null || maxVal === undefined) return '-'
  return `${minVal}° ~ ${maxVal}°`
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

const buildParams = () => {
  const params = {
    status: statusFilter.value || undefined,
    band: bandFilter.value?.length ? bandFilter.value.join(',') : undefined,
  }
  if (Array.isArray(timeRange.value) && timeRange.value.length === 2) {
    params.start_time = timeRange.value[0]
    params.end_time = timeRange.value[1]
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
  } else {
    loadSummary()
  }
}

const handleCellRatChange = (tabName) => {
  cellRat.value = tabName
  cellPage.value = 1
  loadCells()
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

onMounted(() => {
  loadSummary()
})
</script>

<style scoped lang="scss">
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  h1 {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
  }
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.filter-tip {
  margin-top: 8px;
  color: var(--text-light);
  font-size: 12px;
}

.mb16 {
  margin-bottom: 16px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.cell-table {
  width: 100%;
}
</style>
