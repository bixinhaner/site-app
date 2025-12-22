<template>
  <div class="page-container">
    <div class="page-header">
      <h2>入库管理</h2>
    </div>

    <!-- 选择入库方式 -->
    <el-card class="method-selector">
      <el-radio-group v-model="stockInMethod" @change="handleMethodChange">
        <el-radio-button label="manual">手动入库</el-radio-button>
        <el-radio-button label="batch_import">批量导入</el-radio-button>
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
        <el-table-column label="序列号(SN)" width="180">
          <template #default="{ row }">
            <el-input 
              v-model="row.serial_number" 
              size="small" 
              :placeholder="isMainDevice(row.equipment_id) ? '主设备必填' : '可选'"
              :class="{ 'required-field': isMainDevice(row.equipment_id) }"
            />
          </template>
        </el-table-column>
        <el-table-column label="数量" width="100">
          <template #default="{ row }">
            <el-input-number 
              v-model="row.quantity" 
              :min="1" 
              :max="isMainDevice(row.equipment_id) ? 1 : 9999"
              size="small" 
              @change="calculateTotal" 
            />
          </template>
        </el-table-column>
        <el-table-column label="单位" width="60">
          <template #default="{ row }">
            <span>{{ getEquipmentUnit(row.equipment_id) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="批次号" width="120">
          <template #default="{ row }">
            <el-input v-model="row.batch_number" size="small" placeholder="可选" />
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
	              <el-form-item label="导入对象" required>
	                <el-radio-group v-model="importForm.import_target" @change="handleImportTargetChange">
	                  <el-radio-button label="main_device">主设备</el-radio-button>
	                  <el-radio-button label="auxiliary">辅料</el-radio-button>
	                </el-radio-group>
	              </el-form-item>
	            </el-col>
	            <el-col :span="12">
	              <el-form-item v-if="importForm.import_target === 'main_device'" :label="importTargetLabel" required>
	                <el-select
	                  v-model="importForm.equipment_type_id"
	                  placeholder="选择要导入的主设备类型"
	                  style="width: 100%"
	                >
	                  <el-option
	                    v-for="eq in importEquipmentOptions"
	                    :key="eq.id"
	                    :label="`${eq.equipment_name} (${eq.equipment_code})`"
	                    :value="eq.id"
	                  />
	                </el-select>
	              </el-form-item>
	              <el-form-item v-else label="辅料类型">
	                <el-alert
	                  type="info"
	                  :closable="false"
	                  title="辅料导入无需选择类型，请在 Excel 的“辅料类型(编码)”列填写辅材编码"
	                />
	              </el-form-item>
	            </el-col>
	          </el-row>
          <el-row :gutter="20">
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
	              <div>只能上传 xlsx/xls 文件，请先下载模板查看格式要求</div>
	              <div v-if="importForm.import_target === 'auxiliary'">
	                提示：导入的辅料类型(编码)需与系统中已存在的辅材编码一致
	              </div>
	            </div>
	          </template>
	        </el-upload>
      </el-card>

      <!-- 数据预览 -->
      <el-card v-if="previewData.length > 0" class="preview-card">
        <template #header>
          <span>数据预览</span>
	          <el-tag
	            v-if="importForm.import_target === 'auxiliary'"
	            type="info"
	            size="small"
	            style="margin-left: 10px"
	          >
	            共 {{ previewData.length }} 种 / 合计 {{ auxiliaryTotalQuantity }}
	          </el-tag>
          <el-tag v-else type="info" size="small" style="margin-left: 10px">共 {{ previewData.length }} 条数据</el-tag>
        </template>

	        <el-table :data="previewData.slice(0, 10)" border size="small" max-height="400">
	          <template v-if="importForm.import_target === 'auxiliary'">
	            <el-table-column prop="equipment_code" label="辅料编码" width="160" />
	            <el-table-column prop="equipment_name" label="辅料名称" width="180" />
	            <el-table-column prop="quantity" label="数量" width="100" />
	            <el-table-column prop="batch_number" label="批次号" width="120" />
	          </template>
          <template v-else>
            <el-table-column prop="sn" label="SN序列号" width="180" />
            <el-table-column prop="mac_address" label="MAC地址" width="150" />
            <el-table-column prop="manufacture_date" label="生产日期" width="110" />
            <el-table-column prop="warranty_start_date" label="保修开始" width="110" />
            <el-table-column prop="warranty_end_date" label="保修截止" width="110" />
            <el-table-column prop="vendor" label="供应商" width="100" />
            <el-table-column prop="batch_number" label="批次号" width="120" />
            <el-table-column prop="notes" label="备注" min-width="100" />
          </template>
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

        <div class="import-stats" v-if="importResult.import_type === 'auxiliary'">
          <div class="stat-item">
            <span class="stat-label">单据号:</span>
            <span class="stat-value">{{ importResult.document_number }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">种类数:</span>
            <span class="stat-value">{{ importResult.total_rows }}</span>
          </div>
          <div class="stat-item success">
            <span class="stat-label">入库数量:</span>
            <span class="stat-value">{{ importResult.total_quantity }}</span>
          </div>
        </div>

        <div class="import-stats" v-else>
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
          <el-button
            v-if="importResult.import_type === 'auxiliary'"
            size="small"
            @click="jumpToStockHistory"
            type="primary"
            link
          >
            跳转到出入库记录
          </el-button>
          <el-button v-else size="small" @click="viewImportDetails" type="primary" link>
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
  import_target: 'main_device',
  equipment_type_id: null,
  warehouse_id: 1
})
const previewData = ref([])
const importResult = ref(null)
const currentFile = ref(null)
const mainDeviceOptions = ref([])
const auxiliaryOptions = ref([])
const auxiliaryRawRows = ref([])
const auxiliaryImportErrors = ref([])
const importTargetLabel = computed(() =>
  importForm.value.import_target === 'auxiliary' ? '辅料类型' : '主设备类型'
)
const importEquipmentOptions = computed(() =>
  importForm.value.import_target === 'auxiliary' ? auxiliaryOptions.value : mainDeviceOptions.value
)
const auxiliaryTotalQuantity = computed(() => {
  if (importForm.value.import_target !== 'auxiliary') return 0
  return previewData.value.reduce((sum, item) => sum + (Number(item.quantity) || 0), 0)
})

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
  stockInForm.value.items.reduce((sum, item) => {
    const itemTotal = (item.quantity || 0) * (item.unit_price || 0)
    return sum + itemTotal
  }, 0)
)

