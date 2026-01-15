<template>
  <div class="page-container">
    <div class="page-header">
      <h2>领料记录</h2>
      <el-button @click="loadPickups" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <div class="card">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-select
            v-model="filters.pickup_group"
            placeholder="状态分组"
            clearable
            @change="applyFilters"
          >
            <el-option label="已领货" value="picked" />
            <el-option label="退库待收货" value="pending_receive" />
            <el-option label="已安装" value="installed" />
            <el-option label="已退库" value="returned" />
          </el-select>
        </el-col>
        <el-col :span="10">
          <el-input
            v-model="filters.q"
            placeholder="搜索SN/条码/套装名"
            clearable
            @keyup.enter="applyFilters"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="8" style="text-align: right">
          <el-button type="primary" @click="applyFilters">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>

      <div class="counts-row" v-if="Object.keys(groupCounts).length">
        <el-tag size="small" type="success">已领货 {{ groupCounts.picked || 0 }}</el-tag>
        <el-tag size="small" type="warning">退库待收货 {{ groupCounts.pending_receive || 0 }}</el-tag>
        <el-tag size="small" type="info">已安装 {{ groupCounts.installed || 0 }}</el-tag>
        <el-tag size="small">已退库 {{ groupCounts.returned || 0 }}</el-tag>
      </div>
    </div>

    <div class="card">
      <el-table :data="records" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="serial_number" label="SN" width="210">
          <template #default="{ row }">
            <span class="mono">{{ row.serial_number || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="main_device_barcode" label="条码" width="220" show-overflow-tooltip />
        <el-table-column prop="package_name" label="套装" min-width="180" show-overflow-tooltip />
        <el-table-column label="MAC1" width="170">
          <template #default="{ row }">
            <span class="mono">{{ formatMac(row.mac_address_1) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="MAC2" width="170">
          <template #default="{ row }">
            <span class="mono">{{ formatMac(row.mac_address_2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="MAC3" width="170">
          <template #default="{ row }">
            <span class="mono">{{ formatMac(row.mac_address_3) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="MAC4" width="170">
          <template #default="{ row }">
            <span class="mono">{{ formatMac(row.mac_address_4) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="领料时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.pickup_time) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="pickupTagType(row.pickup_group)">
              {{ pickupGroupText(row.pickup_group) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="pagination.total"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { stockApi } from '../../api/stock'

const loading = ref(false)
const records = ref([])
const groupCounts = ref({})

const filters = reactive({
  pickup_group: '',
  q: '',
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const pickupGroupText = (group) => {
  const map = {
    picked: '已领货',
    pending_receive: '退库待收货',
    installed: '已安装',
    returned: '已退库',
  }
  return map[group] || '未知'
}

const pickupTagType = (group) => {
  const map = {
    picked: 'success',
    pending_receive: 'warning',
    installed: 'info',
    returned: '',
  }
  return map[group] || 'info'
}

const formatTime = (value) => {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString()
}

const formatMac = (mac) => {
  const raw = String(mac || '').trim()
  if (!raw) return '-'
  const clean = raw.replace(/[:\\-\\.]/g, '').toUpperCase()
  if (clean.length !== 12) return raw.toUpperCase()
  return clean.replace(/(.{2})/g, '$1:').slice(0, -1)
}

const buildParams = () => {
  const params = {
    page: pagination.page,
    page_size: pagination.page_size,
  }
  const group = String(filters.pickup_group || '').trim()
  const q = String(filters.q || '').trim()
  if (group) params.pickup_group = group
  if (q) params.q = q
  return params
}

const loadPickups = async () => {
  loading.value = true
  try {
    const data = await stockApi.getMyPickups(buildParams())
    records.value = data?.pickup_records || []
    pagination.total = Number(data?.total || 0)
    groupCounts.value = data?.group_counts || {}
  } catch (error) {
    console.error('加载领料记录失败:', error)
    ElMessage.error(error?.response?.data?.detail || error?.message || '加载领料记录失败')
  } finally {
    loading.value = false
  }
}

const applyFilters = () => {
  pagination.page = 1
  loadPickups()
}

const resetFilters = () => {
  filters.pickup_group = ''
  filters.q = ''
  pagination.page = 1
  loadPickups()
}

const onPageChange = (page) => {
  pagination.page = Number(page || 1)
  loadPickups()
}

const onPageSizeChange = (size) => {
  pagination.page_size = Number(size || 20)
  pagination.page = 1
  loadPickups()
}

onMounted(() => {
  loadPickups()
})
</script>

<style scoped>
.mono {
  font-family: 'Courier New', monospace;
}

.counts-row {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.pagination-row {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
