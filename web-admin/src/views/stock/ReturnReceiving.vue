<template>
  <div class="page-container">
    <div class="page-header">
      <h2>退库收货（批次维度）</h2>
      <div class="header-actions">
        <el-button @click="loadData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-card class="toolbar-card">
      <el-row :gutter="16">
        <el-col :xs="24" :sm="12" :md="8">
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

        <el-col :xs="24" :sm="12" :md="6">
          <el-select v-model="statusFilter" placeholder="状态" style="width: 100%" @change="resetAndLoad">
            <el-option label="待收货（含部分）" value="pending_receive" />
            <el-option label="部分收货" value="partially_received" />
            <el-option label="已收货" value="received" />
            <el-option label="已拒收" value="rejected" />
            <el-option label="已取消" value="canceled" />
            <el-option label="全部" value="all" />
          </el-select>
        </el-col>

        <el-col :xs="24" :sm="24" :md="10">
          <el-input
            v-model="keyword"
            placeholder="搜索：批次号 / 退库单号 / 出库单号 / 申请人"
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

    <el-card class="table-card" v-loading="loading">
      <div class="table-meta">
        <el-tag type="info">批次 {{ total }} 条</el-tag>
      </div>

      <el-empty v-if="!loading && batchRecords.length === 0" description="暂无退库批次" />

      <div v-else class="batch-list">
        <div v-for="batch in batchRecords" :key="batch.batch_id" class="batch-card">
          <div class="batch-head">
            <div class="batch-main">
              <div class="batch-id">{{ batch.batch_id }}</div>
              <div class="batch-meta">
                <span>发起：{{ formatDateTime(batch.created_at) }}</span>
                <span>最近更新：{{ formatDateTime(batch.latest_created_at) }}</span>
              </div>
            </div>
            <el-tag :type="statusTagType(batch.status)">{{ statusText(batch.status) }}</el-tag>
          </div>

          <div class="batch-stats">
            <div class="stat-item">
              <div class="k">退库单</div>
              <div class="v">{{ batch.document_count }}</div>
            </div>
            <div class="stat-item">
              <div class="k">主设备</div>
              <div class="v">{{ batch.main_device_count }}</div>
            </div>
            <div class="stat-item">
              <div class="k">辅料数量</div>
              <div class="v">{{ batch.aux_total_quantity }}</div>
            </div>
            <div class="stat-item">
              <div class="k">待收货</div>
              <div class="v">{{ batch.pending_total_quantity }}</div>
            </div>
          </div>

          <div
            v-if="showBatchRejectReason(batch)"
            class="batch-reject"
            @click="openBatchRejectReason(batch)"
          >
            <span class="reject-title">驳回原因</span>
            <span class="reject-content">{{ rejectReasonPreview(batch) }}</span>
            <span class="reject-action">查看详情</span>
          </div>

          <div class="doc-box">
            <div class="doc-box-head">
              <span class="doc-title">批次内单据</span>
              <el-button
                v-if="batch.documents.length > MAX_DOC_PREVIEW"
                link
                type="primary"
                @click="toggleDocs(batch)"
              >
                {{ isDocsExpanded(batch) ? '收起单据' : '展开单据' }}
              </el-button>
            </div>

            <el-table :data="visibleDocs(batch)" size="small" border>
              <el-table-column prop="document_number" label="退库单号" min-width="190" />
              <el-table-column prop="out_document_number" label="关联出库单" min-width="190" />
              <el-table-column prop="warehouse_name" label="退入仓库" width="140" />
              <el-table-column prop="operator_name" label="申请人" width="120" />
              <el-table-column label="待收货" width="100">
                <template #default="{ row }">{{ row.pending_total_quantity }}</template>
              </el-table-column>
              <el-table-column label="状态" width="120">
                <template #default="{ row }">
                  <el-tag :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="申请时间" width="170">
                <template #default="{ row }">{{ formatDateTime(row.created_at || row.operation_time) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="230" fixed="right">
                <template #default="{ row }">
                  <div class="en-op-actions en-op-actions--stack return-op-actions">
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
                  </div>
                </template>
              </el-table-column>
            </el-table>

            <div v-if="!isDocsExpanded(batch) && hiddenDocCount(batch) > 0" class="doc-more">
              还有 {{ hiddenDocCount(batch) }} 张未展示
            </div>
          </div>
        </div>
      </div>

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

    <el-dialog v-model="receiveDialogVisible" title="收货确认（可部分）" width="880px">
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

    <el-dialog v-model="rejectDialogVisible" title="拒收退库" width="520px">
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { stockApi } from '@/api/stock'
import { useUserStore } from '@/stores/user'

