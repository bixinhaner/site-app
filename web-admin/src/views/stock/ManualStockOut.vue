<template>
  <div class="page-container quick-out">
    <div class="page-header">
      <div class="title-block">
        <h2>快速出库（无申请）</h2>
        <div class="subtitle">{{ t('quickOut.subtitle') }}</div>
      </div>
    </div>

    <!-- 1. 基本信息 -->
    <el-card class="card" shadow="never">
      <div class="step-title"><span class="step">1</span>{{ t('quickOut.stepBasic') }}</div>
      <div class="basic-grid">
        <div class="field">
          <div class="label"><span class="required-mark">*</span>出库仓库</div>
          <el-select v-model="form.warehouse_id" filterable placeholder="选择仓库" @change="onWarehouseChange">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
          </el-select>
        </div>
        <div class="field">
          <div class="label"><span class="required-mark">*</span>{{ t('quickOut.receiver') }}</div>
          <el-select
            v-model="form.issued_to_user"
            filterable
            remote
            clearable
            :remote-method="searchUsers"
            :loading="userSearching"
            placeholder="输入姓名/用户名搜索"
            value-key="id"
          >
            <el-option
              v-for="u in userOptions"
              :key="u.id"
              :label="`${u.full_name || u.username}（${u.username}）`"
              :value="u"
            />
          </el-select>
        </div>
        <div class="field">
          <div class="label">
            <span v-if="flowSettings.quick_stock_out_requires_site" class="required-mark">*</span>{{ t('stockTrace.targetSite') }}
          </div>
          <StockSitePicker v-model="form.site_id" @change="selectedSite = $event" />
        </div>
      </div>
    </el-card>

    <!-- 2. 物料 -->
    <el-card class="card" shadow="never">
      <div class="step-title"><span class="step">2</span>{{ t('quickOut.stepItems') }}</div>
      <div class="items-grid">
        <section>
          <div class="sub-head">
            <span class="sub-title">{{ t('quickOut.mainDevice') }}</span>
            <span class="sub-count" v-if="snList.length">{{ t('quickOut.snCount', { n: snList.length }) }}</span>
            <el-button v-if="snList.length" class="sub-action" link @click="clearSns">{{ t('quickOut.clear') }}</el-button>
          </div>
          <el-input
            v-model="snScanInput"
            :placeholder="t('quickOut.snPlaceholder')"
            clearable
            @keyup.enter="addSnFromInput"
            @paste="onSnPaste"
          >
            <template #prefix><el-icon><Aim /></el-icon></template>
          </el-input>
          <div class="sn-list">
            <el-tag v-for="sn in snList" :key="sn" closable class="sn-tag" @close="removeSn(sn)">{{ sn }}</el-tag>
            <div v-if="snList.length === 0" class="empty">{{ t('quickOut.snEmpty') }}</div>
          </div>
        </section>

        <section>
          <div class="sub-head">
            <span class="sub-title">{{ t('quickOut.aux') }}</span>
            <span class="sub-count" v-if="validAuxRows.length">{{ t('quickOut.auxCount', { n: validAuxRows.length }) }}</span>
          </div>
          <div v-for="(row, idx) in auxRows" :key="row.key" class="aux-row">
            <el-select
              v-model="row.equipment_id"
              filterable
              :placeholder="t('quickOut.auxPick')"
              class="aux-select"
            >
              <el-option
                v-for="inv in auxOptions"
                :key="inv.equipment_id"
                :label="`${inv.equipment_name}（${inv.equipment_code}）`"
                :value="inv.equipment_id"
                :disabled="usedAuxIds.has(inv.equipment_id) && inv.equipment_id !== row.equipment_id"
              >
                <div class="aux-option">
                  <span>{{ inv.equipment_name }}（{{ inv.equipment_code }}）</span>
                  <span class="avail">{{ t('quickOut.available', { n: inv.available_stock ?? 0 }) }}</span>
                </div>
              </el-option>
            </el-select>
            <el-input-number
              v-model="row.quantity"
              :min="1"
              :max="99999"
              controls-position="right"
              class="aux-qty"
              :class="{ over: isOverStock(row) }"
            />
            <span class="aux-avail" :class="{ over: isOverStock(row) }">
              {{ row.equipment_id ? t('quickOut.available', { n: auxAvailable(row.equipment_id) }) : '' }}
            </span>
            <el-button link type="danger" @click="removeAuxRow(idx)"><el-icon><Delete /></el-icon></el-button>
          </div>
          <el-button class="aux-add" :disabled="!form.warehouse_id" @click="addAuxRow">
            <el-icon><Plus /></el-icon>{{ form.warehouse_id ? t('quickOut.auxAdd') : t('quickOut.auxPickWarehouseFirst') }}
          </el-button>
        </section>
      </div>
    </el-card>

    <!-- 3. 出库凭证 + 备注 -->
    <el-card class="card" shadow="never">
      <div class="step-title">
        <span class="step">3</span>{{ t('quickOut.voucherTitle') }}
        <span v-if="flowSettings.quick_stock_out_requires_voucher" class="required-mark">*</span>
        <span v-else class="optional">{{ t('quickOut.optional') }}</span>
      </div>
      <VoucherUploader ref="voucherRef" v-model="form.offline_document_id" @change="voucherState = $event" />
      <div class="field notes">
        <div class="label">备注</div>
        <el-input v-model="form.notes" placeholder="可选：原因/项目/紧急程度" clearable />
      </div>
    </el-card>

    <!-- 底部操作栏 -->
    <div class="action-bar">
      <div class="summary">
        <span>{{ t('quickOut.summaryMain', { n: snList.length }) }}</span>
        <span class="dot">·</span>
        <span>{{ t('quickOut.summaryAux', { n: validAuxRows.length }) }}</span>
        <span class="dot">·</span>
        <span class="total">{{ t('quickOut.summaryTotal', { n: totalQty }) }}</span>
        <span v-if="voucherState.count" class="voucher-ok">
          <el-icon><Paperclip /></el-icon>{{ voucherState.count }}
        </span>
      </div>
      <div class="actions">
        <el-button @click="reset" :disabled="submitting">{{ t('quickOut.clear') }}</el-button>
        <el-button type="primary" :loading="submitting" @click="openConfirm">{{ t('quickOut.confirmOut') }}</el-button>
      </div>
    </div>

    <!-- 出库确认 -->
    <el-dialog v-model="confirmVisible" :title="t('quickOut.confirmTitle')" width="560px">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="出库仓库">{{ warehouseName }}</el-descriptions-item>
        <el-descriptions-item :label="t('quickOut.receiver')">{{ receiverName }}</el-descriptions-item>
        <el-descriptions-item :label="t('stockTrace.targetSite')">{{ siteName || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('quickOut.mainDevice')">{{ snList.length }}</el-descriptions-item>
        <el-descriptions-item :label="t('quickOut.aux')">
          <div v-for="r in validAuxRows" :key="r.key">{{ auxName(r.equipment_id) }} × {{ r.quantity }}</div>
          <span v-if="!validAuxRows.length">-</span>
        </el-descriptions-item>
        <el-descriptions-item :label="t('quickOut.voucherTitle')">
          <span v-if="voucherState.count">{{ t('quickOut.voucherFiles', { n: voucherState.count }) }}</span>
          <span v-else class="warn">{{ t('quickOut.voucherNone') }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <div class="confirm-tip">{{ t('quickOut.confirmTip') }}</div>
      <template #footer>
        <el-button @click="confirmVisible = false">{{ t('quickOut.cancel') }}</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">{{ t('quickOut.confirmOut') }}</el-button>
      </template>
    </el-dialog>

    <!-- 出库成功 -->
    <el-dialog v-model="successVisible" width="420px" :show-close="false" align-center>
      <el-result icon="success" :title="t('quickOut.successTitle')" :sub-title="lastDocNo">
        <template #extra>
          <el-button @click="goHistory">{{ t('quickOut.viewHistory') }}</el-button>
          <el-button type="primary" @click="successVisible = false">{{ t('quickOut.continue') }}</el-button>
        </template>
      </el-result>
      <div v-if="!lastHadVoucher" class="success-tip">{{ t('quickOut.voucherLaterTip') }}</div>
    </el-dialog>

    <!-- 库存不足提示 -->
    <el-dialog v-model="shortagesVisible" title="库存不足，无法出库" width="680px">
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
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Aim, Delete, Paperclip, Plus } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { stockApi } from '../../api/stock'
import { userAPI } from '../../api/user'
import StockSitePicker from '../../components/inventory/StockSitePicker.vue'
import VoucherUploader from '../../components/inventory/VoucherUploader.vue'
import { loadStockFlowSettings, useStockFlowSettings } from '../../utils/stockFlowSettings'

const { t } = useI18n()
const router = useRouter()
const flowSettings = useStockFlowSettings()

const warehouses = ref([])
const inventory = ref([]) // 当前仓库库存（辅料可选项与可用数）

const emptyForm = () => ({
  warehouse_id: undefined,
  issued_to_user: null,
  site_id: null,
  notes: '',
  offline_document_id: null,
})
const form = ref(emptyForm())
const selectedSite = ref(null)

const snScanInput = ref('')
const snList = ref([])
const auxRows = ref([])
let auxSeq = 0

const voucherRef = ref(null)
const voucherState = ref({ count: 0, uploading: false })

const submitting = ref(false)
const confirmVisible = ref(false)
const successVisible = ref(false)
const lastDocNo = ref('')
const lastHadVoucher = ref(false)

const userSearching = ref(false)
const userOptions = ref([])

const shortagesVisible = ref(false)
const shortages = ref([])

const auxOptions = computed(() => inventory.value.filter((i) => i.category === 'auxiliary'))
const auxMap = computed(() => Object.fromEntries(auxOptions.value.map((i) => [i.equipment_id, i])))
const usedAuxIds = computed(() => new Set(auxRows.value.map((r) => r.equipment_id).filter(Boolean)))
const validAuxRows = computed(() => auxRows.value.filter((r) => r.equipment_id && Number(r.quantity) > 0))
const totalQty = computed(() => snList.value.length + validAuxRows.value.reduce((s, r) => s + Number(r.quantity || 0), 0))

const auxAvailable = (id) => Number(auxMap.value[id]?.available_stock ?? 0)
const auxName = (id) => {
  const inv = auxMap.value[id]
  return inv ? `${inv.equipment_name}（${inv.equipment_code}）` : String(id)
}
const isOverStock = (row) => !!row.equipment_id && Number(row.quantity || 0) > auxAvailable(row.equipment_id)

const warehouseName = computed(() => warehouses.value.find((w) => w.id === form.value.warehouse_id)?.warehouse_name || '-')
const receiverName = computed(() => {
  const u = form.value.issued_to_user
  return u ? `${u.full_name || u.username}（${u.username}）` : '-'
})
const siteName = computed(() => {
  const s = selectedSite.value
  if (!s || s.id !== form.value.site_id) return form.value.site_id ? String(form.value.site_id) : ''
  return s.site_name && s.site_code && s.site_name !== s.site_code ? `${s.site_name}（${s.site_code}）` : s.site_name || s.site_code
})

const extractError = (error) => {
  const detail = error?.response?.data?.detail
  if (!detail) return { message: error?.message || '操作失败' }
  if (typeof detail === 'string') return { message: detail }
  return { message: detail?.message || '操作失败', shortages: detail?.shortages }
}

const loadInventory = async () => {
  inventory.value = []
  if (!form.value.warehouse_id) return
  try {
    const res = await stockApi.getInventoryList({ warehouse_id: form.value.warehouse_id })
    inventory.value = res?.inventory || []
  } catch (error) {
    ElMessage.error('加载库存失败')
  }
}

const onWarehouseChange = () => {
  loadInventory()
}

const loadWarehouses = async () => {
  try {
    const res = await stockApi.getWarehouses()
    warehouses.value = res?.warehouses || []
    // 只有一个仓库时直接带出
    if (warehouses.value.length === 1 && !form.value.warehouse_id) {
      form.value.warehouse_id = warehouses.value[0].id
      loadInventory()
    }
  } catch (error) {
    ElMessage.error('加载基础数据失败')
  }
}

const searchUsers = async (query) => {
  const kw = String(query || '').trim()
  if (!kw) {
    userOptions.value = []
    return
  }
  try {
    userSearching.value = true
    const res = await userAPI.searchUsers({ keyword: kw, limit: 20 })
    userOptions.value = res?.users || []
  } catch (error) {
    userOptions.value = []
  } finally {
    userSearching.value = false
  }
}

const addSns = (values) => {
  let added = 0
  for (const raw of values) {
    const v = String(raw || '').trim()
    if (v && !snList.value.includes(v)) {
      snList.value.push(v)
      added += 1
    }
  }
  return added
}

const addSnFromInput = () => {
  addSns(String(snScanInput.value || '').split(/[\s,，;；]+/))
  snScanInput.value = ''
}

// 粘贴多行/多个 SN 时直接拆分加入；单个 SN 仍按普通输入处理
const onSnPaste = (e) => {
  const text = e.clipboardData?.getData('text') || ''
  const parts = text.split(/[\s,，;；]+/).filter(Boolean)
  if (parts.length <= 1) return
  e.preventDefault()
  const added = addSns(parts)
  ElMessage.success(t('quickOut.snPasted', { n: added }))
}

const removeSn = (sn) => {
  snList.value = snList.value.filter((s) => s !== sn)
}

const clearSns = () => {
  snList.value = []
  snScanInput.value = ''
}

const addAuxRow = () => {
  auxRows.value.push({ key: ++auxSeq, equipment_id: null, quantity: 1 })
}

const removeAuxRow = (idx) => {
  auxRows.value.splice(idx, 1)
}

const reset = () => {
  const keepWarehouse = warehouses.value.length === 1 ? form.value.warehouse_id : undefined
  form.value = { ...emptyForm(), warehouse_id: keepWarehouse }
  if (!keepWarehouse) inventory.value = []
  selectedSite.value = null
  clearSns()
  auxRows.value = []
  voucherRef.value?.reset()
  shortagesVisible.value = false
  shortages.value = []
}

const buildPayload = () => {
  const warehouse_id = Number(form.value.warehouse_id || 0)
  if (!warehouse_id) throw new Error('请选择出库仓库')
  const issued_to = Number(form.value.issued_to_user?.id || 0)
  if (!issued_to) throw new Error('请选择领取人')
  if (flowSettings.quick_stock_out_requires_site && !form.value.site_id) throw new Error('请选择目标站点')
  const aux_map = new Map()
  for (const row of validAuxRows.value) {
    aux_map.set(row.equipment_id, (aux_map.get(row.equipment_id) || 0) + Number(row.quantity))
  }
  if (snList.value.length === 0 && aux_map.size === 0) throw new Error('请至少录入1个主设备SN或辅料数量')
  if (voucherState.value.uploading) throw new Error(t('quickOut.voucherUploading'))
  if (flowSettings.quick_stock_out_requires_voucher && !form.value.offline_document_id) {
    throw new Error(t('quickOut.voucherRequired'))
  }
  return {
    warehouse_id,
    main_sns: snList.value.slice(),
    aux_items: Array.from(aux_map.entries()).map(([equipment_id, quantity]) => ({ equipment_id, quantity })),
    issued_to,
    site_id: form.value.site_id || null,
    notes: (form.value.notes || '').trim(),
    offline_document_id: form.value.offline_document_id || undefined,
  }
}

const openConfirm = () => {
  try {
    buildPayload()
    confirmVisible.value = true
  } catch (error) {
    ElMessage.warning(error.message)
  }
}

const submit = async () => {
  try {
    submitting.value = true
    const payload = buildPayload()
    const res = await stockApi.manualStockOut(payload)
    lastDocNo.value = res?.document_number || ''
    lastHadVoucher.value = !!payload.offline_document_id
    confirmVisible.value = false
    successVisible.value = true
    reset()
    loadInventory()
  } catch (error) {
    console.error('快速出库失败:', error)
    const parsed = extractError(error)
    if (Array.isArray(parsed?.shortages)) {
      shortages.value = parsed.shortages
      shortagesVisible.value = true
    }
    ElMessage.error(parsed.message)
  } finally {
    submitting.value = false
  }
}

const goHistory = () => {
  successVisible.value = false
  router.push({ name: 'StockHistory', query: { keyword: lastDocNo.value } })
}

onMounted(async () => {
  loadStockFlowSettings()
  await loadWarehouses()
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
}

.card {
  border-radius: 14px;
  margin-bottom: 16px;
}

.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 700;
  font-size: 15px;
}

.step {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #fff;
  background: var(--primary-color, var(--el-color-primary));
}

.optional {
  font-weight: 400;
  font-size: 12px;
  color: var(--text-secondary);
}

.basic-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1.4fr;
  gap: 16px;
}

.field .label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.field :deep(.el-select) {
  width: 100%;
}

.required-mark {
  color: var(--el-color-danger);
  margin-right: 4px;
}

.items-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 28px;
}

