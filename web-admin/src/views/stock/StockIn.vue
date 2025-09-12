<template>
  <div class="page-container">
    <div class="page-header">
      <h2>入库管理</h2>
    </div>

    <!-- 选择入库方式 -->
    <el-card class="method-selector">
      <el-radio-group v-model="stockInMethod" @change="handleMethodChange">
        <el-radio-button label="manual">手动入库</el-radio-button>
        <el-radio-button label="batch_import">SN批量导入</el-radio-button>
      </el-radio-group>
    </el-card>

    <!-- 手动入库表单 -->
    <div v-if="stockInMethod === 'manual'" class="manual-stock-in">
      <!-- 入库单据表单 -->
    <div class="card">
      <h3>新建入库单</h3>
      
      <el-form :model="stockInForm" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="入库仓库" required>
              <el-select v-model="stockInForm.warehouse_id" placeholder="选择仓库">
                <el-option 
                  v-for="warehouse in warehouseOptions" 
                  :key="warehouse.id" 
                  :label="warehouse.warehouse_name" 
                  :value="warehouse.id" 
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="入库类型">
              <el-select v-model="stockInForm.in_type">
                <el-option label="采购入库" value="purchase" />
                <el-option label="调拨入库" value="transfer" />
                <el-option label="退料入库" value="return" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="备注说明">
          <el-input v-model="stockInForm.notes" type="textarea" :rows="2" placeholder="入库说明..." />
        </el-form-item>
      </el-form>
    </div>

    <!-- 入库明细 -->
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h3>入库明细</h3>
        <el-button size="small" @click="addStockInItem">
          <el-icon><Plus /></el-icon>
          添加设备
        </el-button>
      </div>
      
      <el-table :data="stockInForm.items" border size="small">
        <el-table-column label="设备" width="200">
          <template #default="{ row, $index }">
            <el-select v-model="row.equipment_id" placeholder="选择设备" @change="onEquipmentChange(row, $index)">
              <el-option 
                v-for="eq in equipmentOptions" 
                :key="eq.id" 
                :label="`${eq.equipment_name} (${eq.equipment_code})`" 
                :value="eq.id"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="120">
          <template #default="{ row }">
            <el-input-number v-model="row.quantity" :min="1" size="small" @change="calculateTotal" />
          </template>
        </el-table-column>
        <el-table-column label="单位" width="80">
          <template #default="{ row }">
            <span>{{ getEquipmentUnit(row.equipment_id) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="单价" width="120">
          <template #default="{ row }">
            <el-input-number v-model="row.unit_price" :min="0" :precision="2" size="small" @change="calculateTotal" />
          </template>
        </el-table-column>
        <el-table-column label="批次号" width="120">
          <template #default="{ row }">
            <el-input v-model="row.batch_number" size="small" placeholder="可选" />
          </template>
        </el-table-column>
        <el-table-column label="小计" width="120">
          <template #default="{ row }">
            ¥{{ ((row.quantity || 0) * (row.unit_price || 0)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row, $index }">
            <el-button size="small" type="danger" @click="removeStockInItem($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div style="margin-top: 16px; text-align: right;">
        <span style="font-size: 16px; font-weight: 600;">
          总金额: ¥{{ totalAmount.toFixed(2) }}
        </span>
      </div>
      
      <div style="margin-top: 20px; text-align: center;">
        <el-button @click="resetForm">重置</el-button>
        <el-button type="primary" @click="submitStockIn" :loading="submitting" :disabled="stockInForm.items.length === 0">
          提交入库
        </el-button>
      </div>
    </div>
    </div>

    <!-- SN批量导入表单 -->
    <div v-if="stockInMethod === 'batch_import'" class="batch-import-section">
      <!-- 基本信息 -->
      <el-card class="import-form-card">
        <template #header>
          <span>批量导入设置</span>
        </template>
        
        <el-form :model="importForm" label-width="120px">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="设备类型" required>
                <el-select v-model="importForm.equipment_type_id" placeholder="选择要导入的设备类型" style="width: 100%">
                  <el-option 
                    v-for="eq in mainDeviceOptions" 
                    :key="eq.id" 
                    :label="`${eq.equipment_name} (${eq.equipment_code})`" 
                    :value="eq.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="目标仓库" required>
                <el-select v-model="importForm.warehouse_id" placeholder="选择仓库" style="width: 100%">
                  <el-option 
                    v-for="warehouse in warehouseOptions" 
                    :key="warehouse.id" 
                    :label="warehouse.warehouse_name" 
                    :value="warehouse.id" 
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <!-- 文件上传 -->
      <el-card class="upload-card">
        <template #header>
          <div class="upload-header">
            <span>Excel文件上传</span>
            <el-button size="small" @click="downloadTemplate" type="success">
              <el-icon><Download /></el-icon>
              下载模板
            </el-button>
          </div>
        </template>

        <el-upload
          ref="uploadRef"
          class="upload-demo"
          drag
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          :before-upload="beforeUpload"
          :auto-upload="false"
          accept=".xlsx,.xls"
          :limit="1"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            将Excel文件拖到此处，或<em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              只能上传 xlsx/xls 文件，请先下载模板查看格式要求
            </div>
          </template>
        </el-upload>
      </el-card>

      <!-- 数据预览 -->
      <el-card v-if="previewData.length > 0" class="preview-card">
        <template #header>
          <span>数据预览</span>
          <el-tag type="info" size="small" style="margin-left: 10px">共 {{ previewData.length }} 条数据</el-tag>
        </template>

        <el-table :data="previewData.slice(0, 10)" border size="small" max-height="400">
          <el-table-column prop="sn" label="SN序列号" width="180" />
          <el-table-column prop="mac_address" label="MAC地址" width="150" />
          <el-table-column prop="manufacture_date" label="生产日期" width="110" />
          <el-table-column prop="warranty_start_date" label="保修开始" width="110" />
          <el-table-column prop="warranty_end_date" label="保修截止" width="110" />
          <el-table-column prop="vendor" label="供应商" width="100" />
          <el-table-column prop="batch_number" label="批次号" width="120" />
          <el-table-column prop="notes" label="备注" min-width="100" />
        </el-table>
        
        <div v-if="previewData.length > 10" style="margin-top: 10px; text-align: center; color: #909399;">
          仅显示前10条数据，实际将导入 {{ previewData.length }} 条
        </div>
      </el-card>

      <!-- 导入按钮 -->
      <div style="margin-top: 20px; text-align: center;">
        <el-button @click="resetImport">重置</el-button>
        <el-button type="primary" @click="submitImport" :loading="importing" :disabled="!canImport">
          开始导入
        </el-button>
      </div>

      <!-- 导入结果 -->
      <el-card v-if="importResult" class="result-card">
        <template #header>
          <span>导入结果</span>
        </template>

        <div class="import-stats">
          <div class="stat-item">
            <span class="stat-label">总数量:</span>
            <span class="stat-value">{{ importResult.total_count }}</span>
          </div>
          <div class="stat-item success">
            <span class="stat-label">成功:</span>
            <span class="stat-value">{{ importResult.success_count }}</span>
          </div>
          <div class="stat-item warning" v-if="importResult.duplicate_count > 0">
            <span class="stat-label">重复:</span>
            <span class="stat-value">{{ importResult.duplicate_count }}</span>
          </div>
          <div class="stat-item error" v-if="importResult.failed_count > 0">
            <span class="stat-label">失败:</span>
            <span class="stat-value">{{ importResult.failed_count }}</span>
          </div>
        </div>

        <div style="margin-top: 15px;">
          <el-button size="small" @click="viewImportDetails" type="primary" link>
            查看详细结果
          </el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search, Warning, Download, UploadFilled } from '@element-plus/icons-vue'
import { stockApi } from '../../api/stock'
import { equipmentApi } from '../../api/equipment'
import { useUserStore } from '../../stores/user'
import * as XLSX from 'xlsx'

const userStore = useUserStore()

const loading = ref(false)
const submitting = ref(false)
const inventoryList = ref([])
const warehouseOptions = ref([])
const equipmentOptions = ref([])
const showLowStockOnly = ref(false)

// 新增批量导入相关状态
const stockInMethod = ref('manual')
const importing = ref(false)
const uploadRef = ref()
const importForm = ref({
  equipment_type_id: null,
  warehouse_id: 1
})
const previewData = ref([])
const importResult = ref(null)
const currentFile = ref(null)
const mainDeviceOptions = ref([])

const filters = ref({
  search: '',
  category: ''
})

const stockInForm = ref({
  warehouse_id: 1,
  in_type: 'purchase',
  notes: '',
  items: []
})

const filteredInventoryList = computed(() => {
  let list = inventoryList.value
  
  if (filters.value.search) {
    list = list.filter(item => 
      item.equipment_name.toLowerCase().includes(filters.value.search.toLowerCase()) ||
      item.equipment_code.toLowerCase().includes(filters.value.search.toLowerCase())
    )
  }
  
  if (filters.value.category) {
    list = list.filter(item => item.category === filters.value.category)
  }
  
  return list
})

const lowStockCount = computed(() => 
  inventoryList.value.filter(item => item.is_low_stock).length
)

const mainDeviceCount = computed(() => 
  inventoryList.value.filter(item => item.category === 'main_device').length
)

const auxiliaryCount = computed(() => 
  inventoryList.value.filter(item => item.category === 'auxiliary').length
)

const totalAmount = computed(() => 
  stockInForm.value.items.reduce((sum, item) => 
    sum + (item.quantity || 0) * (item.unit_price || 0), 0
  )
)

const getEquipmentUnit = (equipmentId) => {
  const equipment = equipmentOptions.value.find(eq => eq.id === equipmentId)
  return equipment?.unit || '台'
}

const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

const loadInventoryList = async () => {
  try {
    loading.value = true
    const params = {}
    if (showLowStockOnly.value) {
      params.low_stock_only = true
    }
    
    const response = await stockApi.getInventoryList(params)
    inventoryList.value = response.inventory || []
  } catch (error) {
    console.error('加载库存列表失败:', error)
    ElMessage.error('加载库存列表失败')
  } finally {
    loading.value = false
  }
}

const loadOptions = async () => {
  try {
    // 加载仓库选项
    const warehousesResponse = await stockApi.getWarehouses()
    warehouseOptions.value = warehousesResponse.warehouses || []
    
    // 加载设备选项
    const equipmentResponse = await equipmentApi.getEquipmentList({ status: 'active' })
    equipmentOptions.value = equipmentResponse || []
  } catch (error) {
    console.error('加载选项失败:', error)
  }
}

const addStockInItem = () => {
  stockInForm.value.items.push({
    equipment_id: null,
    quantity: 1,
    unit_price: 0,
    batch_number: ''
  })
}

const removeStockInItem = (index) => {
  stockInForm.value.items.splice(index, 1)
  calculateTotal()
}

const onEquipmentChange = (row, index) => {
  const equipment = equipmentOptions.value.find(eq => eq.id === row.equipment_id)
  if (equipment && equipment.standard_price) {
    row.unit_price = equipment.standard_price
    calculateTotal()
  }
}

const calculateTotal = () => {
  // 触发计算，computed会自动更新
}

const submitStockIn = async () => {
  if (stockInForm.value.items.length === 0) {
    ElMessage.warning('请至少添加一个入库明细')
    return
  }
  
  const hasEmptyItems = stockInForm.value.items.some(item => !item.equipment_id || !item.quantity)
  if (hasEmptyItems) {
    ElMessage.warning('请完善入库明细信息')
    return
  }
  
  try {
    await ElMessageBox.confirm('确认提交入库单据？', '提交确认')
    
    submitting.value = true
    const response = await stockApi.createStockIn(stockInForm.value)
    ElMessage.success('入库单据创建成功')
    
    resetForm()
    loadInventoryList()
  } catch (error) {
    if (error === 'cancel') return
    console.error('提交入库失败:', error)
    ElMessage.error('提交失败: ' + (error.response?.data?.detail || '网络错误'))
  } finally {
    submitting.value = false
  }
}

const resetForm = () => {
  stockInForm.value = {
    warehouse_id: 1,
    in_type: 'purchase',
    notes: '',
    items: []
  }
}

// 批量导入相关方法
const canImport = computed(() => {
  return importForm.value.equipment_type_id && 
         importForm.value.warehouse_id && 
         previewData.value.length > 0
})

const handleMethodChange = () => {
  // 切换方式时重置状态
  resetImport()
}

const downloadTemplate = async () => {
  try {
    // 使用带认证的API调用
    const response = await stockApi.downloadImportTemplate()
    
    // 创建blob对象 - 响应拦截器已返回data，所以直接使用response
    const blob = new Blob([response], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    
    // 创建下载链接
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'SN导入模板.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('模板下载成功')
  } catch (error) {
    ElMessage.error('模板下载失败: ' + (error.response?.data?.detail || error.message))
    console.error('下载模板失败:', error)
  }
}

const beforeUpload = () => {
  return false // 阻止自动上传
}

const handleFileChange = (file) => {
  currentFile.value = file.raw
  parseExcelFile(file.raw)
}

const handleFileRemove = () => {
  currentFile.value = null
  previewData.value = []
  importResult.value = null
}

const parseExcelFile = async (file) => {
  try {
    const reader = new FileReader()
    reader.onload = (e) => {
      const data = new Uint8Array(e.target.result)
      const workbook = XLSX.read(data, { type: 'array' })
      const sheetName = workbook.SheetNames[0]
      const worksheet = workbook.Sheets[sheetName]
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 })
      
      // 解析数据（跳过标题行）- 简化版字段
      const parsedData = []
      const duplicatesSN = new Set() // 文件内部重复SN检查
      const internalDuplicates = []
      
      for (let i = 1; i < jsonData.length; i++) {
        const row = jsonData[i]
        if (row.length > 0 && row[0]) { // 确保有SN数据
          const sn = String(row[0]).trim()
          
          // 检查文件内部重复
          if (duplicatesSN.has(sn)) {
            internalDuplicates.push({ sn, row: i + 1 })
          } else {
            duplicatesSN.add(sn)
          }
          
          parsedData.push({
            sn: sn,
            mac_address: row[1] || '',
            manufacture_date: row[2] || '',
            warranty_start_date: row[3] || '',
            warranty_end_date: row[4] || '',
            vendor: row[5] || '',
            batch_number: row[6] || '',
            notes: row[7] || ''
          })
        }
      }
      
      // 显示文件内部重复警告
      if (internalDuplicates.length > 0) {
        const duplicateInfo = internalDuplicates.map(d => `${d.sn}(行${d.row})`).join(', ')
        ElMessage.warning(`文件内检测到重复SN: ${duplicateInfo}`)
      }
      
      previewData.value = parsedData
      ElMessage.success(`已解析 ${parsedData.length} 条数据`)
    }
    reader.readAsArrayBuffer(file)
  } catch (error) {
    ElMessage.error('文件解析失败')
    console.error('解析Excel失败:', error)
  }
}

const submitImport = async () => {
  try {
    importing.value = true
    
    // 先执行批量SN检查
    ElMessage.info('正在检查SN重复情况...')
    const snList = previewData.value.map(item => item.sn)
    const checkResult = await stockApi.checkSNBatch(snList)
    
    // 显示检查结果
    const existingSNs = checkResult.results.filter(r => r.exists)
    if (existingSNs.length > 0) {
      const duplicateInfo = existingSNs.map(item => 
        `${item.sn} (${item.equipment_name}, ${item.status})`
      ).join('\\n')
      
      const confirm = await ElMessageBox.confirm(
        `检测到 ${existingSNs.length} 个重复SN将被跳过:\\n\\n${duplicateInfo}\\n\\n是否继续导入剩余 ${checkResult.available_count} 个SN？`,
        'SN重复检查',
        {
          confirmButtonText: '继续导入',
          cancelButtonText: '取消',
          type: 'warning',
          customStyle: {
            width: '600px'
          }
        }
      )
      
      if (confirm !== 'confirm') {
        return
      }
    }
    
    // 将文件转换为base64
    const reader = new FileReader()
    const fileContent = await new Promise((resolve) => {
      reader.onload = (e) => resolve(e.target.result.split(',')[1])
      reader.readAsDataURL(currentFile.value)
    })
    
    const importData = {
      file_content: fileContent,
      file_name: currentFile.value.name,
      equipment_type_id: importForm.value.equipment_type_id,
      warehouse_id: importForm.value.warehouse_id
    }
    
    const response = await stockApi.importSN(importData)
    importResult.value = response
    
    ElMessage.success(`导入完成！成功：${response.success_count}，重复：${response.duplicate_count}，失败：${response.failed_count}`)
    
    // 刷新库存列表
    if (response.success_count > 0) {
      await loadInventoryList()
    }
    
  } catch (error) {
    if (error === 'cancel') return
    console.error('导入失败:', error)
    ElMessage.error('导入失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    importing.value = false
  }
}

const resetImport = () => {
  importForm.value = {
    equipment_type_id: null,
    warehouse_id: 1
  }
  previewData.value = []
  importResult.value = null
  currentFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

const viewImportDetails = () => {
  if (importResult.value?.import_record_id) {
    // 跳转到导入记录详情页，并携带importId
    window.location.href = `/import-history?importId=${importResult.value.import_record_id}`
  } else {
    ElMessage.info('没有可查看的导入记录')
  }
}

const loadMainDeviceOptions = async () => {
  try {
    const response = await equipmentApi.getEquipmentList()
    mainDeviceOptions.value = response.filter(eq => eq.category === 'main_device')
  } catch (error) {
    console.error('加载主设备选项失败:', error)
  }
}

onMounted(() => {
  loadInventoryList()
  loadOptions()
  loadMainDeviceOptions()
})
</script>

<style lang="scss" scoped>
.el-select {
  width: 100%;
}

.danger-text {
  color: var(--danger-color) !important;
}

h3 {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 20px;
}

.low-stock {
  color: var(--danger-color) !important;
  font-weight: 600;
}

.method-selector {
  margin-bottom: 20px;
}

.manual-stock-in, .batch-import-section {
  .card, .el-card {
    margin-bottom: 20px;
  }
}

.upload-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-demo {
  .el-upload {
    border: 1px dashed var(--el-border-color);
    border-radius: 6px;
    cursor: pointer;
    position: relative;
    overflow: hidden;
    transition: var(--el-transition-duration-fast);
  }
  
  .el-upload:hover {
    border-color: var(--el-color-primary);
  }
}

.import-stats {
  display: flex;
  gap: 24px;
  align-items: center;
  
  .stat-item {
    display: flex;
    align-items: center;
    gap: 8px;
    
    .stat-label {
      color: var(--el-text-color-regular);
      font-size: 14px;
    }
    
    .stat-value {
      font-weight: 600;
      font-size: 16px;
    }
    
    &.success .stat-value {
      color: var(--el-color-success);
    }
    
    &.warning .stat-value {
      color: var(--el-color-warning);
    }
    
    &.error .stat-value {
      color: var(--el-color-danger);
    }
  }
}

.preview-card, .result-card {
  .el-table {
    margin-top: 16px;
  }
}
</style>
