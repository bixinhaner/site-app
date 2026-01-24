<template>
  <div class="page-container">
    <div class="page-header">
      <h2>人员领用台账</h2>
      <div class="header-actions">
        <el-button type="primary" @click="exportAllOwnership" :loading="exportingAll" :disabled="usersLoading">
          <el-icon><Download /></el-icon>
          导出全部台账
        </el-button>
        <el-button @click="loadUsers" :loading="usersLoading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="card">
      <el-row :gutter="16" align="middle">
        <el-col :span="10">
          <el-input
            v-model="userFilters.keyword"
            placeholder="搜索用户名/姓名/邮箱"
            clearable
            @keyup.enter="applyUserSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="14" style="text-align: right">
          <el-button type="primary" @click="applyUserSearch" :loading="usersLoading">查询</el-button>
          <el-button @click="resetUserSearch" :disabled="usersLoading">重置</el-button>
        </el-col>
      </el-row>
    </div>

    <div class="card">
      <el-table :data="users" v-loading="usersLoading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="full_name" label="姓名" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.full_name || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="160">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)">{{ roleText(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '活跃' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="主设备" min-width="220">
          <template #default="{ row }">
            <div class="tag-group">
              <el-tag size="small" type="success">领 {{ row?.main_counts?.picked || 0 }}</el-tag>
              <el-tag size="small" type="info">装 {{ row?.main_counts?.installed || 0 }}</el-tag>
              <el-tag size="small" type="warning">待收 {{ row?.main_counts?.pending_receive || 0 }}</el-tag>
              <el-tag size="small">退 {{ row?.main_counts?.returned || 0 }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="辅料" min-width="190">
          <template #default="{ row }">
            <div class="tag-group">
              <el-tag size="small" type="success">领 {{ row?.aux_counts?.picked || 0 }}</el-tag>
              <el-tag size="small" type="warning">待收 {{ row?.aux_counts?.pending_receive || 0 }}</el-tag>
              <el-tag size="small">退 {{ row?.aux_counts?.returned || 0 }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="最近出库" width="180">
          <template #default="{ row }">
            {{ formatTime(row.last_out_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openOwnership(row)">查看台账</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <el-pagination
          v-model:current-page="userPagination.page"
          v-model:page-size="userPagination.size"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="userPagination.total"
          @current-change="onUserPageChange"
          @size-change="onUserSizeChange"
        />
      </div>
    </div>

    <!-- 归属明细抽屉 -->
    <el-drawer v-model="drawerVisible" size="82%" :with-header="false" destroy-on-close>
      <div class="drawer-header">
        <div>
          <h3>领用明细</h3>
          <div class="sub">
            用户：{{ selectedUser?.full_name || selectedUser?.username || '-' }}
            <span v-if="selectedUser?.username">（{{ selectedUser.username }}）</span>
          </div>
        </div>
        <div class="drawer-actions">
          <el-button size="small" type="primary" :loading="exporting" @click="exportCurrentTab">
            <el-icon><Download /></el-icon>
            导出当前 Tab
          </el-button>
          <el-button circle @click="drawerVisible = false">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </div>

      <div class="card summary-card" v-if="selectedUser">
        <el-row :gutter="12">
          <el-col :span="10">
            <div class="summary-block">
              <div class="summary-title">主设备</div>
              <div class="tag-group">
                <el-tag size="small" type="success">已领货 {{ selectedUser?.main_counts?.picked || 0 }}</el-tag>
                <el-tag size="small" type="info">已安装 {{ selectedUser?.main_counts?.installed || 0 }}</el-tag>
                <el-tag size="small" type="warning">退库待收货 {{ selectedUser?.main_counts?.pending_receive || 0 }}</el-tag>
                <el-tag size="small">已退库 {{ selectedUser?.main_counts?.returned || 0 }}</el-tag>
              </div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="summary-block">
              <div class="summary-title">辅料</div>
              <div class="tag-group">
                <el-tag size="small" type="success">已领货 {{ selectedUser?.aux_counts?.picked || 0 }}</el-tag>
                <el-tag size="small" type="warning">退库待收货 {{ selectedUser?.aux_counts?.pending_receive || 0 }}</el-tag>
                <el-tag size="small">已退库 {{ selectedUser?.aux_counts?.returned || 0 }}</el-tag>
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-block">
              <div class="summary-title">最近出库</div>
              <div class="summary-value">{{ formatTime(selectedUser?.last_out_time) }}</div>
            </div>
          </el-col>
        </el-row>
      </div>

      <div class="card">
        <div class="tabs-row">
          <el-tabs v-model="issuedFilters.item_type" @tab-change="onItemTypeChange">
            <el-tab-pane label="主设备" name="main" />
            <el-tab-pane label="辅料" name="aux" />
          </el-tabs>
        </div>

        <el-row :gutter="12" align="middle">
          <el-col :span="12">
            <el-tabs v-model="issuedFilters.status_group" type="card" @tab-change="onStatusChange">
              <el-tab-pane
                v-for="t in statusTabs"
                :key="t.key"
                :label="`${t.label} ${t.count}`"
                :name="t.key"
              />
            </el-tabs>
          </el-col>
          <el-col :span="12" style="text-align: right">
            <el-input
              v-model="issuedFilters.q"
              placeholder="搜索SN/物料名/单号"
              clearable
              style="width: 320px"
              @keyup.enter="applyIssuedFilters"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button type="primary" :loading="issuedLoading" @click="applyIssuedFilters">查询</el-button>
            <el-button :disabled="issuedLoading" @click="resetIssuedFilters">重置</el-button>
          </el-col>
        </el-row>
      </div>

      <div class="card">
        <el-table :data="issuedItems" v-loading="issuedLoading" stripe style="width: 100%">
          <!-- 主设备 -->
          <template v-if="issuedFilters.item_type === 'main'">
            <el-table-column label="SN" width="220">
              <template #default="{ row }">
                <span class="mono">{{ row.serial_number || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="条码" width="220">
              <template #default="{ row }">
                <span class="mono">{{ row.main_device_barcode || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="equipment_name" label="设备名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="equipment_code" label="设备编码" width="140" show-overflow-tooltip />
            <el-table-column label="退库单号" width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="mono">{{ row.return_document_number || '-' }}</span>
              </template>
            </el-table-column>
          </template>

          <!-- 辅料 -->
          <template v-else>
            <el-table-column prop="equipment_name" label="物料名称" min-width="220" show-overflow-tooltip />
            <el-table-column prop="equipment_code" label="物料编码" width="140" show-overflow-tooltip />
            <el-table-column label="数量" width="140">
              <template #default="{ row }">
                <span>{{ row.quantity || 0 }} {{ row.unit || '' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="退库进度" width="170">
              <template #default="{ row }">
                <span>待收 {{ row.return_pending_qty || 0 }} / 已收 {{ row.return_received_qty || 0 }}</span>
              </template>
            </el-table-column>
          </template>

          <el-table-column prop="out_document_number" label="出库单号" width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="mono">{{ row.out_document_number || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="operator_name" label="出库人" width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ row.operator_name || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="warehouse_name" label="仓库" width="140" show-overflow-tooltip />
          <el-table-column label="出库时间" width="180">
            <template #default="{ row }">
              {{ formatTime(row.operation_time) }}
            </template>
          </el-table-column>

          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status_group)">{{ statusText(row.status_group) }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column label="方式/来源" min-width="200">
            <template #default="{ row }">
              <div class="tag-group">
                <el-tag size="small" type="info">{{ row.method_tag || '-' }}</el-tag>
                <el-tag size="small">{{ row.source_tag || '-' }}</el-tag>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text @click="openStockOutDetail(row)">出库单详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-row">
          <el-pagination
            v-model:current-page="issuedPagination.page"
            v-model:page-size="issuedPagination.page_size"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            :total="issuedPagination.total"
            @current-change="onIssuedPageChange"
            @size-change="onIssuedSizeChange"
          />
        </div>
      </div>
    </el-drawer>

    <!-- 出库单详情 -->
    <el-dialog v-model="detailVisible" title="出库单详情" width="860px">
      <div v-loading="detailLoading">
        <div class="detail-meta" v-if="stockOutDetail">
          <div class="detail-line">
            <span class="label">单号</span>
            <span class="mono">{{ stockOutDetail.document_number || '-' }}</span>
          </div>
          <div class="detail-line">
            <span class="label">仓库</span>
            <span>{{ stockOutDetail.warehouse_name || '-' }}</span>
          </div>
          <div class="detail-line">
            <span class="label">时间</span>
            <span>{{ formatTime(stockOutDetail.operation_time) }}</span>
          </div>
          <div class="detail-line">
            <span class="label">方式/来源</span>
            <div class="tag-group">
              <el-tag size="small" type="info">{{ stockOutDetail.method_tag || '-' }}</el-tag>
              <el-tag size="small">{{ stockOutDetail.source_tag || '-' }}</el-tag>
            </div>
          </div>
          <div class="detail-line" v-if="stockOutDetail.notes">
            <span class="label">备注</span>
            <span>{{ stockOutDetail.notes }}</span>
          </div>
        </div>

        <el-table
          :data="stockOutDetail?.items || []"
          size="small"
          stripe
          style="width: 100%"
        >
          <el-table-column prop="equipment_code" label="编码" width="140" />
          <el-table-column prop="equipment_name" label="名称" min-width="200" show-overflow-tooltip />
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="row.is_main_device ? 'warning' : 'info'">
                {{ row.is_main_device ? '主设备' : '辅料' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="SN" width="220">
            <template #default="{ row }">
              <span class="mono">{{ row.serial_number || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="quantity" label="数量" width="90" />
          <el-table-column prop="unit" label="单位" width="80" />
        </el-table>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Close, Download, Refresh, Search } from '@element-plus/icons-vue'
import { stockApi } from '@/api/stock'

const usersLoading = ref(false)
const users = ref([])
const userPagination = reactive({
  page: 1,
  size: 20,
  total: 0,
})
const userFilters = reactive({
  keyword: '',
})

const roleText = (role) => {
  const map = {
    admin: '管理员',
    manager: '项目经理',
    warehouse_manager: '仓库管理员',
    inspector: '现场工程师',
    surveyor: '勘察人员',
    planner: '规划人员',
    reviewer: '审核人员',
    user: '普通用户',
  }
  return map[String(role || '').trim()] || String(role || '-')
}

const roleTagType = (role) => {
  const map = {
    admin: 'danger',
    manager: 'warning',
    warehouse_manager: 'success',
    inspector: 'info',
    surveyor: '',
    planner: '',
    reviewer: 'info',
    user: '',
  }
  return map[String(role || '').trim()] || ''
}

const loadUsers = async () => {
  usersLoading.value = true
  try {
    const params = {
      skip: (userPagination.page - 1) * userPagination.size,
      limit: userPagination.size,
    }
    const kw = String(userFilters.keyword || '').trim()
    if (kw) params.keyword = kw

    const res = await stockApi.getUserOwnershipSummary(params)
    users.value = Array.isArray(res?.users) ? res.users : []
    userPagination.total = Number(res?.total || 0)
  } catch (error) {
    console.error('加载用户列表失败:', error)
    ElMessage.error(error?.response?.data?.detail || error?.message || '加载用户列表失败')
  } finally {
    usersLoading.value = false
  }
}

const applyUserSearch = () => {
  userPagination.page = 1
  loadUsers()
}

const resetUserSearch = () => {
  userFilters.keyword = ''
  userPagination.page = 1
  loadUsers()
}

const onUserPageChange = (page) => {
  userPagination.page = Number(page || 1)
  loadUsers()
}

const onUserSizeChange = (size) => {
  userPagination.size = Number(size || 20)
  userPagination.page = 1
  loadUsers()
}

// ===== 归属明细 =====
const drawerVisible = ref(false)
const selectedUser = ref(null)

const issuedLoading = ref(false)
const issuedItems = ref([])
const groupCounts = ref({})

const issuedFilters = reactive({
  item_type: 'main',
  status_group: 'picked',
  q: '',
})

const issuedPagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const statusText = (v) => {
  const map = {
    picked: '已领货',
    installed: '已安装',
    pending_receive: '退库待收货',
    returned: '已退库',
  }
  return map[String(v || '').trim()] || '未知'
}

const statusTagType = (v) => {
  const map = {
    picked: 'success',
    installed: 'info',
    pending_receive: 'warning',
    returned: '',
  }
  return map[String(v || '').trim()] || 'info'
}

const statusTabs = computed(() => {
  const base = [
    { key: 'picked', label: '已领货' },
    { key: 'installed', label: '已安装' },
    { key: 'pending_receive', label: '退库待收货' },
    { key: 'returned', label: '已退库' },
  ]
  const tabs = issuedFilters.item_type === 'aux'
    ? base.filter(t => t.key !== 'installed')
    : base
  return tabs.map(t => ({
    ...t,
    count: Number(groupCounts.value?.[t.key] || 0),
  }))
})

const normalizeStatusForItemType = () => {
  if (issuedFilters.item_type === 'aux' && issuedFilters.status_group === 'installed') {
    issuedFilters.status_group = 'picked'
  }
}

const loadIssuedItems = async () => {
  if (!selectedUser.value?.id) return
  normalizeStatusForItemType()

  issuedLoading.value = true
  try {
    const params = {
      item_type: issuedFilters.item_type,
      status_group: issuedFilters.status_group,
      page: issuedPagination.page,
      page_size: issuedPagination.page_size,
    }
    const q = String(issuedFilters.q || '').trim()
    if (q) params.q = q

    const data = await stockApi.getUserIssuedItems(selectedUser.value.id, params)
    issuedItems.value = Array.isArray(data?.items) ? data.items : []
    issuedPagination.total = Number(data?.total || 0)
    groupCounts.value = data?.group_counts || {}
  } catch (error) {
    console.error('加载归属明细失败:', error)
    ElMessage.error(error?.response?.data?.detail || error?.message || '加载归属明细失败')
  } finally {
    issuedLoading.value = false
  }
}

const openOwnership = async (user) => {
  selectedUser.value = user
  drawerVisible.value = true
  issuedFilters.item_type = 'main'
  issuedFilters.status_group = 'picked'
  issuedFilters.q = ''
  issuedPagination.page = 1
  issuedPagination.page_size = 20
  groupCounts.value = {}
  issuedItems.value = []
  await loadIssuedItems()
}

const onItemTypeChange = () => {
  issuedPagination.page = 1
  normalizeStatusForItemType()
  loadIssuedItems()
}

const onStatusChange = () => {
  issuedPagination.page = 1
  normalizeStatusForItemType()
  loadIssuedItems()
}

const applyIssuedFilters = () => {
  issuedPagination.page = 1
  loadIssuedItems()
}

const resetIssuedFilters = () => {
  issuedFilters.q = ''
  issuedPagination.page = 1
  loadIssuedItems()
}

const onIssuedPageChange = (page) => {
  issuedPagination.page = Number(page || 1)
  loadIssuedItems()
}

const onIssuedSizeChange = (size) => {
  issuedPagination.page_size = Number(size || 20)
  issuedPagination.page = 1
  loadIssuedItems()
}

const formatTime = (value) => {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString()
}

// ===== 出库单详情 =====
const detailVisible = ref(false)
const detailLoading = ref(false)
const stockOutDetail = ref(null)

const openStockOutDetail = async (row) => {
  const id = row?.out_transaction_id
  if (!id) return
  detailVisible.value = true
  detailLoading.value = true
  stockOutDetail.value = null
  try {
    const data = await stockApi.getStockOutDetail(id)
    stockOutDetail.value = data || null
  } catch (error) {
    console.error('加载出库单详情失败:', error)
    ElMessage.error(error?.response?.data?.detail || error?.message || '加载出库单详情失败')
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

const formatExportDate = () => {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`
}

const downloadBlob = (blob, fileName) => {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

const extractErrorDetail = async (error) => {
  const data = error?.response?.data
  if (!data) return error?.message || '网络错误'
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      try {
        const json = JSON.parse(text)
        return json?.detail || text || error?.message || '网络错误'
      } catch {
        return text || error?.message || '网络错误'
      }
    } catch {
      return error?.message || '网络错误'
    }
  }
  return data?.detail || error?.message || '网络错误'
}

const exporting = ref(false)
const exportCurrentTab = async () => {
  if (!selectedUser.value?.id) return
  try {
    exporting.value = true
    const params = {
      item_type: issuedFilters.item_type,
      status_group: issuedFilters.status_group,
    }
    const q = String(issuedFilters.q || '').trim()
    if (q) params.q = q

    const blob = await stockApi.exportUserIssuedItems(selectedUser.value.id, params)
    const userName = selectedUser.value.full_name || selectedUser.value.username || `user_${selectedUser.value.id}`
    const tabName = issuedFilters.item_type === 'main' ? '主设备' : '辅料'
    const fileName = `${userName}_${tabName}_领用明细_${formatExportDate()}.xlsx`
    downloadBlob(blob, fileName)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error(e)
    const msg = await extractErrorDetail(e)
    ElMessage.error('导出失败: ' + msg)
  } finally {
    exporting.value = false
  }
}

const exportingAll = ref(false)
const exportAllOwnership = async () => {
  try {
    exportingAll.value = true
    const params = {}
    const kw = String(userFilters.keyword || '').trim()
    if (kw) params.keyword = kw

    const blob = await stockApi.exportUserOwnershipAll(params)
    const fileName = `人员领用台账_全部物料_${formatExportDate()}.xlsx`
    downloadBlob(blob, fileName)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error(e)
    const msg = await extractErrorDetail(e)
    ElMessage.error('导出失败: ' + msg)
  } finally {
    exportingAll.value = false
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.mono {
  font-family: 'Courier New', monospace;
}

.pagination-row {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 8px 8px;
}

.drawer-header h3 {
  margin: 0;
}

.drawer-header .sub {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.drawer-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.tabs-row :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.tag-group {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.summary-card {
  margin-top: 10px;
}

.summary-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-title {
  color: #64748b;
  font-size: 12px;
}

.summary-value {
  font-size: 14px;
}

.detail-meta {
  margin-bottom: 12px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
}

.detail-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.detail-line:last-child {
  margin-bottom: 0;
}

.detail-line .label {
  width: 72px;
  color: #64748b;
}
</style>
