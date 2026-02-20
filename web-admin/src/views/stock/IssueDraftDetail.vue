<template>
  <div class="page-container">
    <div class="page-header detail-header">
      <div class="left">
        <el-button class="back" @click="router.back()">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <div class="title">
          <h2 class="h2">
            出库确认
            <span class="mono">{{ draft?.draft_no || '-' }}</span>
          </h2>
          <div class="meta">
            <el-tag :type="statusTagType(draft?.status)">{{ statusText(draft?.status) }}</el-tag>
            <span class="dot">·</span>
            <span>仓库：{{ draft?.warehouse_name || draft?.warehouse_id || '-' }}</span>
            <span class="dot">·</span>
            <span>申请人：{{ draft?.request?.requester_name || '-' }}</span>
            <span class="dot">·</span>
            <span>申请单：{{ draft?.request?.request_no || draft?.request_id || '-' }}</span>
          </div>
        </div>
      </div>

      <div class="right">
        <el-button @click="load" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-card class="card hero" shadow="never" v-loading="loading">
      <div class="hero-grid">
        <div class="hero-left">
          <div class="flow-title">本单待确认概览</div>
          <div class="chips">
            <div class="chip">
              <div class="k">待确认 SN</div>
              <div class="v">{{ pendingSerials.length }}</div>
            </div>
            <div class="chip">
              <div class="k">已选 SN</div>
              <div class="v">{{ selectedSerialIds.size }}</div>
            </div>
            <div class="chip">
              <div class="k">辅料本次确认</div>
              <div class="v">{{ auxConfirmTotal }}</div>
            </div>
            <div class="chip accent">
              <div class="k">本次总确认</div>
              <div class="v">{{ totalConfirm }}</div>
            </div>
          </div>

          <div class="scanner">
            <div class="label">扫码快速勾选 SN（不强制复扫）</div>
            <el-input
              v-model="snScanInput"
              placeholder="用扫码枪扫 SN 后回车"
              clearable
              @keyup.enter="onScanEnter"
            >
              <template #prefix>
                <el-icon><Aim /></el-icon>
              </template>
              <template #append>
                <el-button @click="onScanEnter">勾选</el-button>
              </template>
            </el-input>
            <div class="scanner-sub">提示：未输入 SN 时，点击“勾选”无动作</div>
          </div>
        </div>

        <div class="hero-right">
          <div class="mini">
            <div class="line">
              <span class="k">提交时间</span>
              <span class="v">{{ formatDateTime(draft?.submitted_at || draft?.created_at) }}</span>
            </div>
            <div class="line">
              <span class="k">上次确认</span>
              <span class="v">{{ formatDateTime(draft?.confirmed_at) }}</span>
            </div>
            <div class="line">
              <span class="k">驳回原因</span>
              <span class="v">{{ draft?.reject_reason || '-' }}</span>
            </div>
          </div>

          <div class="actions">
            <el-button v-if="canReject" type="danger" plain @click="openReject">驳回整单</el-button>
            <el-button v-if="canRejectRemaining" type="danger" plain @click="openRejectRemaining">驳回剩余</el-button>
            <el-button
              v-if="canConfirm"
              type="primary"
              :loading="confirming"
              @click="confirm"
            >
              确认出库（可部分）
            </el-button>
          </div>
        </div>
      </div>
    </el-card>

    <div class="content-grid">
      <el-card class="card" shadow="never">
        <template #header>
          <div class="section-header">
            <div class="section-title">
              <span class="title">主设备 SN</span>
              <span class="desc">勾选本次确认的 SN；不勾选则不确认 SN</span>
            </div>
            <div class="section-actions">
              <el-button @click="selectAllPending" :disabled="pendingSerials.length === 0">全选待确认</el-button>
              <el-button @click="clearSelected" :disabled="selectedSerialIds.size === 0">清空勾选</el-button>
            </div>
          </div>
        </template>

        <el-table :data="serialRows" style="width: 100%" row-key="id">
          <el-table-column width="56">
            <template #default="{ row }">
              <el-checkbox
                v-model="row._selected"
                :disabled="row.status !== 'pending' || !canConfirm"
                @change="(v) => onRowSelectChange(row, v)"
              />
            </template>
          </el-table-column>
          <el-table-column prop="serial_number" label="SN" min-width="260">
            <template #default="{ row }">
              <div class="sn-line" :class="{ hit: row.id === lastScanHitId }">
                <span class="sn">{{ row.serial_number }}</span>
                <span class="model">{{ equipmentNameById(row.equipment_id) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.status === 'confirmed' ? 'success' : 'warning'" effect="plain">
                {{ row.status === 'confirmed' ? '已确认' : '待确认' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="scanned_at" label="扫码时间" width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.scanned_at) }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="card aux" shadow="never">
        <template #header>
          <div class="section-header">
            <div class="section-title">
              <span class="title">辅料确认</span>
              <span class="desc">本次确认数量 ≤ 待确认数量</span>
            </div>
            <div class="section-actions">
              <el-button @click="fillAuxAll" :disabled="!canConfirm || auxRows.length === 0">一键填满</el-button>
              <el-button @click="clearAux" :disabled="auxConfirmTotal === 0">清空</el-button>
            </div>
          </div>
        </template>

        <el-table :data="auxRows" style="width: 100%">
          <el-table-column prop="equipment_name" label="辅料" min-width="240" />
          <el-table-column prop="pending_qty" label="待确认" width="120" />
          <el-table-column label="本次确认" width="180">
            <template #default="{ row }">
              <el-input-number
                v-model="row._confirm_qty"
                :min="0"
                :max="row.pending_qty"
                :disabled="!canConfirm || row.pending_qty <= 0"
                controls-position="right"
              />
            </template>
          </el-table-column>
          <el-table-column prop="unit" label="单位" width="90" />
        </el-table>

        <div class="notes">
          <div class="label">出库备注</div>
          <el-input v-model="confirmNotes" placeholder="可选：本次确认说明" clearable />
        </div>
      </el-card>
    </div>

    <!-- 库存不足提示 -->
    <el-dialog v-model="shortagesVisible" title="库存不足，无法确认出库" width="680px">
      <el-table :data="shortages" style="width: 100%">
        <el-table-column prop="equipment_name" label="物料" min-width="220" />
        <el-table-column prop="required" label="需要" width="120" />
        <el-table-column prop="available" label="可用" width="120" />
        <el-table-column prop="current_stock" label="现存" width="120" />
      </el-table>
      <template #footer>
        <el-button type="primary" @click="shortagesVisible = false">知道了</el-button>
      </template>
    </el-dialog>

    <!-- 驳回对话框 -->
    <el-dialog v-model="rejectVisible" :title="rejectMode === 'remaining' ? '驳回剩余待确认项' : '驳回待确认出库单'" width="520px">
      <el-form label-width="90px">
        <el-form-item label="原因" required>
          <el-input v-model="rejectReason" type="textarea" :rows="3" placeholder="请输入驳回原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" :loading="rejecting" @click="reject">{{ rejectMode === 'remaining' ? '确认驳回剩余' : '确认驳回' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { stockApi } from '../../api/stock'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const confirming = ref(false)
const rejecting = ref(false)

const draft = ref(null)

const snScanInput = ref('')
const lastScanHitId = ref(null)

const selectedSerialIds = reactive(new Set())
const auxRows = ref([])
const confirmNotes = ref('')

const shortagesVisible = ref(false)
const shortages = ref([])

const rejectVisible = ref(false)
const rejectReason = ref('')
const rejectMode = ref('all')

const draftId = computed(() => String(route.params.id || '').trim())
const pendingSerials = computed(() => (draft.value?.serials || []).filter(s => s.status === 'pending'))
const canConfirm = computed(() => ['pending_confirm', 'partially_confirmed'].includes(draft.value?.status))
const canReject = computed(() => draft.value?.status === 'pending_confirm')
const canRejectRemaining = computed(() => draft.value?.status === 'partially_confirmed')

const serialRows = computed(() => {
  const rows = (draft.value?.serials || []).map((s) => ({
    ...s,
    _selected: selectedSerialIds.has(Number(s.id)),
  }))
  // pending 优先展示
  rows.sort((a, b) => {
    const ap = a.status === 'pending' ? 0 : 1
    const bp = b.status === 'pending' ? 0 : 1
    if (ap !== bp) return ap - bp
    return String(a.serial_number || '').localeCompare(String(b.serial_number || ''))
  })
  return rows
})

const auxConfirmTotal = computed(() => {
  return auxRows.value.reduce((s, r) => s + Number(r._confirm_qty || 0), 0)
})

const totalConfirm = computed(() => auxConfirmTotal.value + selectedSerialIds.size)

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

const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

const equipmentNameById = (equipmentId) => {
  const items = draft.value?.request?.items || []
  const found = items.find(i => Number(i.equipment_id) === Number(equipmentId))
  return found?.equipment_name || ''
}

const extractError = (error) => {
  const detail = error?.response?.data?.detail
  if (!detail) return { message: error?.message || '操作失败' }
  if (typeof detail === 'string') return { message: detail }
  return { message: detail?.message || '操作失败', shortages: detail?.shortages }
}

const load = async () => {
  if (!draftId.value) return
  try {
    loading.value = true
    const res = await stockApi.getIssueDraftDetail(draftId.value)
    draft.value = res?.draft || null

    // 默认选中全部 pending SN（便于一键确认）；若已存在选择则保留
    if (selectedSerialIds.size === 0) {
      for (const s of pendingSerials.value) selectedSerialIds.add(Number(s.id))
    } else {
      // 清理已不存在的 id
      const valid = new Set((draft.value?.serials || []).map(s => Number(s.id)))
      for (const id of Array.from(selectedSerialIds)) {
        if (!valid.has(id)) selectedSerialIds.delete(id)
      }
    }

    auxRows.value = (draft.value?.aux_items || []).map((r) => ({
      ...r,
      pending_qty: Number(r.pending_qty || 0),
      _confirm_qty: typeof r._confirm_qty === 'number' ? r._confirm_qty : Number(r.pending_qty || 0),
    }))
    confirmNotes.value = ''
    lastScanHitId.value = null
    snScanInput.value = ''
  } catch (error) {
    console.error('加载待确认出库单失败:', error)
    ElMessage.error(extractError(error).message)
  } finally {
    loading.value = false
  }
}

const onRowSelectChange = (row, checked) => {
  const id = Number(row.id)
  if (!id) return
  if (checked) selectedSerialIds.add(id)
  else selectedSerialIds.delete(id)
}

const selectAllPending = () => {
  for (const s of pendingSerials.value) selectedSerialIds.add(Number(s.id))
}

const clearSelected = () => {
  selectedSerialIds.clear()
}

const fillAuxAll = () => {
  auxRows.value = auxRows.value.map(r => ({ ...r, _confirm_qty: Number(r.pending_qty || 0) }))
}

const clearAux = () => {
  auxRows.value = auxRows.value.map(r => ({ ...r, _confirm_qty: 0 }))
}

const onScanEnter = () => {
  const sn = String(snScanInput.value || '').trim()
  if (!sn) return
  const hit = (draft.value?.serials || []).find(s => String(s.serial_number || '').trim() === sn)
  if (!hit) {
    ElMessage.warning('未在本单中找到该SN')
    snScanInput.value = ''
    return
  }
  if (hit.status !== 'pending') {
    ElMessage.info('该SN已确认，无需重复操作')
    lastScanHitId.value = Number(hit.id)
    snScanInput.value = ''
    return
  }
  selectedSerialIds.add(Number(hit.id))
  lastScanHitId.value = Number(hit.id)
  snScanInput.value = ''
}

const confirm = async () => {
  try {
    confirming.value = true
    const serial_ids = Array.from(selectedSerialIds)
    const aux_items = auxRows.value
      .map(r => ({ equipment_id: r.equipment_id, quantity: Number(r._confirm_qty || 0) }))
      .filter(r => Number(r.quantity || 0) > 0)

    await stockApi.confirmIssueDraft(draftId.value, {
      serial_ids,
      aux_items,
      notes: (confirmNotes.value || '').trim(),
    })
    ElMessage.success('确认出库成功')
    selectedSerialIds.clear()
    await load()
  } catch (error) {
    console.error('确认出库失败:', error)
    const parsed = extractError(error)
    if (parsed?.shortages && Array.isArray(parsed.shortages)) {
      shortages.value = parsed.shortages
      shortagesVisible.value = true
    }
    ElMessage.error(parsed.message)
  } finally {
    confirming.value = false
  }
}

const openReject = () => {
  rejectMode.value = 'all'
  rejectReason.value = ''
  rejectVisible.value = true
}

const openRejectRemaining = () => {
  rejectMode.value = 'remaining'
  rejectReason.value = ''
  rejectVisible.value = true
}

const reject = async () => {
  try {
    rejecting.value = true
    const reason = (rejectReason.value || '').trim()
    if (!reason) {
      ElMessage.warning('请填写驳回原因')
      return
    }
    if (rejectMode.value === 'remaining') {
      await stockApi.rejectRemainingIssueDraft(draftId.value, { reason })
      ElMessage.success('已驳回剩余项')
    } else {
      await stockApi.rejectIssueDraft(draftId.value, { reason })
      ElMessage.success('已驳回')
    }
    rejectVisible.value = false
    selectedSerialIds.clear()
    await load()
  } catch (error) {
    console.error('驳回失败:', error)
    ElMessage.error(extractError(error).message)
  } finally {
    rejecting.value = false
  }
}

watch(
  () => draftId.value,
  async () => {
    selectedSerialIds.clear()
    await load()
  }
)

onMounted(async () => {
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
  font-size: 16px;
  margin-left: 8px;
  color: #0f766e;
}

.meta {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.meta .dot {
  opacity: 0.7;
}

.hero {
  border-radius: 16px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background:
    radial-gradient(1000px 360px at 10% 0%, rgba(16, 185, 129, 0.12), transparent 60%),
    radial-gradient(1100px 420px at 90% 30%, rgba(59, 130, 246, 0.08), transparent 60%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.98));
}

.hero-grid {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 18px;
}

.flow-title {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.chips {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.chip {
  border-radius: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(10px);
}

.chip .k {
  color: var(--text-secondary);
  font-size: 12px;
}

.chip .v {
  margin-top: 8px;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.2px;
}

.chip.accent {
  grid-column: span 2;
  border: 1px solid rgba(16, 185, 129, 0.18);
  background: linear-gradient(180deg, rgba(240, 253, 250, 0.9), rgba(255, 255, 255, 0.9));
}

.scanner {
  margin-top: 14px;
  border-radius: 14px;
  border: 1px solid rgba(16, 185, 129, 0.18);
  background: rgba(240, 253, 250, 0.65);
  padding: 12px 14px;
}

.scanner .label {
  font-size: 12px;
  color: #0f766e;
  margin-bottom: 8px;
}

.scanner-sub {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.hero-right .mini {
  border-radius: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background: rgba(255, 255, 255, 0.72);
}

.mini .line {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 6px 0;
  color: var(--text-secondary);
  font-size: 12px;
  gap: 12px;
}

.mini .line .v {
  color: var(--text-primary);
  font-weight: 500;
  text-align: right;
  max-width: 65%;
  word-break: break-word;
}

.actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.content-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
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

.sn-line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid transparent;
}

.sn-line .sn {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
}

.sn-line .model {
  color: var(--text-secondary);
  font-size: 12px;
}

.sn-line.hit {
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(240, 253, 250, 0.7);
}

.aux {
  border-radius: 16px;
  border: 1px solid rgba(249, 115, 22, 0.14);
  background:
    radial-gradient(900px 240px at 90% 0%, rgba(249, 115, 22, 0.12), transparent 55%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.98));
}

.notes {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
}

.notes .label {
  color: var(--text-secondary);
  font-size: 12px;
  margin-bottom: 6px;
}

@media (max-width: 1200px) {
  .hero-grid {
    grid-template-columns: 1fr;
  }
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
