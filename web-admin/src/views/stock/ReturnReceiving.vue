<template>
  <div class="page-container">
    <div class="page-header">
      <h2>退库收货</h2>
      <div class="header-actions">
        <el-button @click="loadData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-card class="toolbar-card">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-input
            ref="snInputRef"
            v-model="snInput"
            placeholder="扫码枪输入SN后回车：快速定位待收货退库单"
            clearable
            @keyup.enter="handleQuickLookup"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
            <template #append>
              <el-button type="primary" @click="handleQuickLookup">查找</el-button>
            </template>
          </el-input>
        </el-col>

        <el-col :span="6">
          <el-select
            v-model="selectedWarehouseIds"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="筛选仓库（默认我的仓库）"
            style="width: 100%"
            @change="resetAndLoad"
          >
            <el-option
              v-for="w in selectableWarehouses"
              :key="w.id"
              :label="w.warehouse_name"
              :value="w.id"
            />
          </el-select>
        </el-col>

        <el-col :span="4">
          <el-select v-model="statusFilter" placeholder="状态" style="width: 100%" @change="resetAndLoad">
            <el-option label="待收货" value="pending_receive" />
            <el-option label="已收货" value="received" />
            <el-option label="已拒收" value="rejected" />
            <el-option label="已取消" value="canceled" />
            <el-option label="全部" value="all" />
          </el-select>
        </el-col>

        <el-col :span="6">
          <el-input
            v-model="keyword"
            placeholder="搜索：退库单号 / 申请人 / SN"
            clearable
            @keyup.enter="resetAndLoad"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
            <template #append>
              <el-button type="primary" @click="resetAndLoad">查询</el-button>
            </template>
          </el-input>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="table-card">
      <div class="table-meta">
        <el-tag type="info">共 {{ total }} 条</el-tag>
      </div>

      <el-table :data="records" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="document_number" label="退库单号" min-width="220" />
        <el-table-column prop="scan_barcode" label="主设备SN" min-width="180" />
        <el-table-column prop="warehouse_name" label="退入仓库" width="160" />
        <el-table-column prop="operator_name" label="申请人" width="140" />
        <el-table-column label="申请时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at || row.operation_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="out_document_number" label="关联出库单" min-width="220" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="success"
              @click="openReceive(row)"
              :disabled="row.status !== 'pending_receive'"
            >
              收货确认
            </el-button>
            <el-button
              size="small"
              type="danger"
              plain
              @click="openReject(row)"
              :disabled="row.status !== 'pending_receive'"
            >
              拒收
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @change="loadData"
        />
      </div>
    </el-card>

    <!-- 收货确认 -->
    <el-dialog v-model="receiveDialogVisible" title="收货确认" width="680px" @closed="focusSnInput">
      <div v-if="currentRecord">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="退库单号">{{ currentRecord.document_number }}</el-descriptions-item>
          <el-descriptions-item label="退入仓库">{{ currentRecord.warehouse_name }}</el-descriptions-item>
          <el-descriptions-item label="主设备SN">{{ currentRecord.scan_barcode }}</el-descriptions-item>
          <el-descriptions-item label="申请人">{{ currentRecord.operator_name }}</el-descriptions-item>
          <el-descriptions-item label="关联出库单">{{ currentRecord.out_document_number || '-' }}</el-descriptions-item>
          <el-descriptions-item label="出库仓库">{{ currentRecord.out_warehouse_name || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">退库明细（整单）</el-divider>
        <el-table :data="currentRecord.items || []" size="small" border max-height="260px">
          <el-table-column prop="equipment_name" label="物料" min-width="240" />
          <el-table-column prop="equipment_code" label="编码" width="140" />
          <el-table-column prop="quantity" label="数量" width="100" />
          <el-table-column prop="unit" label="单位" width="80" />
        </el-table>

        <el-form label-width="100px" class="dialog-form">
          <el-form-item label="SN核验" required>
            <el-input
              v-model="receiveForm.sn_input"
              placeholder="请再次输入/扫码SN进行核验"
              @keyup.enter="submitReceive"
            />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="receiveForm.receive_notes" type="textarea" :rows="2" placeholder="可选" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="receiveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitReceive">确认收货</el-button>
      </template>
    </el-dialog>

    <!-- 拒收 -->
    <el-dialog v-model="rejectDialogVisible" title="拒收退库" width="520px" @closed="focusSnInput">
      <el-form label-width="100px">
        <el-form-item label="拒收原因" required>
          <el-input v-model="rejectForm.reason" type="textarea" :rows="3" placeholder="请填写拒收原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="submitReject">提交拒收</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { stockApi } from '@/api/stock'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(false)
const submitting = ref(false)

const snInputRef = ref(null)
const snInput = ref('')
const keyword = ref('')
const statusFilter = ref('pending_receive')

const warehouses = ref([])
const selectableWarehouses = computed(() => {
  const list = warehouses.value || []
  const role = userStore.user?.role
  if (['admin', 'manager'].includes(role)) return list
  const uid = userStore.user?.id
  return list.filter((w) => w.manager_id === uid)
})

const selectedWarehouseIds = ref([])

const records = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const receiveDialogVisible = ref(false)
const rejectDialogVisible = ref(false)
const currentRecord = ref(null)

const receiveForm = ref({ sn_input: '', receive_notes: '' })
const rejectForm = ref({ reason: '' })

const formatDateTime = (iso) => {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const statusText = (s) => {
  const map = {
    pending_receive: '待收货',
    received: '已收货',
    rejected: '已拒收',
    canceled: '已取消',
  }
  return map[s] || s || '-'
}

const statusTagType = (s) => {
  if (s === 'pending_receive') return 'warning'
  if (s === 'received') return 'success'
  if (s === 'rejected') return 'danger'
  if (s === 'canceled') return 'info'
  return 'info'
}

const focusSnInput = async () => {
  await nextTick()
  snInputRef.value?.focus?.()
}

const loadWarehouses = async () => {
  try {
    const res = await stockApi.getWarehouses()
    warehouses.value = res.warehouses || []
  } catch (error) {
    console.error('加载仓库列表失败:', error)
  }
}

const resetAndLoad = async () => {
  currentPage.value = 1
  await loadData()
}

const loadData = async () => {
  try {
    loading.value = true
    const params = {
      status_filter: statusFilter.value,
      keyword: keyword.value?.trim() || undefined,
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
    }
    if (selectedWarehouseIds.value?.length > 0) {
      params.warehouse_ids = selectedWarehouseIds.value.join(',')
    }

    const res = await stockApi.getReturnRequests(params)
    records.value = res.records || []
    total.value = res.total || 0
  } catch (error) {
    console.error('加载退库收货列表失败:', error)
    ElMessage.error(error?.response?.data?.detail || '加载退库收货列表失败')
  } finally {
    loading.value = false
    await focusSnInput()
  }
}

const handleQuickLookup = async () => {
  const sn = snInput.value?.trim()
  if (!sn) {
    ElMessage.warning('请先输入SN')
    return
  }

  try {
    loading.value = true
    const params = {
      status_filter: 'pending_receive',
      sn,
      skip: 0,
      limit: 5,
    }
    if (selectedWarehouseIds.value?.length > 0) {
      params.warehouse_ids = selectedWarehouseIds.value.join(',')
    }

    const res = await stockApi.getReturnRequests(params)
    const list = res.records || []
    if (list.length === 0) {
      ElMessage.warning('未找到该SN对应的待收货退库单')
      return
    }
    if (list.length > 1) {
      ElMessage.warning('找到多条记录，请在列表中确认后操作')
      records.value = list
      total.value = res.total || list.length
      currentPage.value = 1
      return
    }
    openReceive(list[0], sn)
  } catch (error) {
    console.error('SN快速查找失败:', error)
    ElMessage.error(error?.response?.data?.detail || 'SN快速查找失败')
  } finally {
    loading.value = false
  }
}

const openReceive = async (row, scannedSn = '') => {
  currentRecord.value = row
  receiveForm.value = { sn_input: scannedSn || row.scan_barcode || '', receive_notes: '' }
  receiveDialogVisible.value = true
  await nextTick()
}

const openReject = (row) => {
  currentRecord.value = row
  rejectForm.value = { reason: '' }
  rejectDialogVisible.value = true
}

const submitReceive = async () => {
  if (!currentRecord.value?.id) return
  if (!receiveForm.value.sn_input?.trim()) {
    ElMessage.warning('请填写SN核验')
    return
  }

  try {
    submitting.value = true
    await stockApi.receiveReturn({
      return_transaction_id: currentRecord.value.id,
      sn_input: receiveForm.value.sn_input.trim(),
      receive_notes: receiveForm.value.receive_notes?.trim() || '',
    })
    ElMessage.success('收货确认成功')
    receiveDialogVisible.value = false
    snInput.value = ''
    await loadData()
  } catch (error) {
    console.error('收货确认失败:', error)
    ElMessage.error(error?.response?.data?.detail || '收货确认失败')
  } finally {
    submitting.value = false
  }
}

const submitReject = async () => {
  if (!currentRecord.value?.id) return
  if (!rejectForm.value.reason?.trim()) {
    ElMessage.warning('请填写拒收原因')
    return
  }

  try {
    submitting.value = true
    await stockApi.rejectReturn({
      return_transaction_id: currentRecord.value.id,
      reason: rejectForm.value.reason.trim(),
    })
    ElMessage.success('已拒收退库申请')
    rejectDialogVisible.value = false
    snInput.value = ''
    await loadData()
  } catch (error) {
    console.error('拒收失败:', error)
    ElMessage.error(error?.response?.data?.detail || '拒收失败')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await loadWarehouses()
  const role = userStore.user?.role
  if (!['admin', 'manager'].includes(role)) {
    selectedWarehouseIds.value = (selectableWarehouses.value || []).map((w) => w.id)
    if (selectedWarehouseIds.value.length === 0) {
      ElMessage.warning('当前账号未绑定可管理仓库，无法处理退库收货')
    }
  }
  await loadData()
})
</script>

<style scoped lang="scss">
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.toolbar-card {
  margin-bottom: 16px;
}

.table-meta {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.dialog-form {
  margin-top: 16px;
}
</style>
