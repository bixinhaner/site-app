<template>
  <div class="page-container">
    <div class="page-header">
      <div class="title-block">
        <h2>待确认出库</h2>
        <div class="subtitle">仓库确认出库支持“部分确认”，主设备不强制复扫（可扫码快速勾选）</div>
      </div>
      <div class="header-actions">
        <el-button @click="load" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="card filters-card">
      <el-row :gutter="16">
        <el-col :span="4">
          <el-select v-model="filters.status_filter" placeholder="状态" @change="resetAndLoad">
            <el-option label="待确认" value="pending_confirm" />
            <el-option label="部分确认" value="partially_confirmed" />
            <el-option label="已确认" value="confirmed" />
            <el-option label="已驳回" value="rejected" />
            <el-option label="已取消" value="canceled" />
            <el-option label="全部" value="all" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.warehouse_id" placeholder="仓库" clearable filterable @change="resetAndLoad">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
          </el-select>
        </el-col>
        <el-col :span="9">
          <el-input v-model="filters.keyword" placeholder="搜索领料单号/申请单号" clearable @keyup.enter="resetAndLoad">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
            <template #append>
              <el-button type="primary" @click="resetAndLoad">查询</el-button>
            </template>
          </el-input>
        </el-col>
        <el-col :span="6" class="hint">
          <div class="hint-chip">
            <span class="dot" />
            <span>先勾选SN与辅料数量，再确认出库</span>
          </div>
        </el-col>
      </el-row>
    </div>

    <div class="card">
      <el-table :data="records" v-loading="loading" style="width: 100%" @row-dblclick="goDetail">
        <el-table-column prop="draft_no" label="领料单号" width="230" />
        <el-table-column prop="request_no" label="申请单号" width="230">
          <template #default="{ row }">
            <span class="mono">{{ row.request_no || row.request_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="warehouse_name" label="仓库" width="160" />
        <el-table-column prop="requester_name" label="申请人" width="140" />
        <el-table-column prop="status" label="状态" width="140">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="submitted_at" label="提交时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.submitted_at || row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="goDetail(row)">详情</el-button>
            <el-button
              v-if="['pending_confirm', 'partially_confirmed'].includes(row.status)"
              type="success"
              link
              @click="goDetail(row)"
            >
              去确认
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="load"
          @size-change="resetAndLoad"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { stockApi } from '../../api/stock'

const router = useRouter()

const loading = ref(false)
const records = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const warehouses = ref([])

const filters = ref({
  status_filter: 'pending_confirm',
  warehouse_id: undefined,
  keyword: '',
})

const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

const statusText = (status) => {
  const map = {
    draft: '草稿',
    pending_confirm: '待确认',
    partially_confirmed: '部分确认',
    confirmed: '已确认',
    rejected: '已驳回',
    canceled: '已取消',
  }
  return map[status] || status || '-'
}

const statusTagType = (status) => {
  const map = {
    draft: 'info',
    pending_confirm: 'warning',
    partially_confirmed: 'warning',
    confirmed: 'success',
    rejected: 'danger',
    canceled: 'info',
  }
  return map[status] || ''
}

const extractError = (error) => {
  const detail = error?.response?.data?.detail
  if (!detail) return error?.message || '操作失败'
  if (typeof detail === 'string') return detail
  return detail?.message || '操作失败'
}

const loadWarehouses = async () => {
  try {
    const res = await stockApi.getWarehouses()
    warehouses.value = res?.warehouses || []
  } catch (error) {
    warehouses.value = []
  }
}

const load = async () => {
  try {
    loading.value = true
    const params = {
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
      status_filter: filters.value.status_filter || 'pending_confirm',
    }
    if (filters.value.warehouse_id) params.warehouse_id = filters.value.warehouse_id
    if (filters.value.keyword?.trim()) params.keyword = filters.value.keyword.trim()

    const res = await stockApi.listIssueDrafts(params)
    records.value = res?.records || []
    total.value = res?.total || 0
  } catch (error) {
    console.error('加载待确认出库单失败:', error)
    ElMessage.error(extractError(error))
  } finally {
    loading.value = false
  }
}

const resetAndLoad = async () => {
  page.value = 1
  await load()
}

const goDetail = (row) => {
  const id = row?.id
  if (!id) return
  router.push({ name: 'IssueDraftDetail', params: { id } })
}

onMounted(async () => {
  await loadWarehouses()
  await load()
})
</script>

<style scoped lang="scss">
.title-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 12px;
  letter-spacing: 0.2px;
}

.filters-card {
  position: relative;
  overflow: hidden;
}

.filters-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(900px 200px at 10% 0%, rgba(249, 115, 22, 0.14), transparent 60%),
    radial-gradient(800px 260px at 90% 30%, rgba(16, 185, 129, 0.10), transparent 55%);
  pointer-events: none;
}

.hint {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.hint-chip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: var(--shadow-sm);
  color: var(--text-secondary);
  font-size: 12px;
}

.hint-chip .dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: radial-gradient(circle at 30% 30%, #fff, #10b981);
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.16);
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  color: var(--text-secondary);
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>

