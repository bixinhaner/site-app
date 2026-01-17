<template>
  <div class="page-container">
    <div class="page-header detail-header">
      <div class="left">
        <el-button class="back" @click="router.back()">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <div class="title">
          <h2 class="h2">
            申请单
            <span class="mono">{{ requestData?.request_no || '-' }}</span>
          </h2>
          <div class="meta">
            <el-tag :type="statusTagType(requestData?.status)">{{ statusText(requestData?.status) }}</el-tag>
            <span class="dot">·</span>
            <span>仓库：{{ requestData?.warehouse_name || '-' }}</span>
            <span class="dot">·</span>
            <span>申请人：{{ requestData?.requester_name || '-' }}</span>
          </div>
        </div>
      </div>

      <div class="right">
        <el-button @click="load" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button
          v-if="canCancel"
          type="danger"
          plain
          @click="openCancel"
        >
          取消申请
        </el-button>
      </div>
    </div>

    <el-card class="card hero" shadow="never" v-loading="loading">
      <div class="hero-grid">
        <div class="hero-left">
          <div class="flow-title">流程进度</div>
          <el-steps
            :active="flowActive"
            align-center
            finish-status="success"
            class="steps"
          >
            <el-step title="申请" description="填写物料与数量" />
            <el-step title="审批" description="仓库可部分批准" />
            <el-step title="领料" description="主设备逐台扫码" />
            <el-step title="出库" description="仓库可部分确认" />
          </el-steps>

          <div v-if="requestData?.notes" class="notes">
            <div class="label">备注</div>
            <div class="value">{{ requestData.notes }}</div>
          </div>
        </div>

        <div class="hero-right">
          <div class="stat">
            <div class="k">主设备申请</div>
            <div class="v">{{ mainRequestedTotal }}</div>
          </div>
          <div class="stat">
            <div class="k">辅料申请</div>
            <div class="v">{{ auxRequestedTotal }}</div>
          </div>
          <div class="stat accent">
            <div class="k">剩余可发</div>
            <div class="v">{{ remainingTotal }}</div>
          </div>
          <div class="mini">
            <div class="line">
              <span class="k">提交时间</span>
              <span class="v">{{ formatDateTime(requestData?.submitted_at) }}</span>
            </div>
            <div class="line">
              <span class="k">审批时间</span>
              <span class="v">{{ formatDateTime(requestData?.approved_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <div class="content-grid">
      <el-card class="card" shadow="never">
        <template #header>
          <div class="section-header">
            <div class="section-title">
              <span class="title">申请明细</span>
              <span class="desc">已发放以仓库“确认出库”为准</span>
            </div>
            <div class="section-actions">
              <el-button
                v-if="isDraft"
                type="primary"
                plain
                @click="addDraftRow"
              >
                <el-icon><Plus /></el-icon>
                添加一行
              </el-button>
            </div>
          </div>
        </template>

        <el-table :data="tableRows" style="width: 100%">
          <el-table-column label="物料" min-width="320">
            <template #default="{ row }">
              <div v-if="isDraft" class="cell-ctrl">
                <el-select
                  v-model="row.equipment"
                  value-key="id"
                  filterable
                  clearable
                  placeholder="选择物料"
                  @change="onDraftEquipChange(row)"
                >
                  <el-option
                    v-for="eq in equipmentOptions"
                    :key="eq.id"
                    :label="`${eq.equipment_name}（${eq.equipment_code}）`"
                    :value="eq"
                  />
                </el-select>
              </div>
              <div v-else class="cell-text">
                <div class="name">{{ row.equipment_name || '-' }}</div>
                <div class="code">{{ row.equipment_code || '' }}</div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="类别" width="120">
            <template #default="{ row }">
              <el-tag
                :type="((isDraft ? (row.equipment?.category || row.equipment_category) : row.equipment_category) === 'main_device') ? 'warning' : 'info'"
                effect="plain"
              >
                {{ (isDraft ? (row.equipment?.category || row.equipment_category) : row.equipment_category) === 'main_device' ? '主设备' : '辅料' }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="申请" width="140">
            <template #default="{ row }">
              <div v-if="isDraft" class="cell-ctrl">
                <el-input-number
                  v-model="row.requested_qty"
                  :min="1"
                  :max="99999"
                  controls-position="right"
                />
              </div>
              <span v-else>{{ row.requested_qty }}</span>
            </template>
          </el-table-column>

          <el-table-column label="已批准" width="110">
            <template #default="{ row }">
              <span v-if="isDraft">-</span>
              <span v-else>{{ row.approved_qty }}</span>
            </template>
          </el-table-column>
          <el-table-column label="已发放" width="110">
            <template #default="{ row }">
              <span v-if="isDraft">-</span>
              <span v-else>{{ row.issued_qty }}</span>
            </template>
          </el-table-column>
          <el-table-column label="待确认" width="110">
            <template #default="{ row }">
              <span v-if="isDraft">-</span>
              <span v-else>{{ row.pending_qty }}</span>
            </template>
          </el-table-column>
          <el-table-column label="可发" width="90">
            <template #default="{ row }">
              <span v-if="isDraft">-</span>
              <span v-else>{{ row.remaining_qty }}</span>
            </template>
          </el-table-column>

          <el-table-column v-if="isDraft" label="操作" width="120" fixed="right">
            <template #default="{ $index }">
              <el-button type="danger" link @click="removeDraftRow($index)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="isDraft" class="draft-actions">
          <div class="draft-left">
            <div class="draft-label">发料仓库</div>
            <el-select v-model="draftWarehouseId" filterable placeholder="选择仓库" class="warehouse-select">
              <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
            </el-select>
            <div class="draft-label">备注</div>
            <el-input v-model="draftNotes" placeholder="可选：用途/项目/紧急程度" class="notes-input" />
          </div>

          <div class="draft-right">
            <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
            <el-button type="primary" :loading="saving" @click="submitDraft">提交申请</el-button>
          </div>
        </div>
      </el-card>

      <el-card v-if="canApprove" class="card approve" shadow="never">
        <template #header>
          <div class="section-header">
            <div class="section-title">
              <span class="title">审批面板</span>
              <span class="desc">支持部分批准；全部为 0 请用驳回</span>
            </div>
            <div class="section-actions">
              <el-button @click="fillApproveAll">全部按申请量</el-button>
              <el-button @click="fillApproveZero">全部清零</el-button>
            </div>
          </div>
        </template>

        <el-table :data="approveRows" style="width: 100%">
          <el-table-column prop="equipment_name" label="物料" min-width="240" />
          <el-table-column prop="equipment_category" label="类别" width="110">
            <template #default="{ row }">
              <el-tag :type="row.equipment_category === 'main_device' ? 'warning' : 'info'" effect="plain">
                {{ row.equipment_category === 'main_device' ? '主设备' : '辅料' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="requested_qty" label="申请" width="100" />
          <el-table-column label="批准" width="180">
            <template #default="{ row }">
              <el-input-number
                v-model="row.approved_qty"
                :min="0"
                :max="row.requested_qty"
                controls-position="right"
              />
            </template>
          </el-table-column>
        </el-table>

        <div class="approve-footer">
          <el-input
            v-model="approveComments"
            placeholder="可选：审批说明"
            clearable
          />
          <div class="btns">
            <el-button type="danger" plain @click="openReject">驳回</el-button>
            <el-button type="primary" :loading="approving" @click="approve">通过（可部分）</el-button>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 驳回对话框 -->
    <el-dialog v-model="rejectVisible" title="驳回申请" width="520px">
      <el-form label-width="90px">
        <el-form-item label="原因" required>
          <el-input v-model="rejectReason" type="textarea" :rows="3" placeholder="请输入驳回原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" :loading="rejecting" @click="reject">确认驳回</el-button>
      </template>
    </el-dialog>

    <!-- 取消对话框 -->
    <el-dialog v-model="cancelVisible" title="取消申请" width="520px">
      <el-form label-width="90px">
        <el-form-item label="原因">
          <el-input v-model="cancelReason" type="textarea" :rows="3" placeholder="可选：填写取消原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancelVisible = false">返回</el-button>
        <el-button type="danger" :loading="canceling" @click="cancel">确认取消</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { stockApi } from '../../api/stock'
import { equipmentApi } from '../../api/equipment'
import { useUserStore } from '../../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const requestData = ref(null)
const warehouses = ref([])
const equipmentOptions = ref([])

const saving = ref(false)
const approving = ref(false)
const rejecting = ref(false)
const canceling = ref(false)

const rejectVisible = ref(false)
const rejectReason = ref('')

const cancelVisible = ref(false)
const cancelReason = ref('')

const draftWarehouseId = ref(undefined)
const draftNotes = ref('')
const draftRows = ref([])

const approveRows = ref([])
const approveComments = ref('')

const requestId = computed(() => String(route.params.id || '').trim())
const isWarehouseOperator = computed(() => ['admin', 'manager', 'warehouse_manager'].includes(userStore.user?.role))
const isDraft = computed(() => requestData.value?.status === 'draft')
const canApprove = computed(() => isWarehouseOperator.value && requestData.value?.status === 'submitted')
const canCancel = computed(() => isWarehouseOperator.value && ['draft', 'submitted'].includes(requestData.value?.status))

const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

const statusText = (status) => {
  const map = {
    draft: '草稿',
    submitted: '待审批',
    approved: '已批准',
    partially_approved: '部分批准',
    rejected: '已驳回',
    canceled: '已取消',
    closed: '已关闭',
  }
  return map[status] || status || '-'
}

const statusTagType = (status) => {
  const map = {
    draft: 'info',
    submitted: 'warning',
    approved: 'success',
    partially_approved: 'warning',
    rejected: 'danger',
    canceled: 'info',
    closed: 'success',
  }
  return map[status] || ''
}

const extractError = (error) => {
  const detail = error?.response?.data?.detail
  if (!detail) return error?.message || '操作失败'
  if (typeof detail === 'string') return detail
  return detail?.message || '操作失败'
}

const flowActive = computed(() => {
  const status = requestData.value?.status
  if (status === 'draft') return 0
  if (status === 'submitted') return 1
  if (status === 'approved' || status === 'partially_approved') return 2
  if (status === 'closed') return 3
  return 0
})

const mainRequestedTotal = computed(() => {
  const items = requestData.value?.items || []
  return items.filter(i => i.equipment_category === 'main_device').reduce((s, i) => s + Number(i.requested_qty || 0), 0)
})

const auxRequestedTotal = computed(() => {
  const items = requestData.value?.items || []
  return items.filter(i => i.equipment_category === 'auxiliary').reduce((s, i) => s + Number(i.requested_qty || 0), 0)
})

const remainingTotal = computed(() => {
  const items = requestData.value?.items || []
  return items.reduce((s, i) => s + Number(i.remaining_qty || 0), 0)
})

const tableRows = computed(() => {
  return isDraft.value ? draftRows.value : (requestData.value?.items || [])
})

const loadBaseOptions = async () => {
  try {
    const [whRes, eqRes] = await Promise.all([
      stockApi.getWarehouses(),
      equipmentApi.getEquipmentList({ status: 'active', limit: 1000 }),
    ])
    warehouses.value = whRes?.warehouses || []
    equipmentOptions.value = Array.isArray(eqRes) ? eqRes : []
  } catch (error) {
    console.error('加载基础数据失败:', error)
  }
}

const load = async () => {
  if (!requestId.value) return
  try {
    loading.value = true
    const res = await stockApi.getMaterialRequestDetail(requestId.value)
    requestData.value = res?.request || null

    draftWarehouseId.value = requestData.value?.warehouse_id
    draftNotes.value = requestData.value?.notes || ''

    const eqMap = new Map(equipmentOptions.value.map(e => [e.id, e]))
    draftRows.value = (requestData.value?.items || []).map((it) => ({
      equipment: eqMap.get(it.equipment_id) || null,
      equipment_category: it.equipment_category,
      requested_qty: it.requested_qty,
    }))

    approveRows.value = (requestData.value?.items || []).map((it) => ({
      equipment_id: it.equipment_id,
      equipment_name: it.equipment_name,
      equipment_category: it.equipment_category,
      requested_qty: Number(it.requested_qty || 0),
      approved_qty: Number(it.requested_qty || 0),
    }))
    approveComments.value = ''
  } catch (error) {
    console.error('加载申请单失败:', error)
    ElMessage.error(extractError(error))
  } finally {
    loading.value = false
  }
}

const addDraftRow = () => {
  draftRows.value.push({ equipment: null, requested_qty: 1 })
}

const removeDraftRow = (idx) => {
  draftRows.value.splice(idx, 1)
}

const onDraftEquipChange = (row) => {
  if (!row.requested_qty || row.requested_qty < 1) row.requested_qty = 1
}

const saveDraft = async () => {
  try {
    saving.value = true
    const warehouse_id = Number(draftWarehouseId.value || 0)
    if (!warehouse_id) throw new Error('请选择仓库')

    const merged = new Map()
    for (const row of draftRows.value) {
      const eq = row?.equipment
      if (!eq?.id) continue
      const qty = Number(row.requested_qty || 0)
      if (qty <= 0) continue
      merged.set(eq.id, (merged.get(eq.id) || 0) + qty)
    }
    if (merged.size === 0) throw new Error('请至少添加一条明细')

    await stockApi.updateMaterialRequest(requestId.value, {
      warehouse_id,
      notes: (draftNotes.value || '').trim(),
      items: Array.from(merged.entries()).map(([equipment_id, quantity]) => ({ equipment_id, quantity })),
    })
    ElMessage.success('保存成功')
    await load()
  } catch (error) {
    console.error('保存草稿失败:', error)
    ElMessage.error(extractError(error) || error?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const submitDraft = async () => {
  try {
    await saveDraft()
    saving.value = true
    await stockApi.submitMaterialRequest(requestId.value)
    ElMessage.success('提交成功')
    await load()
  } catch (error) {
    console.error('提交失败:', error)
    ElMessage.error(extractError(error))
  } finally {
    saving.value = false
  }
}

const fillApproveAll = () => {
  approveRows.value = approveRows.value.map(r => ({ ...r, approved_qty: Number(r.requested_qty || 0) }))
}

const fillApproveZero = () => {
  approveRows.value = approveRows.value.map(r => ({ ...r, approved_qty: 0 }))
}

const approve = async () => {
  try {
    approving.value = true
    await stockApi.approveMaterialRequest(requestId.value, {
      items: approveRows.value.map(r => ({ equipment_id: r.equipment_id, approved_qty: Number(r.approved_qty || 0) })),
      comments: (approveComments.value || '').trim(),
    })
    ElMessage.success('审批成功')
    await load()
  } catch (error) {
    console.error('审批失败:', error)
    ElMessage.error(extractError(error))
  } finally {
    approving.value = false
  }
}

const openReject = () => {
  rejectReason.value = ''
  rejectVisible.value = true
}

const reject = async () => {
  try {
    rejecting.value = true
    await stockApi.rejectMaterialRequest(requestId.value, { reason: (rejectReason.value || '').trim() })
    ElMessage.success('已驳回')
    rejectVisible.value = false
    await load()
  } catch (error) {
    console.error('驳回失败:', error)
    ElMessage.error(extractError(error))
  } finally {
    rejecting.value = false
  }
}

const openCancel = () => {
  cancelReason.value = ''
  cancelVisible.value = true
}

const cancel = async () => {
  try {
    canceling.value = true
    await stockApi.cancelMaterialRequest(requestId.value, { reason: (cancelReason.value || '').trim() })
    ElMessage.success('已取消')
    cancelVisible.value = false
    await load()
  } catch (error) {
    console.error('取消失败:', error)
    ElMessage.error(extractError(error))
  } finally {
    canceling.value = false
  }
}

watch(
  () => requestId.value,
  async () => {
    await load()
  }
)

onMounted(async () => {
  await loadBaseOptions()
  await load()
})
</script>

<style scoped lang="scss">
.detail-header {
  align-items: flex-start;
}

.detail-header .left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.back {
  border-radius: 12px;
  padding: 10px 12px;
}

.title .h2 {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0.2px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 18px;
  margin-left: 8px;
  color: #9a3412;
}

.meta {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.meta .dot {
  opacity: 0.7;
}

.hero {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background:
    radial-gradient(1000px 380px at 10% 0%, rgba(249, 115, 22, 0.16), transparent 60%),
    radial-gradient(1100px 420px at 90% 30%, rgba(59, 130, 246, 0.08), transparent 60%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.96));
}

.hero-grid {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 18px;
}

.flow-title {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.steps :deep(.el-step__title) {
  font-weight: 600;
}

.notes {
  margin-top: 14px;
  border-radius: 14px;
  border: 1px solid rgba(249, 115, 22, 0.18);
  background: rgba(255, 247, 237, 0.65);
  padding: 12px 14px;
}

.notes .label {
  font-size: 12px;
  color: #9a3412;
  margin-bottom: 6px;
}

.notes .value {
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.hero-right {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  align-content: start;
}

.stat {
  border-radius: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(10px);
}

.stat .k {
  color: var(--text-secondary);
  font-size: 12px;
}

.stat .v {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.2px;
}

.stat.accent {
  grid-column: span 2;
  border: 1px solid rgba(249, 115, 22, 0.22);
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.9), rgba(255, 255, 255, 0.9));
}

.mini {
  grid-column: span 2;
  border-radius: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background: rgba(255, 255, 255, 0.65);
}

.mini .line {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 6px 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.mini .line .v {
  color: var(--text-primary);
  font-weight: 500;
}

.content-grid {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 18px;
  align-items: start;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.section-title .title {
  font-weight: 700;
  letter-spacing: 0.2px;
}

.section-title .desc {
  margin-left: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}

.cell-text .name {
  font-weight: 600;
}

.cell-text .code {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.draft-actions {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-end;
}

.draft-left {
  display: grid;
  grid-template-columns: auto 220px auto 1fr;
  gap: 10px;
  align-items: center;
  width: 100%;
}

.draft-label {
  color: var(--text-secondary);
  font-size: 12px;
  white-space: nowrap;
}

.warehouse-select {
  width: 220px;
}

.notes-input {
  width: 100%;
}

.draft-right {
  display: flex;
  gap: 10px;
  white-space: nowrap;
}

.approve {
  border-radius: 16px;
  border: 1px solid rgba(16, 185, 129, 0.14);
  background:
    radial-gradient(900px 240px at 90% 0%, rgba(16, 185, 129, 0.10), transparent 55%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.98));
}

.approve-footer {
  margin-top: 14px;
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.approve-footer .btns {
  display: flex;
  gap: 10px;
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
  .hero-grid {
    grid-template-columns: 1fr;
  }
  .draft-left {
    grid-template-columns: 1fr;
    align-items: stretch;
  }
  .warehouse-select {
    width: 100%;
  }
}
</style>
