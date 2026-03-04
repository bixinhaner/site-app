<template>
  <div class="page-container">
    <div class="page-header">
      <div class="title-block">
        <h2>物料申请</h2>
        <div class="subtitle">申请 → 审批 → 自助领料 → 仓库确认出库（支持部分确认）</div>
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
        <el-col :xs="24" :sm="12" :md="4">
          <el-select v-model="filters.status_filter" placeholder="状态" clearable @change="resetAndLoad">
            <el-option label="草稿" value="draft" />
            <el-option label="待审批" value="submitted" />
            <el-option label="已批准" value="approved" />
            <el-option label="部分批准" value="partially_approved" />
            <el-option label="已放弃" value="abandoned" />
            <el-option label="已驳回" value="rejected" />
            <el-option label="已取消" value="canceled" />
            <el-option label="已关闭" value="closed" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="12" :md="5">
          <el-select v-model="filters.warehouse_id" placeholder="仓库" clearable filterable @change="resetAndLoad">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="24" :md="9">
          <el-input v-model="filters.keyword" placeholder="搜索申请单号/备注" clearable @keyup.enter="resetAndLoad">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
            <template #append>
              <el-button type="primary" @click="resetAndLoad">查询</el-button>
            </template>
          </el-input>
        </el-col>
        <el-col :xs="24" :sm="24" :md="6" class="quick-hint">
          <div class="hint-chip">
            <span class="dot" />
            <span>仓库可部分批准；出库可部分确认</span>
          </div>
        </el-col>
      </el-row>
    </div>

    <div class="card">
      <el-table :data="records" v-loading="loading" style="width: 100%" @row-dblclick="goDetail">
        <el-table-column prop="request_no" label="申请单号" :width="isCompactTable ? 210 : 230" />
        <el-table-column prop="warehouse_name" label="仓库" :width="isCompactTable ? 140 : 160" />
        <el-table-column v-if="!isCompactTable" prop="requester_name" label="申请人" width="140" />
        <el-table-column v-if="!isCompactTable" prop="main_summary" label="主设备摘要" min-width="240" />
        <el-table-column prop="status" label="状态" :width="isCompactTable ? 120 : 130">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!isCompactTable" prop="submitted_at" label="提交时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.submitted_at || row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="isCompactTable ? 140 : 160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="goDetail(row)">详情</el-button>
            <el-button
              v-if="isWarehouseOperator && row.status === 'submitted'"
              type="success"
              link
              @click="goDetail(row)"
            >
              审批
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

    <!-- 新建申请抽屉 -->
    <el-drawer v-model="createVisible" size="70%" :with-header="false" destroy-on-close>
      <div class="drawer-header">
        <div>
          <h3 class="drawer-title">新建物料申请（代他人）</h3>
          <div class="drawer-sub">支持按套装一键带出明细，也可自由增删改</div>
        </div>
        <el-button circle @click="createVisible = false">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>

      <div class="drawer-body">
        <el-card class="glass-card" shadow="never">
          <div class="grid">
            <div class="field">
              <div class="label">申请人</div>
              <el-select
                v-model="createForm.requester"
                filterable
                remote
                clearable
                :remote-method="searchUsers"
                :loading="userSearching"
                placeholder="输入姓名/用户名搜索"
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
              <div class="label">发料仓库</div>
              <el-select v-model="createForm.warehouse_id" filterable clearable placeholder="选择仓库">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
              </el-select>
            </div>

            <div class="field span2">
              <div class="label">备注</div>
              <el-input v-model="createForm.notes" placeholder="可选：用途/项目/紧急程度" />
            </div>
          </div>
        </el-card>

        <el-card class="quickfill" shadow="never">
          <template #header>
            <div class="quickfill-header">
              <div class="left">
                <span class="title">套装一键带出</span>
                <span class="desc">选套装 + 数量，自动合并到明细</span>
              </div>
              <div class="right">
                <el-button :disabled="!selectedPackage" @click="applyPackage">应用到明细</el-button>
              </div>
            </div>
          </template>

          <el-row :gutter="12">
            <el-col :span="12">
              <el-select v-model="selectedPackage" value-key="id" filterable clearable placeholder="选择套装">
                <el-option
                  v-for="p in packages"
                  :key="p.id"
                  :label="`${p.package_name}（${p.package_code}）`"
                  :value="p"
                />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-input-number v-model="packageCount" :min="1" :max="999" controls-position="right" />
            </el-col>
            <el-col :span="6" class="pkg-preview">
              <div class="preview" v-if="selectedPackage">
                <div class="pill">主设备 {{ selectedPackageMainQty }} * {{ packageCount }} = {{ selectedPackageMainTotal }}</div>
                <div class="pill">辅料 {{ selectedPackageAuxLineCount }} 行</div>
              </div>
              <div class="preview" v-else>
                <div class="muted">可选</div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <el-card class="card" shadow="never">
          <template #header>
            <div class="items-header">
              <div>
                <span class="title">申请明细</span>
                <span class="desc">主设备按“台”计数；辅料按数量计数</span>
              </div>
              <el-button type="primary" plain @click="addItemRow">
                <el-icon><Plus /></el-icon>
                添加一行
              </el-button>
            </div>
          </template>

          <el-table :data="createForm.items" style="width: 100%" empty-text="请添加明细">
            <el-table-column label="物料" min-width="320">
              <template #default="{ row }">
                <el-select
                  v-model="row.equipment"
                  value-key="id"
                  filterable
                  clearable
                  placeholder="选择物料"
                  @change="onEquipChange(row)"
                >
                  <el-option
                    v-for="eq in equipmentOptions"
                    :key="eq.id"
                    :label="`${eq.equipment_name}（${eq.equipment_code}）`"
                    :value="eq"
                  />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="类别" width="120">
              <template #default="{ row }">
                <el-tag :type="row.category === 'main_device' ? 'warning' : (row.category === 'auxiliary' ? 'info' : '')" effect="plain">
                  {{ row.category === 'main_device' ? '主设备' : (row.category === 'auxiliary' ? '辅料' : '-') }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="数量" width="160">
              <template #default="{ row }">
                <el-input-number v-model="row.quantity" :min="1" :max="99999" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ $index }">
                <el-button type="danger" link @click="removeItemRow($index)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="footer-actions">
            <el-button @click="createVisible = false">取消</el-button>
            <el-button :loading="creating" @click="create(false)">保存草稿</el-button>
            <el-button type="primary" :loading="creating" @click="create(true)">创建并提交</el-button>
          </div>
        </el-card>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../../stores/user'
