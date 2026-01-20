<template>
  <div class="page-container">
    <div class="page-header">
      <div class="title-block">
        <h2>快速出库（无申请）</h2>
        <div class="subtitle">仅仓库/管理员使用：主设备逐台 SN，辅料手选数量</div>
      </div>
      <div class="header-actions">
        <el-button @click="reset" :disabled="submitting">
          <el-icon><Refresh /></el-icon>
          清空
        </el-button>
        <el-button type="primary" :loading="submitting" @click="submit">
          <el-icon><Upload /></el-icon>
          出库
        </el-button>
      </div>
    </div>

    <el-card class="card hero" shadow="never">
      <div class="hero-grid">
        <div class="hero-left">
          <div class="grid">
            <div class="field">
              <div class="label">出库仓库</div>
              <el-select v-model="form.warehouse_id" filterable clearable placeholder="选择仓库">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
              </el-select>
            </div>
            <div class="field">
              <div class="label">领取人（必选）</div>
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
            <div class="field span2">
              <div class="label">备注</div>
              <el-input v-model="form.notes" placeholder="可选：原因/项目/紧急程度" clearable />
            </div>
          </div>
        </div>

        <div class="hero-right">
          <div class="stat">
            <div class="k">主设备 SN</div>
            <div class="v">{{ snList.length }}</div>
          </div>
          <div class="stat">
            <div class="k">辅料行数</div>
            <div class="v">{{ auxRows.length }}</div>
          </div>
          <div class="stat accent">
            <div class="k">本次总数量</div>
            <div class="v">{{ totalQty }}</div>
          </div>
        </div>
      </div>
    </el-card>

    <div class="content-grid">
      <el-card class="card" shadow="never">
        <template #header>
          <div class="section-header">
            <div class="section-title">
              <span class="title">主设备（SN）</span>
              <span class="desc">支持扫码枪逐条录入，也支持粘贴多行</span>
            </div>
            <div class="section-actions">
              <el-button @click="clearSns" :disabled="snList.length === 0">清空SN</el-button>
            </div>
          </div>
        </template>

        <div class="sn-inputs">
          <el-input
            v-model="snScanInput"
            placeholder="扫码录入 SN 后回车"
            clearable
            @keyup.enter="addSnFromInput"
          >
            <template #prefix>
              <el-icon><Aim /></el-icon>
            </template>
            <template #append>
              <el-button @click="addSnFromInput">添加</el-button>
            </template>
          </el-input>

          <el-input
            v-model="snTextarea"
            type="textarea"
            :rows="6"
            placeholder="可粘贴多行SN（每行一个），点击“解析加入”"
          />

          <div class="sn-actions">
            <el-button @click="parseTextarea">解析加入</el-button>
            <div class="sn-tip">已自动去重；空行会忽略</div>
          </div>
        </div>

        <div class="sn-list">
          <el-tag
            v-for="sn in snList"
            :key="sn"
            closable
            @close="removeSn(sn)"
            class="sn-tag"
          >
            {{ sn }}
          </el-tag>
          <div v-if="snList.length === 0" class="empty">暂无SN</div>
        </div>
      </el-card>

      <el-card class="card aux" shadow="never">
        <template #header>
          <div class="section-header">
            <div class="section-title">
              <span class="title">辅料</span>
              <span class="desc">辅料不可扫码：选择物料 + 数量</span>
            </div>
            <div class="section-actions">
              <el-button type="primary" plain @click="addAuxRow">
                <el-icon><Plus /></el-icon>
                添加辅料
              </el-button>
              <el-button @click="clearAux" :disabled="auxRows.length === 0">清空</el-button>
            </div>
          </div>
        </template>

        <el-table :data="auxRows" style="width: 100%">
          <el-table-column label="辅料" min-width="260">
            <template #default="{ row }">
              <el-select
                v-model="row.equipment"
                value-key="id"
                filterable
                clearable
                placeholder="选择辅料"
              >
                <el-option
                  v-for="eq in auxEquipmentOptions"
                  :key="eq.id"
                  :label="`${eq.equipment_name}（${eq.equipment_code}）`"
                  :value="eq"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="数量" width="160">
            <template #default="{ row }">
              <el-input-number v-model="row.quantity" :min="1" :max="99999" controls-position="right" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ $index }">
              <el-button type="danger" link @click="removeAuxRow($index)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

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
import { ElMessage } from 'element-plus'
import { stockApi } from '../../api/stock'
import { equipmentApi } from '../../api/equipment'
import { userAPI } from '../../api/user'

const warehouses = ref([])
const equipmentOptions = ref([])

const form = ref({
  warehouse_id: undefined,
  issued_to_user: null,
  notes: '',
})

const snScanInput = ref('')
const snTextarea = ref('')
const snList = ref([])

const auxRows = ref([])

const submitting = ref(false)

const userSearching = ref(false)
const userOptions = ref([])

const shortagesVisible = ref(false)
const shortages = ref([])

const auxEquipmentOptions = computed(() => {
  return equipmentOptions.value.filter(e => e.category === 'auxiliary')
})