const getEquipmentUnit = (equipmentId) => {
  const equipment = equipmentOptions.value.find(eq => eq.id === equipmentId)
  return equipment?.unit || '台'
}

const isMainDevice = (equipmentId) => {
  const equipment = equipmentOptions.value.find(eq => eq.id === equipmentId)
  return equipment?.category === 'main_device'
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
    batch_number: '',
    serial_number: ''
  })
}

const removeStockInItem = (index) => {
  stockInForm.value.items.splice(index, 1)
  calculateTotal()
}

const onEquipmentChange = (row, index) => {
  const equipment = equipmentOptions.value.find(eq => eq.id === row.equipment_id)
  if (equipment) {
    row.unit_price = equipment.price || 0
  }
  calculateTotal()
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
  
  // 验证主设备必须填写SN
  for (const item of stockInForm.value.items) {
    const equipment = equipmentOptions.value.find(eq => eq.id === item.equipment_id)
    if (equipment && equipment.category === 'main_device') {
      if (!item.serial_number || item.serial_number.trim() === '') {
        ElMessage.warning(`主设备 ${equipment.equipment_name} 必须填写序列号(SN)`)
        return
      }
      // 主设备数量必须为1
      if (item.quantity !== 1) {
        ElMessage.warning(`主设备 ${equipment.equipment_name} 数量必须为1`)
        item.quantity = 1
        return
      }
    }
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
  calculateTotal()
}

// 批量导入相关方法
const canImport = computed(() => {
  if (!importForm.value.warehouse_id || previewData.value.length === 0) return false
  if (importForm.value.import_target === 'auxiliary') {
    return auxiliaryImportErrors.value.length === 0
  }
  return Boolean(importForm.value.equipment_type_id)
})

const handleMethodChange = () => {
  // 切换方式时重置状态
  resetImport()
}

const downloadTemplate = async () => {
  if (importForm.value.import_target === 'auxiliary') {
    downloadAuxTemplate()
    return
  }

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

const handleImportTargetChange = () => {
  resetImport({ preserveWarehouse: true, preserveTarget: true })
}

const downloadAuxTemplate = () => {
  try {
    const templateHeader = ['辅料类型(编码)', '数量', '批次号', '备注', '供应商']
    const auxSamples = auxiliaryOptions.value.filter((i) => i && i.equipment_code).slice(0, 2)
    const templateData = [templateHeader]
    if (auxSamples.length > 0) {
      templateData.push([auxSamples[0].equipment_code, 10, 'BATCH2024001', '辅料批量入库示例', '华为'])
    }
    if (auxSamples.length > 1) {
      templateData.push([auxSamples[1].equipment_code, 5, 'BATCH2024002', '', '中兴'])
    }
    const worksheet = XLSX.utils.aoa_to_sheet(templateData)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, '辅料入库模板')

    const wbout = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' })
    const blob = new Blob([wbout], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '辅料入库模板.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    ElMessage.success('模板下载成功')
  } catch (error) {
    ElMessage.error('模板生成失败')
    console.error('生成辅料模板失败:', error)
  }
}

const beforeUpload = () => {
  return false // 阻止自动上传
}

const handleFileChange = async (file) => {
  currentFile.value = file.raw
  if (importForm.value.import_target === 'auxiliary' && auxiliaryOptions.value.length === 0) {
    await loadBatchImportOptions()
  }
  parseExcelFile(file.raw)
}

const handleFileRemove = () => {
  currentFile.value = null
  previewData.value = []
  importResult.value = null
  auxiliaryRawRows.value = []
  auxiliaryImportErrors.value = []
}

// 辅助函数：将Excel日期序列号或各种日期格式转换为标准日期格式
const excelDateToJSDate = (excelDate) => {
  if (!excelDate) return ''
  
  // Excel日期序列号转换（Excel的日期是从1900年1月1日开始计数）
  if (typeof excelDate === 'number') {
    // Excel将1900-01-01视为第1天，但实际上有一个已知的bug（将1900年错误地视为闰年）
    const excelEpoch = new Date(1899, 11, 30) // 1899年12月30日
    const jsDate = new Date(excelEpoch.getTime() + excelDate * 86400000)
    
    // 格式化为 YYYY-MM-DD
    const year = jsDate.getFullYear()
    const month = String(jsDate.getMonth() + 1).padStart(2, '0')
    const day = String(jsDate.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }
  
  // 处理字符串格式的日期
  if (typeof excelDate === 'string') {
    const dateStr = excelDate.trim()
    
    // 已经是 YYYY-MM-DD 格式，直接返回
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      return dateStr
    }
    
    // 处理 M/D/YY 或 MM/DD/YY 或 M/D/YYYY 或 MM/DD/YYYY 格式
    const slashMatch = dateStr.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/)
    if (slashMatch) {
      let [, month, day, year] = slashMatch
      
      // 处理两位数年份，假设00-49为2000-2049，50-99为1950-1999
      if (year.length === 2) {
        const yy = parseInt(year)
        year = yy < 50 ? `20${year}` : `19${year}`
      }
      
      month = month.padStart(2, '0')
      day = day.padStart(2, '0')
      return `${year}-${month}-${day}`
    }
    
    // 处理 YYYY/MM/DD 格式
    const slashMatch2 = dateStr.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/)
    if (slashMatch2) {
      const [, year, month, day] = slashMatch2
      return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
    }
    
    // 尝试使用 Date 对象解析
    try {
      const parsedDate = new Date(dateStr)
      if (!isNaN(parsedDate.getTime())) {
        const year = parsedDate.getFullYear()
        const month = String(parsedDate.getMonth() + 1).padStart(2, '0')
        const day = String(parsedDate.getDate()).padStart(2, '0')
        return `${year}-${month}-${day}`
      }
    } catch (e) {
      console.warn('日期解析失败:', dateStr, e)
    }
  }
  
  return ''
}