import { stockApi } from '../../api/stock'
import { equipmentApi } from '../../api/equipment'
import { userAPI } from '../../api/user'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const records = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filters = ref({
  status_filter: '',
  warehouse_id: undefined,
  keyword: '',
})

const warehouses = ref([])
const equipmentOptions = ref([])
const packages = ref([])

const createVisible = ref(false)
const creating = ref(false)

const isCompactTable = ref(typeof window !== 'undefined' ? window.innerWidth <= 980 : false)
const syncCompactTable = () => {
  if (typeof window === 'undefined') return
  isCompactTable.value = window.innerWidth <= 980
}
const createForm = ref({
  requester: null,
  warehouse_id: undefined,
  notes: '',
  items: [],
})

const selectedPackage = ref(null)
const packageCount = ref(1)
const selectedPackageMainQty = computed(() => {
  const pkg = selectedPackage.value
  if (!pkg) return 0

  const directQty = Number(pkg.main_equipment_quantity || 0)
  if (Number.isFinite(directQty) && directQty > 0) {
    return Math.floor(directQty)
  }

  const mainId = Number(pkg.main_equipment_id || 0)
  if (!mainId) return 1

  const mainRow = (pkg.items || []).find((it) => Number(it?.equipment_id || 0) === mainId)
  const rowQty = Number(mainRow?.quantity || 0)
  if (Number.isFinite(rowQty) && rowQty > 0) {
    return Math.floor(rowQty)
  }
  return 1
})
const selectedPackageMainTotal = computed(() => {
  const count = Math.max(1, Number(packageCount.value || 1))
  return Math.max(0, Number(selectedPackageMainQty.value || 0)) * count
})
const selectedPackageAuxLineCount = computed(() => {
  const pkg = selectedPackage.value
  if (!pkg) return 0
  const mainId = Number(pkg.main_equipment_id || 0)
  return (pkg.items || []).filter((it) => {
    const equipmentId = Number(it?.equipment_id || 0)
    if (mainId > 0 && equipmentId === mainId) return false
    if (String(it?.category || '').trim() === 'main_device') return false
    return true
  }).length
})

const userSearching = ref(false)
const userOptions = ref([])