const auxConfirmTotal = computed(() => {
  return auxRows.value.reduce((s, r) => s + Number(r.quantity || 0), 0)
})

const totalQty = computed(() => snList.value.length + auxConfirmTotal.value)

const extractError = (error) => {
  const detail = error?.response?.data?.detail
  if (!detail) return { message: error?.message || '操作失败' }
  if (typeof detail === 'string') return { message: detail }
  return { message: detail?.message || '操作失败', shortages: detail?.shortages }
}

const loadBaseOptions = async () => {
  try {
    const [whRes, eqRes] = await Promise.all([
      stockApi.getWarehouses(),
      equipmentApi.getEquipmentList({ status: 'active', limit: 2000 }),
    ])
    warehouses.value = whRes?.warehouses || []
    equipmentOptions.value = Array.isArray(eqRes) ? eqRes : []
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

const normalizeSn = (raw) => String(raw || '').trim()

const addSn = (sn) => {
  const value = normalizeSn(sn)
  if (!value) return
  if (!snList.value.includes(value)) snList.value.push(value)
}

const addSnFromInput = () => {
  addSn(snScanInput.value)
  snScanInput.value = ''
}

const parseTextarea = () => {
  const lines = String(snTextarea.value || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean)
  for (const line of lines) addSn(line)
  snTextarea.value = ''
  ElMessage.success('已加入SN列表')
}

const removeSn = (sn) => {
  snList.value = snList.value.filter(s => s !== sn)
}

const clearSns = () => {
  snList.value = []
  snScanInput.value = ''
  snTextarea.value = ''
}

const addAuxRow = () => {
  auxRows.value.push({ equipment: null, quantity: 1 })
}

const removeAuxRow = (idx) => {
  auxRows.value.splice(idx, 1)
}

const clearAux = () => {
  auxRows.value = []
}

const reset = () => {
  form.value = { warehouse_id: undefined, issued_to_user: null, notes: '' }
  clearSns()
  clearAux()
  shortagesVisible.value = false
  shortages.value = []
}

const buildPayload = () => {
  const warehouse_id = Number(form.value.warehouse_id || 0)
  if (!warehouse_id) throw new Error('请选择出库仓库')
  const issued_to = Number(form.value.issued_to_user?.id || 0)
  if (!issued_to) throw new Error('请选择领取人')
  const main_sns = snList.value.slice()
  const aux_map = new Map()
  for (const row of auxRows.value) {
    const eq = row?.equipment
    if (!eq?.id) continue
    const qty = Number(row.quantity || 0)
    if (qty <= 0) continue
    aux_map.set(eq.id, (aux_map.get(eq.id) || 0) + qty)
  }
  if (main_sns.length === 0 && aux_map.size === 0) throw new Error('请至少录入1个主设备SN或辅料数量')

  return {
    warehouse_id,
    main_sns,
    aux_items: Array.from(aux_map.entries()).map(([equipment_id, quantity]) => ({ equipment_id, quantity })),
    issued_to,
    notes: (form.value.notes || '').trim(),
  }
}

const submit = async () => {
  try {
    submitting.value = true
    const payload = buildPayload()
    const res = await stockApi.manualStockOut(payload)
    ElMessage.success(`出库成功：${res?.document_number || ''}`)
    reset()
  } catch (error) {
    console.error('快速出库失败:', error)
    const parsed = extractError(error)
    if (parsed?.shortages && Array.isArray(parsed.shortages)) {
      shortages.value = parsed.shortages
      shortagesVisible.value = true
    }
    ElMessage.error(parsed.message)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await loadBaseOptions()
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

.hero {
  border-radius: 16px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background:
    radial-gradient(1000px 360px at 10% 0%, rgba(249, 115, 22, 0.16), transparent 60%),
    radial-gradient(1100px 420px at 90% 30%, rgba(59, 130, 246, 0.08), transparent 60%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.98));
}

.hero-grid {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 18px;
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
  font-weight: 800;
  letter-spacing: 0.2px;
}

.stat.accent {
  grid-column: span 2;
  border: 1px solid rgba(249, 115, 22, 0.22);
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.9), rgba(255, 255, 255, 0.9));
}

.content-grid {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
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

.sn-inputs {
  display: grid;
  gap: 12px;
}

.sn-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.sn-tip {
  color: var(--text-secondary);
  font-size: 12px;
}

.sn-list {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sn-tag {
  border-radius: 999px;
}

.empty {
  color: var(--text-secondary);
  font-size: 12px;
  padding: 8px 0;
}

.aux {
  border-radius: 16px;
  border: 1px solid rgba(59, 130, 246, 0.12);
  background:
    radial-gradient(900px 240px at 90% 0%, rgba(59, 130, 246, 0.10), transparent 55%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.98));
}

@media (max-width: 1200px) {
  .hero-grid {
    grid-template-columns: 1fr;
  }
  .grid {
    grid-template-columns: 1fr;
  }
  .field.span2 {
    grid-column: span 1;
  }
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