.sub-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 10px;
}

.sub-title {
  font-weight: 600;
}

.sub-count {
  font-size: 12px;
  color: var(--primary-color, var(--el-color-primary));
}

.sub-action {
  margin-left: auto;
}

.sn-list {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 220px;
  overflow: auto;
}

.sn-tag {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.empty {
  color: var(--text-secondary);
  font-size: 12px;
  padding: 6px 0;
}

.aux-row {
  display: grid;
  grid-template-columns: 1fr 130px 90px 28px;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.aux-qty {
  width: 130px;
}

.aux-qty.over :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--el-color-danger) inset;
}

.aux-avail {
  font-size: 12px;
  color: var(--text-secondary);
}

.aux-avail.over {
  color: var(--el-color-danger);
}

.aux-option {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.aux-option .avail {
  font-size: 12px;
  color: var(--text-secondary);
}

.aux-add {
  width: 100%;
  border-style: dashed;
}

.notes {
  margin-top: 18px;
  max-width: 640px;
}

.action-bar {
  position: sticky; // 吸附在内容区底部，不受侧边栏宽度/折叠影响
  bottom: 12px;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 18px;
  border-radius: 12px;
  border: 1px solid var(--el-border-color-lighter);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 6px 24px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(8px);
}

.summary {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 13px;
}

.summary .total {
  color: var(--text-primary);
  font-weight: 700;
}

.summary .dot {
  opacity: 0.5;
}

.voucher-ok {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: 10px;
  color: var(--el-color-success);
}

.confirm-tip {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.warn {
  color: var(--el-color-warning);
}

.success-tip {
  margin-top: -8px;
  text-align: center;
  font-size: 12px;
  color: var(--el-color-warning);
}

@media (max-width: 1200px) {
  .basic-grid,
  .items-grid {
    grid-template-columns: 1fr;
  }
}
</style>
