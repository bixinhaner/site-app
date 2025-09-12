<template>
  <div class="import-history-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1>SN 导入记录</h1>
      <div class="header-actions">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索文件名/设备类型/仓库/导入人"
          clearable
          style="width: 320px"
          @keyup.enter="applySearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button @click="refresh" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 记录列表 -->
    <el-card class="table-card">
      <template #header>
        <div class="table-header">
          <span>导入记录</span>
          <div class="table-actions">
            <el-tag type="info">共 {{ filteredRecords.length }} 条</el-tag>
          </div>
        </div>
      </template>

      <el-table
        :data="paginatedRecords"
        v-loading="loading"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="import_date" label="导入时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.import_date) }}</template>
        </el-table-column>
        <el-table-column prop="file_name" label="文件名" min-width="200" />
        <el-table-column prop="equipment_type_name" label="设备类型" width="160" />
        <el-table-column prop="warehouse_name" label="仓库" width="160" />
        <el-table-column label="数量" width="220">
          <template #default="{ row }">
            <div class="counts">
              <el-tag size="small">总 {{ row.total_count }}</el-tag>
              <el-tag size="small" type="success">成功 {{ row.success_count }}</el-tag>
              <el-tag size="small" type="warning" v-if="row.duplicate_count > 0">重复 {{ row.duplicate_count }}</el-tag>
              <el-tag size="small" type="danger" v-if="row.failed_count > 0">失败 {{ row.failed_count }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="importer_name" label="导入人" width="120" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openDetails(row)">
              <el-icon><View /></el-icon>
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="filteredRecords.length"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailsVisible" size="70%" :with-header="false">
      <div class="drawer-header">
        <div>
          <h3>导入详情</h3>
          <div class="sub">文件：{{ currentRecord?.file_name }} ｜ 时间：{{ formatDateTime(currentRecord?.import_date) }}</div>
        </div>
        <el-button circle @click="detailsVisible = false"><el-icon><Close /></el-icon></el-button>
      </div>

      <el-card class="summary-card" v-if="currentRecord">
        <div class="summary-grid">
          <div class="summary-item"><span class="label">设备类型</span><span class="value">{{ currentRecord.equipment_type_name || '-' }}</span></div>
          <div class="summary-item"><span class="label">仓库</span><span class="value">{{ currentRecord.warehouse_name || '-' }}</span></div>
          <div class="summary-item"><span class="label">导入人</span><span class="value">{{ currentRecord.importer_name || '-' }}</span></div>
          <div class="summary-item"><span class="label">状态</span><span class="value"><el-tag :type="statusTagType(currentRecord.status)">{{ statusText(currentRecord.status) }}</el-tag></span></div>
        </div>
      </el-card>

      <el-card class="details-card">
        <template #header>
          <div class="table-header">
            <span>导入明细</span>
            <div class="table-actions">
              <el-input v-model="detailKeyword" placeholder="按SN/MAC/供应商过滤" clearable style="width: 260px" />
              <el-tag type="info">共 {{ filteredDetails.length }} 条</el-tag>
            </div>
          </div>
        </template>

        <el-table :data="filteredDetails" v-loading="detailsLoading" height="60vh" stripe>
          <el-table-column prop="line_number" label="行号" width="80" />
          <el-table-column prop="serial_number" label="SN序列号" width="200" />
          <el-table-column prop="mac_address" label="MAC地址" width="160" />
          <el-table-column prop="imei" label="IMEI" width="160" />
          <el-table-column prop="vendor" label="供应商" width="120" />
          <el-table-column prop="batch_number" label="批次号" width="140" />
          <el-table-column prop="import_status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="detailStatusTagType(row.import_status)">{{ detailStatusText(row.import_status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="error_message" label="错误信息" min-width="220" show-overflow-tooltip />
        </el-table>
      </el-card>
    </el-drawer>
  </div>
  
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { stockApi } from '../../api/stock'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const records = ref([])
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(20)

const detailsVisible = ref(false)
const currentRecord = ref(null)
const detailsLoading = ref(false)
const details = ref([])
const detailKeyword = ref('')

const refresh = async () => {
  try {
    loading.value = true
    const res = await stockApi.getImportHistory()
    records.value = res?.records || []
    // 如果带了 importId 参数，自动打开详情
    const importId = route.query.importId
    if (importId) {
      const found = records.value.find(r => r.id === importId)
      if (found) openDetails(found)
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('加载导入记录失败')
  } finally {
    loading.value = false
  }
}

const applySearch = () => {
  currentPage.value = 1
}

const filteredRecords = computed(() => {
  if (!searchKeyword.value) return records.value
  const kw = searchKeyword.value.toLowerCase()
  return records.value.filter(r =>
    (r.file_name || '').toLowerCase().includes(kw) ||
    (r.equipment_type_name || '').toLowerCase().includes(kw) ||
    (r.warehouse_name || '').toLowerCase().includes(kw) ||
    (r.importer_name || '').toLowerCase().includes(kw)
  )
})

const paginatedRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredRecords.value.slice(start, end)
})

const openDetails = async (record) => {
  currentRecord.value = record
  detailsVisible.value = true
  await loadDetails(record.id)
}

const loadDetails = async (importId) => {
  try {
    detailsLoading.value = true
    const res = await stockApi.getImportDetails(importId)
    details.value = res?.details || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载导入明细失败')
  } finally {
    detailsLoading.value = false
  }
}

const filteredDetails = computed(() => {
  if (!detailKeyword.value) return details.value
  const kw = detailKeyword.value.toLowerCase()
  return details.value.filter(d =>
    (d.serial_number || '').toLowerCase().includes(kw) ||
    (d.mac_address || '').toLowerCase().includes(kw) ||
    (d.vendor || '').toLowerCase().includes(kw) ||
    (d.batch_number || '').toLowerCase().includes(kw)
  )
})

const formatDateTime = (val) => {
  if (!val) return '-'
  const d = new Date(val)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const statusText = (s) => ({ processing: '处理中', completed: '已完成', failed: '失败' }[s] || s)
const statusTagType = (s) => ({ processing: 'info', completed: 'success', failed: 'danger' }[s] || 'info')
const detailStatusText = (s) => ({ success: '成功', failed: '失败', duplicate: '重复' }[s] || s)
const detailStatusTagType = (s) => ({ success: 'success', failed: 'danger', duplicate: 'warning' }[s] || 'info')

onMounted(() => {
  refresh()
})
</script>

<style scoped lang="scss">
.import-history-page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  h1 {
    margin: 0;
    font-size: 24px;
    color: var(--text-primary);
  }

  .header-actions {
    display: flex;
    gap: 12px;
  }
}

.table-card {
  border-radius: 8px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: var(--text-primary);
}

.counts {
  display: flex;
  gap: 6px;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0 16px 0;

  h3 {
    margin: 0;
    font-size: 18px;
  }
  .sub {
    color: var(--text-secondary);
    margin-top: 4px;
  }
}

.summary-card {
  margin-bottom: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.summary-item {
  display: flex;
  gap: 8px;
  .label { color: var(--text-secondary); }
  .value { color: var(--text-primary); font-weight: 500; }
}

.details-card {
  .table-header { margin-bottom: 8px; }
}
</style>