const MAX_DOC_PREVIEW = 8

const userStore = useUserStore()

const loading = ref(false)
const receiveLoading = ref(false)
const submitting = ref(false)

const keyword = ref('')
const statusFilter = ref('pending_receive')

const warehouses = ref([])
const hasGlobalWarehouseAccess = computed(() => userStore.hasGlobalInventoryAccess)
const selectableWarehouses = computed(() => {
  const list = warehouses.value || []
  if (hasGlobalWarehouseAccess.value) return list
  const managedIds = new Set((userStore.managedWarehouseIds || []).map((id) => Number(id)))
  return list.filter((w) => managedIds.has(Number(w.id)))
})
const selectedWarehouseIds = ref([])

const batchRecords = ref([])
const expandedDocsMap = ref({})
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

const canReceiveRow = (row) => ['pending_receive', 'partially_received'].includes(String(row?.status || ''))
const canRejectRow = (row) => String(row?.status || '') === 'pending_receive'

const normalizeDoc = (doc) => ({
  id: doc?.id,
  document_number: String(doc?.document_number || '-'),
  out_document_number: String(doc?.out_document_number || '-'),
  out_warehouse_name: String(doc?.out_warehouse_name || ''),
  warehouse_name: String(doc?.warehouse_name || ''),
  operator_name: String(doc?.operator_name || ''),
  status: String(doc?.status || ''),
  main_device_count: Number(doc?.main_device_count || 0),
  aux_total_quantity: Number(doc?.aux_total_quantity || 0),
  pending_total_quantity: Number(doc?.pending_total_quantity || 0),
  approval_comments: String(doc?.approval_comments || ''),
  created_at: doc?.created_at || null,
  operation_time: doc?.operation_time || null,
})

const normalizeBatch = (batch) => {
  const docs = Array.isArray(batch?.documents) ? batch.documents.map(normalizeDoc) : []
  docs.sort((a, b) => (new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()))
  return {
    batch_id: String(batch?.batch_id || '-'),
    status: String(batch?.status || 'pending_receive'),
    created_at: batch?.created_at || null,
    latest_created_at: batch?.latest_created_at || null,
    batch_split_count: Number(batch?.batch_split_count || docs.length || 1),
    document_count: Number(batch?.document_count || docs.length || 0),
    main_device_count: Number(batch?.main_device_count || 0),
    aux_total_quantity: Number(batch?.aux_total_quantity || 0),
    pending_total_quantity: Number(batch?.pending_total_quantity || 0),
    reject_reasons: Array.isArray(batch?.reject_reasons)
      ? batch.reject_reasons.map(x => String(x || '').trim()).filter(Boolean)
      : [],
    documents: docs,
  }
}

const initExpandState = (list, reset = false) => {
  const next = reset ? {} : { ...(expandedDocsMap.value || {}) }
  for (const batch of list || []) {
    const key = String(batch?.batch_id || '').trim()
    if (!key || Object.prototype.hasOwnProperty.call(next, key)) continue
    const size = Array.isArray(batch?.documents) ? batch.documents.length : 0
    next[key] = size <= MAX_DOC_PREVIEW
  }
  expandedDocsMap.value = next
}

const isDocsExpanded = (batch) => {
  const key = String(batch?.batch_id || '').trim()
  if (!key) return true
  if (!Object.prototype.hasOwnProperty.call(expandedDocsMap.value || {}, key)) {
    const size = Array.isArray(batch?.documents) ? batch.documents.length : 0
    return size <= MAX_DOC_PREVIEW
  }
  return !!expandedDocsMap.value[key]
}

const visibleDocs = (batch) => {
  const docs = Array.isArray(batch?.documents) ? batch.documents : []
  if (isDocsExpanded(batch)) return docs
  return docs.slice(0, MAX_DOC_PREVIEW)
}