const parseExcelFile = async (file) => {
  try {
    const reader = new FileReader()
    reader.onload = (e) => {
      const data = new Uint8Array(e.target.result)
      const workbook = XLSX.read(data, { type: 'array', cellDates: true })
      const sheetName = workbook.SheetNames[0]
      const worksheet = workbook.Sheets[sheetName]
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1, raw: false, dateNF: 'yyyy-mm-dd' })

      if (importForm.value.import_target === 'auxiliary') {
        parseAuxiliaryRows(jsonData)
        return
      }

      parseMainDeviceRows(jsonData)
    }
    reader.readAsArrayBuffer(file)
  } catch (error) {
    ElMessage.error('文件解析失败')
    console.error('解析Excel失败:', error)
  }
}

const parseMainDeviceRows = (jsonData) => {
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
        mac_address: row[1] ? String(row[1]).trim() : '',
        manufacture_date: excelDateToJSDate(row[2]),
        warranty_start_date: excelDateToJSDate(row[3]),
        warranty_end_date: excelDateToJSDate(row[4]),
        vendor: row[5] ? String(row[5]).trim() : '',
        batch_number: row[6] ? String(row[6]).trim() : '',
        notes: row[7] ? String(row[7]).trim() : ''
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

const parseAuxiliaryRows = (jsonData) => {
  // 辅料模板：辅料类型(编码) / 数量 / 批次号 / 备注 / 供应商
  const rawRows = []
  const errors = []

  const headerRow = (jsonData && jsonData[0]) ? jsonData[0] : []
  const normalize = (v) => String(v ?? '').trim().replace(/\s+/g, '')
  const findCol = (candidates) => {
    const normalized = headerRow.map(normalize)
    for (const cand of candidates) {
      const idx = normalized.findIndex((h) => h.includes(normalize(cand)))
      if (idx >= 0) return idx
    }
    return -1
  }

  const colCode = findCol(['辅料类型(编码)', '辅料类型', '辅材类型', '辅料编码', '辅材编码'])
  const colQuantity = findCol(['数量'])
  const colBatch = findCol(['批次号', '批次'])
  const colNotes = findCol(['备注'])
  const colVendor = findCol(['供应商'])

  if (colCode < 0 || colQuantity < 0) {
    auxiliaryImportErrors.value = [{ row: 1, reason: '模板格式不正确：缺少“辅料类型(编码)”或“数量”列，请下载最新模板' }]
    previewData.value = []
    auxiliaryRawRows.value = []
    ElMessage.error('模板格式不正确，请下载最新模板后重新导入')
    return
  }

  const auxCodeMap = new Map(
    auxiliaryOptions.value
      .filter((eq) => eq && eq.equipment_code)
      .map((eq) => [String(eq.equipment_code).trim(), eq])
  )

  for (let i = 1; i < jsonData.length; i++) {
    const row = jsonData[i] || []
    const hasAnyValue = row.some((cell) => cell !== undefined && cell !== null && String(cell).trim() !== '')
    if (!hasAnyValue) continue

    const rowNumber = i + 1
    const equipmentCode = row[colCode] ? String(row[colCode]).trim() : ''
    if (!equipmentCode) {
      errors.push({ row: rowNumber, reason: '辅料类型(编码)不能为空' })
      continue
    }

    const matched = auxCodeMap.get(equipmentCode)
    if (!matched) {
      errors.push({ row: rowNumber, reason: `辅料编码不存在或非辅材：${equipmentCode}` })
      continue
    }

    const rawQuantity = row[colQuantity]
    const quantity = Number(String(rawQuantity ?? '').trim())
    if (!Number.isFinite(quantity) || quantity <= 0) {
      errors.push({ row: rowNumber, reason: '数量必须为大于0的数字' })
      continue
    }
    if (!Number.isInteger(quantity)) {
      errors.push({ row: rowNumber, reason: '数量必须为整数' })
      continue
    }

    rawRows.push({
      row: rowNumber,
      equipment_code: equipmentCode,
      equipment_id: matched.id,
      equipment_name: matched.equipment_name,
      quantity,
      batch_number: colBatch >= 0 && row[colBatch] ? String(row[colBatch]).trim() : '',
      notes: colNotes >= 0 && row[colNotes] ? String(row[colNotes]).trim() : '',
      vendor: colVendor >= 0 && row[colVendor] ? String(row[colVendor]).trim() : ''
    })
  }

  // 合并同一辅料编码（数量求和），批次号不一致则阻止导入
  const mergedMap = new Map()
  for (const r of rawRows) {
    const key = r.equipment_code
    const existing = mergedMap.get(key)
    if (!existing) {
      mergedMap.set(key, {
        equipment_code: r.equipment_code,
        equipment_id: r.equipment_id,
        equipment_name: r.equipment_name,
        quantity: r.quantity,
        batch_number: r.batch_number || ''
      })
      continue
    }

    existing.quantity += r.quantity

    const existingBatch = String(existing.batch_number || '').trim()
    const rowBatch = String(r.batch_number || '').trim()
    if (existingBatch && rowBatch && existingBatch !== rowBatch) {
      errors.push({
        row: r.row,
        reason: `同一辅料编码(${key})存在多个批次号，无法合并，请在Excel中保持一致或合并为一行`
      })
      continue
    }
    if (!existingBatch && rowBatch) {
      existing.batch_number = rowBatch
    }
  }

  auxiliaryImportErrors.value = errors
  auxiliaryRawRows.value = rawRows
  if (errors.length > 0) {
    previewData.value = []
    const preview = errors.slice(0, 20).map((r) => `行${r.row}:${r.reason}`).join('\n')
    ElMessageBox.alert(
      `发现 ${errors.length} 处问题，已阻止导入：\n\n${preview}${errors.length > 20 ? `\n\n... 还有 ${errors.length - 20} 条` : ''}`,
      '辅料导入校验失败',
      { type: 'error' }
    )
    return
  }

  previewData.value = Array.from(mergedMap.values()).sort((a, b) => String(a.equipment_code).localeCompare(String(b.equipment_code)))
  ElMessage.success(`已解析 ${rawRows.length} 行数据，合并后 ${previewData.value.length} 种辅料`)
}

const submitImport = async () => {
  try {
    importing.value = true

    if (importForm.value.import_target === 'auxiliary') {
      const totalQuantity = auxiliaryTotalQuantity.value
      if (auxiliaryImportErrors.value.length > 0) {
        ElMessage.error('辅料导入校验未通过，请修正Excel后重新上传')
        return
      }
      await ElMessageBox.confirm(
        `确认导入辅料入库？\\n原始行数：${auxiliaryRawRows.value.length}\\n辅料种类数：${previewData.value.length}\\n入库总数量：${totalQuantity}`,
        '导入确认',
        { type: 'warning' }
      )

      const vendors = [...new Set(auxiliaryRawRows.value.map((i) => (i.vendor || '').trim()).filter(Boolean))]
      const vendorText = vendors.length > 0 ? `，供应商：${vendors.join(',')}` : ''
      const rawNotes = auxiliaryRawRows.value.map((i) => (i.notes || '').trim()).filter(Boolean)
      const uniqueNotes = [...new Set(rawNotes)]
      const noteText =
        uniqueNotes.length > 0
          ? `，备注：${uniqueNotes.slice(0, 5).join('；')}${uniqueNotes.length > 5 ? ` 等${uniqueNotes.length}条` : ''}`
          : ''
      const notes = `辅料批量导入 - ${currentFile.value?.name || ''}${vendorText}${noteText}`

      const items = previewData.value.map((row) => ({
        equipment_id: row.equipment_id,
        quantity: Number(row.quantity) || 0,
        batch_number: row.batch_number || '',
        serial_number: ''
      }))

      const missing = items.filter((i) => !i.equipment_id)
      if (missing.length > 0) {
        ElMessage.error('存在无法匹配的辅料编码，请刷新页面后重新上传')
        return
      }

      const res = await stockApi.createStockIn({
        warehouse_id: importForm.value.warehouse_id,
        notes,
        items
      })

      importResult.value = {
        import_type: 'auxiliary',
        transaction_id: res.transaction_id,
        document_number: res.document_number,
        total_rows: previewData.value.length,
        total_quantity: totalQuantity
      }

      ElMessage.success(`导入完成！入库单据号：${res.document_number}`)
      await loadInventoryList()
      return
    }

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
    importResult.value = { ...response, import_type: 'main_device' }
    
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

const resetImport = (options = {}) => {
  const preserveWarehouse = options.preserveWarehouse === true
  const preserveTarget = options.preserveTarget === true
  importForm.value = {
    import_target: preserveTarget ? importForm.value.import_target : 'main_device',
    equipment_type_id: null,
    warehouse_id: preserveWarehouse ? importForm.value.warehouse_id : 1
  }
  previewData.value = []
  importResult.value = null
  currentFile.value = null
  auxiliaryRawRows.value = []
  auxiliaryImportErrors.value = []
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

const viewImportDetails = () => {
  if (importResult.value?.import_record_id) {
    // 跳转到导入记录详情页，并携带importId
    const params = new URLSearchParams({
      type: 'import',
      importId: importResult.value.import_record_id
    })
    window.location.href = `/inventory/history?${params.toString()}`
  } else {
    ElMessage.info('没有可查看的导入记录')
  }
}

const jumpToStockHistory = () => {
  const doc = importResult.value?.document_number
  if (!doc) {
    ElMessage.warning('未找到入库单据号')
    return
  }
  const params = new URLSearchParams({
    type: 'transaction',
    keyword: doc
  })
  window.location.href = `/inventory/history?${params.toString()}`
}

const loadBatchImportOptions = async () => {
  try {
    const response = await equipmentApi.getEquipmentList({ status: 'active', limit: 2000 })
    mainDeviceOptions.value = response.filter(eq => eq.category === 'main_device')
    auxiliaryOptions.value = response.filter(eq => eq.category === 'auxiliary')
  } catch (error) {
    console.error('加载批量导入选项失败:', error)
  }
}

onMounted(() => {
  loadInventoryList()
  loadOptions()
  loadBatchImportOptions()
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

.required-field {
  :deep(.el-input__wrapper) {
    box-shadow: 0 0 0 1px #f56c6c inset;
  }
  
  :deep(.el-input__inner::placeholder) {
    color: #f56c6c;
    font-weight: 500;
  }
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
