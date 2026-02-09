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
            <el-option label="待收货（含部分）" value="pending_receive" />
            <el-option label="部分收货" value="partially_received" />
            <el-option label="已收货" value="received" />
            <el-option label="已拒收" value="rejected" />
            <el-option label="已取消" value="canceled" />
            <el-option label="全部" value="all" />
          </el-select>
        </el-col>

        <el-col :span="6">
          <el-input
            v-model="keyword"
            placeholder="搜索：退库单号 / 出库单号 / SN"
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
        <el-table-column prop="out_document_number" label="关联出库单" min-width="220" />
        <el-table-column prop="warehouse_name" label="退入仓库" width="160" />
        <el-table-column prop="operator_name" label="申请人" width="140" />
        <el-table-column label="待收货" width="180">
          <template #default="{ row }">
            <span>主 {{ mainPending(row) }} · 辅 {{ auxPending(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="申请时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at || row.operation_time) }}
          </template>
        </el-table-column>
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
              :disabled="!canReceiveRow(row)"
            >
              收货确认
            </el-button>
            <el-button
              size="small"
              type="danger"
              plain
              @click="openReject(row)"
              :disabled="!canRejectRow(row)"
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
    <el-dialog v-model="receiveDialogVisible" title="收货确认（可部分）" width="880px" @closed="focusSnInput">
      <div v-loading="receiveLoading">
        <div v-if="currentRecord">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="退库单号">{{ currentRecord.document_number }}</el-descriptions-item>
            <el-descriptions-item label="退入仓库">{{ currentRecord.warehouse_name }}</el-descriptions-item>
            <el-descriptions-item label="申请人">{{ currentRecord.operator_name }}</el-descriptions-item>
            <el-descriptions-item label="关联出库单">{{ currentRecord.out_document_number || '-' }}</el-descriptions-item>
            <el-descriptions-item label="出库仓库">{{ currentRecord.out_warehouse_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ statusText(currentRecord.status) }}</el-descriptions-item>
          </el-descriptions>

          <el-divider content-position="left">本次收货概览</el-divider>
          <div class="chips">
            <div class="chip">
              <div class="k">待收 SN</div>
              <div class="v">{{ pendingMainItems.length }}</div>
            </div>
            <div class="chip">
              <div class="k">已选 SN</div>
              <div class="v">{{ selectedMainSns.size }}</div>
            </div>
            <div class="chip">
              <div class="k">辅料本次收货</div>
              <div class="v">{{ auxReceiveTotal }}</div>
            </div>
            <div class="chip accent">
              <div class="k">本次总收货</div>
              <div class="v">{{ totalReceive }}</div>
            </div>
          </div>

          <el-divider content-position="left">主设备（SN）</el-divider>
          <div class="main-sn-actions">
            <el-button
              size="small"
              @click="selectAllReceivableMainSns"
              :disabled="!canReceiveCurrent || receivableMainSns.length === 0"
            >
              一键勾选全部可收货 SN
            </el-button>
            <el-button
              size="small"
              @click="clearSelectedMain"
              :disabled="selectedMainSns.size === 0"
            >
              清空已选 SN
            </el-button>
          </div>
          <el-table :data="mainItems" size="small" border max-height="240px">
            <el-table-column label="" width="56">
              <template #default="{ row }">
                <el-checkbox
                  :model-value="selectedMainSns.has(String(row.serial_number || ''))"
                  :disabled="!canSelectMain(row)"
                  @change="(v) => toggleMain(row.serial_number, v)"
                />
              </template>
            </el-table-column>
            <el-table-column prop="serial_number" label="SN" min-width="180" />
            <el-table-column prop="equipment_name" label="物料" min-width="220" />
            <el-table-column prop="pending_quantity" label="待收" width="100" />
            <el-table-column prop="received_quantity" label="已收" width="100" />
          </el-table>

          <el-divider content-position="left">辅料</el-divider>
          <el-table :data="auxRows" size="small" border max-height="260px">
            <el-table-column prop="equipment_name" label="物料" min-width="240" />
            <el-table-column prop="pending_quantity" label="待收" width="120" />
            <el-table-column label="本次收货" width="200">
              <template #default="{ row }">
                <el-input-number
                  v-model="row._receive_qty"
                  :min="0"
                  :max="row.pending_quantity"
                  controls-position="right"
                  :disabled="row.pending_quantity <= 0 || !canReceiveCurrent"
                />
              </template>
            </el-table-column>
            <el-table-column prop="unit" label="单位" width="90" />
          </el-table>

          <el-form label-width="90px" class="dialog-form">
            <el-form-item label="备注">
              <el-input v-model="receiveNotes" type="textarea" :rows="2" placeholder="可选" />
            </el-form-item>
          </el-form>
        </div>
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
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { stockApi } from '@/api/stock'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(false)
const receiveLoading = ref(false)
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

const selectedMainSns = reactive(new Set())
const auxRows = ref([])
const receiveNotes = ref('')

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
    partially_received: '部分收货',
    received: '已收货',
    rejected: '已拒收',
    canceled: '已取消',
  }
  return map[s] || s || '-'
}

const statusTagType = (s) => {
  if (s === 'pending_receive') return 'warning'
  if (s === 'partially_received') return 'warning'
  if (s === 'received') return 'success'
  if (s === 'rejected') return 'danger'
  if (s === 'canceled') return 'info'
  return 'info'
}

const mainPending = (row) => {
  const items = Array.isArray(row?.items) ? row.items : []
  return items.filter((it) => it?.is_main_device).reduce((sum, it) => sum + Number(it?.pending_quantity || 0), 0)
}

const auxPending = (row) => {
  const items = Array.isArray(row?.items) ? row.items : []
  return items.filter((it) => !it?.is_main_device).reduce((sum, it) => sum + Number(it?.pending_quantity || 0), 0)
}

const canReceiveRow = (row) => ['pending_receive', 'partially_received'].includes(String(row?.status || ''))
const canRejectRow = (row) => String(row?.status || '') === 'pending_receive'

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

    const res = await stockApi.listReturnsWorkbench(params)
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

    const res = await stockApi.listReturnsWorkbench(params)
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

const clearSelectedMain = () => {
  selectedMainSns.forEach((v) => selectedMainSns.delete(v))
}

const normalizeAuxRows = (record) => {
  const items = Array.isArray(record?.items) ? record.items : []
  auxRows.value = items
    .filter((it) => !it?.is_main_device)
    .map((it) => ({
      ...it,
      _receive_qty: 0,
    }))
}

const openReceive = async (row, scannedSn = '') => {
  receiveDialogVisible.value = true
  currentRecord.value = null
  receiveNotes.value = ''
  clearSelectedMain()
  auxRows.value = []

  try {
    receiveLoading.value = true
    const res = await stockApi.getReturnDetail(row.id)
    currentRecord.value = res.record || row
  } catch (error) {
    console.error('加载退库单详情失败:', error)
    ElMessage.error(error?.response?.data?.detail || '加载退库单详情失败')
    currentRecord.value = row
  } finally {
    receiveLoading.value = false
    normalizeAuxRows(currentRecord.value)
    if (scannedSn) {
      const hit = (currentRecord.value?.items || []).find((it) => it?.is_main_device && String(it.serial_number || '') === scannedSn)
      if (hit && Number(hit.pending_quantity || 0) > 0) {
        selectedMainSns.add(scannedSn)
      }
    }
    await nextTick()
  }
}

const openReject = async (row) => {
  rejectForm.value = { reason: '' }
  try {
    const res = await stockApi.getReturnDetail(row.id)
    currentRecord.value = res.record || row
  } catch (error) {
    currentRecord.value = row
  }
  rejectDialogVisible.value = true
}

const canReceiveCurrent = computed(() => canReceiveRow(currentRecord.value))

const mainItems = computed(() => {
  const items = Array.isArray(currentRecord.value?.items) ? currentRecord.value.items : []
  return items.filter((it) => it?.is_main_device)
})

const pendingMainItems = computed(() => mainItems.value.filter((it) => Number(it?.pending_quantity || 0) > 0))
const receivableMainSns = computed(() => {
  return mainItems.value
    .filter((it) => canSelectMain(it))
    .map((it) => String(it?.serial_number || '').trim())
    .filter(Boolean)
})

const auxReceiveTotal = computed(() => {
  return auxRows.value.reduce((sum, it) => sum + Number(it?._receive_qty || 0), 0)
})

const totalReceive = computed(() => selectedMainSns.size + auxReceiveTotal.value)

const canSelectMain = (row) => {
  if (!canReceiveCurrent.value) return false
  const sn = String(row?.serial_number || '')
  if (!sn) return false
  return Number(row?.pending_quantity || 0) > 0
}

const toggleMain = (sn, checked) => {
  const snv = String(sn || '').trim()
  if (!snv) return
  if (checked) selectedMainSns.add(snv)
  else selectedMainSns.delete(snv)
}

const selectAllReceivableMainSns = () => {
  receivableMainSns.value.forEach((sn) => selectedMainSns.add(sn))
}

const submitReceive = async () => {
  if (!currentRecord.value?.id) return
  if (!canReceiveCurrent.value) {
    ElMessage.warning('当前状态不可收货确认')
    return
  }

  const main_sns = Array.from(selectedMainSns)
  const aux_items = auxRows.value
    .filter((r) => Number(r?._receive_qty || 0) > 0)
    .map((r) => ({
      equipment_id: r.equipment_id,
      quantity: Number(r._receive_qty || 0),
    }))

  if (main_sns.length === 0 && aux_items.length === 0) {
    ElMessage.warning('请至少选择1个SN或填写辅料收货数量')
    return
  }

  try {
    submitting.value = true
    await stockApi.receiveReturnV2(currentRecord.value.id, {
      main_sns,
      aux_items,
      receive_notes: (receiveNotes.value || '').trim(),
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
    await stockApi.rejectReturnV2(currentRecord.value.id, {
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

.chips {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.chip {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.72);
}

.chip .k {
  font-size: 12px;
  color: var(--text-secondary);
}

.chip .v {
  margin-top: 6px;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.chip.accent {
  border-color: rgba(59, 130, 246, 0.34);
  background: rgba(59, 130, 246, 0.08);
}

.main-sn-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0 12px;
}

.dialog-form {
  margin-top: 16px;
}
</style>