const hiddenDocCount = (batch) => {
  const docs = Array.isArray(batch?.documents) ? batch.documents : []
  if (isDocsExpanded(batch)) return 0
  return Math.max(0, docs.length - MAX_DOC_PREVIEW)
}

const toggleDocs = (batch) => {
  const key = String(batch?.batch_id || '').trim()
  if (!key) return
  const cur = isDocsExpanded(batch)
  expandedDocsMap.value = { ...(expandedDocsMap.value || {}), [key]: !cur }
}

const collectBatchRejectRows = (batch) => {
  const rows = []
  for (const doc of batch?.documents || []) {
    if (String(doc?.status || '') !== 'rejected') continue
    const reason = String(doc?.approval_comments || '').trim()
    rows.push({
      document_number: String(doc?.document_number || '-'),
      reason: reason || '未填写驳回原因',
    })
  }
  if (rows.length > 0) return rows
  const fallback = Array.isArray(batch?.reject_reasons)
    ? batch.reject_reasons.map(x => String(x || '').trim()).filter(Boolean)
    : []
  return fallback.map((reason) => ({ document_number: '-', reason }))
}

const showBatchRejectReason = (batch) => collectBatchRejectRows(batch).length > 0

const rejectReasonPreview = (batch) => {
  const rows = collectBatchRejectRows(batch)
  if (rows.length === 0) return '未填写驳回原因'
  const first = rows[0]
  const base = first.document_number && first.document_number !== '-'
    ? `${first.document_number}：${first.reason}`
    : first.reason
  return base.length > 36 ? `${base.slice(0, 36)}...` : base
}

const openBatchRejectReason = (batch) => {
  const rows = collectBatchRejectRows(batch)
  const content = rows.length
    ? rows.map((row, idx) => {
      if (row.document_number && row.document_number !== '-') {
        return `${idx + 1}. 退库单号：${row.document_number}\n${row.reason}`
      }
      return `${idx + 1}. ${row.reason}`
    }).join('\n\n')
    : '未填写驳回原因'
  ElMessageBox.alert(content, `批次 ${batch?.batch_id || '-'} - 驳回原因`, {
    confirmButtonText: '确定',
  })
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
    const res = await stockApi.listReturnWorkbenchBatches(params)
    const list = Array.isArray(res?.records) ? res.records.map(normalizeBatch) : []
    batchRecords.value = list
    total.value = Number(res?.total || 0)
    initExpandState(list, true)
  } catch (error) {
    console.error('加载退库批次失败:', error)
    ElMessage.error(error?.response?.data?.detail || '加载退库批次失败')
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
    .map((it) => ({ ...it, _receive_qty: 0 }))
}

const openReceive = async (row) => {
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
  if (!hasGlobalWarehouseAccess.value) {
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

.table-card {
  margin-bottom: 12px;
}

.table-meta {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.batch-list {
  display: grid;
  gap: 14px;
}

.batch-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 14px;
  background: #fff;
}

.batch-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.batch-id {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.batch-meta {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.batch-stats {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.stat-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 8px 10px;
  background: #fafafa;
}

.stat-item .k {
  font-size: 12px;
  color: var(--text-secondary);
}

.stat-item .v {
  margin-top: 4px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.batch-reject {
  margin-top: 10px;
  border: 1px solid #fecaca;
  background: #fef2f2;
  border-radius: 8px;
  padding: 8px 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.reject-title {
  color: #b91c1c;
  font-weight: 700;
  flex-shrink: 0;
}

.reject-content {
  color: #7f1d1d;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reject-action {
  color: #991b1b;
  font-weight: 700;
  flex-shrink: 0;
}

.doc-box {
  margin-top: 12px;
}

.doc-box-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.doc-title {
  font-weight: 700;
  color: var(--text-primary);
}

.doc-more {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  text-align: center;
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
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}

.main-sn-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

html[lang='en-US'] .return-op-actions :deep(.el-button) {
  min-width: 132px;
  justify-content: center;
}

@media (max-width: 980px) {
  .toolbar-card :deep(.el-row) {
    row-gap: 10px;
  }

  .page-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }

  .batch-stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .chips {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
