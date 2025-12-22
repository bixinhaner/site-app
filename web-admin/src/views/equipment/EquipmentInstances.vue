<template>
  <div class="page">
    <div class="page-header">
      <h1>设备实例清单</h1>
      <div class="header-actions">
        <el-select v-model="selectedEquipmentId" filterable clearable placeholder="设备类型" style="width: 320px" @visible-change="v=> v && loadEquipments()">
          <el-option v-for="eq in equipmentOptions" :key="eq.id" :label="`${eq.equipment_name} (${eq.equipment_code})`" :value="eq.id" />
        </el-select>
        <el-select v-model="status" clearable placeholder="状态" style="width: 160px">
          <el-option label="库存中" value="in_stock" />
          <el-option label="已分配" value="allocated" />
          <el-option label="已出库" value="issued" />
          <el-option label="已退库" value="returned" />
        </el-select>
        <el-checkbox v-model="includeVoided">显示已撤销</el-checkbox>
        <el-input v-model="keyword" placeholder="搜索SN/条码/供应商" clearable style="width: 220px" />
        <el-button type="primary" @click="load"><el-icon><Search /></el-icon>查询</el-button>
      </div>
    </div>
    <el-card>
      <el-table :data="displayedItems" v-loading="loading" stripe>
        <el-table-column prop="serial_number" label="SN" width="220">
          <template #default="{ row }">
            <el-space>
              <span>{{ row.serial_number }}</span>
              <el-tag v-if="row.is_voided" size="small" type="info">已撤销</el-tag>
              <el-button text size="small" @click="copy(row.serial_number)">复制</el-button>
            </el-space>
          </template>
        </el-table-column>
        <el-table-column prop="barcode" label="条码" width="200" />
        <el-table-column prop="vendor" label="供应商" width="140" />
        <el-table-column label="所在仓库" width="220">
          <template #default="{ row }">
            <span>{{ formatWarehouseDisplay(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="绑定信息" width="300">
          <template #default="{ row }">
            <el-space direction="vertical" :size="2" style="width: 100%">
              <el-tag v-if="row.binding_info" type="success" size="small">
                {{ row.binding_info.site_name }} - {{ row.binding_info.cell_id }}
              </el-tag>
              <el-button 
                v-if="row.serial_number" 
                text 
                type="primary" 
                size="small" 
                @click="showBindingHistory(row)"
              >
                <el-icon><Document /></el-icon> 查看历史
              </el-button>
            </el-space>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              text
              @click="openEdit(row)"
            >
              编辑信息
            </el-button>
            <el-button
              size="small"
              type="danger"
              text
              :disabled="row.is_voided || row.status !== 'in_stock'"
              @click="openVoid(row)"
            >
              撤销入库
            </el-button>
            <el-button
              size="small"
              type="primary"
              text
              :disabled="row.is_voided"
              @click="gotoLifecycle(row)"
            >
              设备跟踪
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑设备信息 -->
    <el-dialog v-model="editVisible" title="编辑设备信息" width="600px">
      <el-form label-width="90px">
        <el-form-item label="SN">
          <el-input :model-value="editSn" disabled />
        </el-form-item>
        <el-form-item label="供应商">
          <el-input v-model="editForm.vendor" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="editForm.batch_number" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="MAC">
          <el-input v-model="editForm.mac_address" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="IMEI">
          <el-input v-model="editForm.imei" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="固件版本">
          <el-input v-model="editForm.firmware_version" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="硬件版本">
          <el-input v-model="editForm.hardware_version" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="库位">
          <el-input v-model="editForm.location" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input v-model="editForm.reason" placeholder="请填写修改原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 撤销入库 -->
    <el-dialog v-model="voidVisible" title="撤销入库" width="520px">
      <el-form label-width="90px">
        <el-form-item label="SN">
          <el-input :model-value="voidSn" disabled />
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input v-model="voidForm.reason" placeholder="请填写撤销原因" />
        </el-form-item>
        <el-alert
          type="warning"
          :closable="false"
          title="撤销会释放 SN 以便重导，并生成“调整”记录。"
        />
      </el-form>
      <template #footer>
        <el-button @click="voidVisible = false">取消</el-button>
        <el-button type="danger" :loading="voidSubmitting" @click="submitVoid">确认撤销</el-button>
      </template>
    </el-dialog>
    
    <!-- 绑定历史弹窗（改为生命周期视图） -->
    <el-dialog
      v-model="historyDialogVisible"
      title="设备生命周期"
      width="70%"
      top="5vh"
    >
      <EquipmentLifecycleTimeline
        v-if="currentEquipment && currentEquipment.serial_number"
        :sn="currentEquipment.serial_number"
      />
      <el-empty
        v-else
        description="未找到设备序列号，无法查询生命周期"
      />
    </el-dialog>
  </div>
  
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { stockApi } from '../../api/stock'
import { ElMessage } from 'element-plus'
import { equipmentApi } from '../../api/equipment'
import { Document } from '@element-plus/icons-vue'
import EquipmentLifecycleTimeline from '@/components/equipment/EquipmentLifecycleTimeline.vue'

const router = useRouter()

const loading = ref(false)
const selectedEquipmentId = ref('')
const status = ref('')
const items = ref([])
const keyword = ref('')
const equipmentOptions = ref([])
const includeVoided = ref(false)

const editVisible = ref(false)
const editSubmitting = ref(false)
const editingRow = ref(null)
const editForm = ref({
  vendor: '',
  batch_number: '',
  mac_address: '',
  imei: '',
  firmware_version: '',
  hardware_version: '',
  location: '',
  reason: '',
})

const voidVisible = ref(false)
const voidSubmitting = ref(false)
const voidingRow = ref(null)
const voidForm = ref({ reason: '' })

const editSn = computed(() => editingRow.value?.serial_number || '-')
const voidSn = computed(() => voidingRow.value?.serial_number || '-')

// 绑定历史 / 生命周期弹窗相关
const historyDialogVisible = ref(false)
const currentEquipment = ref(null)

const load = async () => {
  if (!selectedEquipmentId.value) {
    ElMessage.info('请输入设备类型ID')
    return
  }
  try {
    loading.value = true
    const params = {}
    if (status.value) params.status = status.value
    if (includeVoided.value) params.include_voided = true
    const res = await stockApi.getEquipmentInstances(selectedEquipmentId.value, params)
    items.value = res?.instances || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载设备实例失败')
  } finally {
    loading.value = false
  }
}

const displayedItems = computed(() => {
  if (!keyword.value) return items.value
  const kw = keyword.value.toLowerCase()
  return items.value.filter(i =>
    (i.serial_number || '').toLowerCase().includes(kw) ||
    (i.barcode || '').toLowerCase().includes(kw) ||
    (i.vendor || '').toLowerCase().includes(kw)
  )
})

const formatWarehouseDisplay = (row) => {
  if (!row) return '-'
  if (row.warehouse_id !== undefined && row.warehouse_id !== null) {
    return row.warehouse_name || '-'
  }
  if (row.warehouse_id === null) {
    if (row.last_warehouse_name) return `已出库（上个仓库：${row.last_warehouse_name}）`
    return '已出库'
  }
  return row.warehouse_name || row.last_warehouse_name || '-'
}

const loadEquipments = async () => {
  try {
    const res = await equipmentApi.getEquipmentList({ limit: 200 })
    equipmentOptions.value = res || []
  } catch (e) {
    console.error(e)
  }
}

const copy = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch (e) {
    ElMessage.error('复制失败')
  }
}

// 跳转到设备生命周期追踪页面，并自动带入 SN
const gotoLifecycle = (row) => {
  if (!row?.serial_number) {
    ElMessage.warning('该实例缺少 SN，无法追踪')
    return
  }
  router.push({
    name: 'EquipmentLifecycle',
    query: { sn: row.serial_number }
  })
}

// 显示设备生命周期（使用与生命周期页面一致的视图）
const showBindingHistory = (equipment) => {
  currentEquipment.value = equipment
  historyDialogVisible.value = true
}

const openEdit = (row) => {
  if (!row || row.is_voided) {
    ElMessage.warning('已撤销实例不可编辑')
    return
  }
  editingRow.value = row
  editForm.value = {
    vendor: row.vendor || '',
    batch_number: row.batch_number || '',
    mac_address: row.mac_address || '',
    imei: row.imei || '',
    firmware_version: row.firmware_version || '',
    hardware_version: row.hardware_version || '',
    location: row.location || '',
    reason: '',
  }
  editVisible.value = true
}

const submitEdit = async () => {
  const row = editingRow.value
  if (!row) return
  if (!editForm.value.reason?.trim()) {
    ElMessage.warning('请填写修改原因')
    return
  }
  try {
    editSubmitting.value = true
    await stockApi.updateEquipmentInstance(row.id, {
      vendor: editForm.value.vendor,
      batch_number: editForm.value.batch_number,
      mac_address: editForm.value.mac_address,
      imei: editForm.value.imei,
      firmware_version: editForm.value.firmware_version,
      hardware_version: editForm.value.hardware_version,
      location: editForm.value.location,
      reason: editForm.value.reason,
    })
    ElMessage.success('设备信息已更新')
    editVisible.value = false
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '更新失败')
  } finally {
    editSubmitting.value = false
  }
}

const openVoid = (row) => {
  if (!row || row.is_voided) return
  voidingRow.value = row
  voidForm.value = { reason: '' }
  voidVisible.value = true
}

const submitVoid = async () => {
  const row = voidingRow.value
  if (!row) return
  if (!voidForm.value.reason?.trim()) {
    ElMessage.warning('请填写撤销原因')
    return
  }
  try {
    voidSubmitting.value = true
    const res = await stockApi.voidInstances({
      instance_ids: [row.id],
      reason: voidForm.value.reason
    })
    const ok = (res?.success_count || 0) > 0
    if (!ok) {
      const firstErr = res?.results?.find((r) => !r.success)?.error
      ElMessage.error(firstErr || '撤销失败')
      return
    }
    ElMessage.success('撤销成功')
    voidVisible.value = false
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '撤销失败')
  } finally {
    voidSubmitting.value = false
  }
}
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
</style>