const isWarehouseOperator = computed(() => ['admin', 'manager', 'warehouse_manager'].includes(userStore.user?.role))

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
    abandoned: '已放弃',
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
    abandoned: 'danger',
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

const loadBaseOptions = async () => {
  try {
    const [whRes, eqRes, pkgRes] = await Promise.all([
      stockApi.getWarehouses(),
      equipmentApi.getEquipmentList({ status: 'active', limit: 1000 }),
      equipmentApi.getPackageList({ skip: 0, limit: 200 }),
    ])
    warehouses.value = whRes?.warehouses || []
    equipmentOptions.value = Array.isArray(eqRes) ? eqRes : (eqRes?.data || [])
    packages.value = Array.isArray(pkgRes) ? pkgRes : []
  } catch (error) {
    console.error('加载选项失败:', error)
    ElMessage.error('加载基础数据失败')
  }
}

const load = async () => {
  try {
    loading.value = true
    const params = {
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    }
    if (filters.value.status_filter) params.status_filter = filters.value.status_filter
    if (filters.value.warehouse_id) params.warehouse_id = filters.value.warehouse_id
    if (filters.value.keyword?.trim()) params.keyword = filters.value.keyword.trim()

    const res = await stockApi.listMaterialRequests(params)
    records.value = res?.records || []
    total.value = res?.total || 0
  } catch (error) {
    console.error('加载申请单失败:', error)
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
  router.push({ name: 'MaterialRequestDetail', params: { id } })
}

const openCreate = () => {
  createForm.value = {
    requester: null,
    warehouse_id: undefined,
    notes: '',
    items: [],
  }
  selectedPackage.value = null
  packageCount.value = 1
  userOptions.value = []
  createVisible.value = true
}

const addItemRow = () => {
  createForm.value.items.push({
    equipment: null,
    category: '',
    quantity: 1,
  })
}

const removeItemRow = (idx) => {
  createForm.value.items.splice(idx, 1)
}

const onEquipChange = (row) => {
  row.category = row?.equipment?.category || ''
  if (!row.quantity || row.quantity < 1) row.quantity = 1
}

const searchUsers = async (query) => {
  const kw = (query || '').trim()
  if (!kw) {
    userOptions.value = []
    return
  }
  try {
    userSearching.value = true
    const res = await userAPI.searchUsers({ keyword: kw, limit: 20 })
    userOptions.value = res?.users || []
  } catch (error) {
    console.error('搜索用户失败:', error)
    userOptions.value = []
  } finally {
    userSearching.value = false
  }
}

const _mergeItems = (incoming) => {
  const map = new Map()
  for (const row of createForm.value.items) {
    const eq = row?.equipment
    if (!eq?.id) continue
    const key = String(eq.id)
    const prev = map.get(key) || { equipment: eq, quantity: 0 }
    map.set(key, { equipment: eq, quantity: (prev.quantity || 0) + Number(row.quantity || 0) })
  }
  for (const it of incoming) {
    if (!it?.equipment?.id) continue
    const key = String(it.equipment.id)
    const prev = map.get(key) || { equipment: it.equipment, quantity: 0 }
    map.set(key, { equipment: it.equipment, quantity: (prev.quantity || 0) + Number(it.quantity || 0) })
  }
  createForm.value.items = Array.from(map.values()).map((v) => ({
    equipment: v.equipment,
    category: v.equipment?.category || '',
    quantity: Math.max(1, Number(v.quantity || 1)),
  }))
}

const applyPackage = () => {
  const pkg = selectedPackage.value
  if (!pkg) return
  const count = Math.max(1, Number(packageCount.value || 1))
  const incoming = []
  const mainEquipmentId = Number(pkg.main_equipment_id || 0)
  let hasMainInItems = false

  for (const it of pkg.items || []) {
    const equipmentId = Number(it?.equipment_id || 0)
    if (mainEquipmentId > 0 && equipmentId === mainEquipmentId) {
      hasMainInItems = true
    }
    const eq = equipmentOptions.value.find((e) => e.id === it.equipment_id)
    if (!eq) continue
    const qty = Math.max(0, Number(it.quantity || 0)) * count
    if (qty <= 0) continue
    incoming.push({ equipment: eq, quantity: qty })
  }

  // 兼容历史套装：若 items 中缺主设备，按 main_equipment_quantity（缺省 1）补齐
  if (!hasMainInItems && mainEquipmentId > 0) {
    const mainEq = equipmentOptions.value.find((e) => Number(e.id) === mainEquipmentId)
    if (mainEq) {
      const singleMainQty = Math.max(1, Number(pkg.main_equipment_quantity || 1))
      incoming.push({ equipment: mainEq, quantity: singleMainQty * count })
    }
  }

  _mergeItems(incoming)
  ElMessage.success('已应用套装到明细')
}

const _buildCreatePayload = () => {
  const requester = createForm.value.requester
  const warehouse_id = createForm.value.warehouse_id
  if (!requester?.id) throw new Error('请选择申请人')
  if (!warehouse_id) throw new Error('请选择发料仓库')

  const merged = new Map()
  for (const row of createForm.value.items) {
    const eq = row?.equipment
    if (!eq?.id) continue
    const qty = Number(row.quantity || 0)
    if (qty <= 0) continue
    merged.set(eq.id, (merged.get(eq.id) || 0) + qty)
  }
  if (merged.size === 0) throw new Error('请至少添加一条明细')

  return {
    warehouse_id,
    requester_id: requester.id,
    notes: (createForm.value.notes || '').trim(),
    items: Array.from(merged.entries()).map(([equipment_id, quantity]) => ({ equipment_id, quantity })),
  }
}

const create = async (submitAfterCreate) => {
  try {
    creating.value = true
    const payload = _buildCreatePayload()
    const res = await stockApi.createMaterialRequest(payload)
    const requestId = res?.request?.id

    if (submitAfterCreate && requestId) {
      await stockApi.submitMaterialRequest(requestId)
      ElMessage.success('创建并提交成功')
    } else {
      ElMessage.success('创建成功（草稿）')
    }

    createVisible.value = false
    await resetAndLoad()
    if (requestId) goDetail({ id: requestId })
  } catch (error) {
    console.error('创建申请失败:', error)
    ElMessage.error(extractError(error) || error?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', syncCompactTable, { passive: true })
    syncCompactTable()
  }
  await loadBaseOptions()
  await load()
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', syncCompactTable)
  }
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
    radial-gradient(900px 180px at 10% 0%, rgba(249, 115, 22, 0.16), transparent 60%),
    radial-gradient(800px 220px at 90% 20%, rgba(59, 130, 246, 0.10), transparent 55%);
  pointer-events: none;
}

.quick-hint {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.hint-chip {
  position: relative;
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
  background: radial-gradient(circle at 30% 30%, #fff, var(--primary-color));
  box-shadow: 0 0 0 4px rgba(249, 115, 22, 0.18);
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.drawer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px 22px;
  border-bottom: 1px solid var(--border-color);
  background:
    radial-gradient(900px 260px at 10% 0%, rgba(249, 115, 22, 0.16), transparent 60%),
    radial-gradient(1000px 320px at 90% 20%, rgba(59, 130, 246, 0.10), transparent 60%);
}

.drawer-title {
  margin: 0;
  font-size: 18px;
  letter-spacing: 0.2px;
}

.drawer-sub {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
}

.drawer-body {
  padding: 18px 22px 28px;
}

.glass-card {
  border-radius: 14px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(10px);
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.field .label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.field.span2 {
  grid-column: span 2;
}

.quickfill {
  margin-top: 16px;
  border-radius: 14px;
  border: 1px dashed rgba(249, 115, 22, 0.35);
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.9), rgba(255, 255, 255, 0.9));
}

.quickfill-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.quickfill-header .title {
  font-weight: 600;
}

.quickfill-header .desc {
  margin-left: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}

.pkg-preview {
  display: flex;
  justify-content: flex-end;
}

.preview {
  display: flex;
  gap: 8px;
  align-items: center;
}

.pill {
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(249, 115, 22, 0.25);
  background: rgba(255, 255, 255, 0.65);
  color: #9a3412;
  font-size: 12px;
}

.muted {
  color: var(--text-secondary);
  font-size: 12px;
}

.items-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.items-header .title {
  font-weight: 600;
}

.items-header .desc {
  margin-left: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 14px;
}

@media (max-width: 980px) {
  .filters-card :deep(.el-row) {
    row-gap: 10px;
  }

  .quick-hint {
    justify-content: flex-start;
  }

  .hint-chip {
    width: 100%;
    border-radius: 12px;
  }

  .grid {
    grid-template-columns: 1fr;
  }
  .field.span2 {
    grid-column: span 1;
  }
}
</style>
