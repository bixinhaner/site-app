<template>
  <div class="inventory-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1>设备库存管理</h1>
      <div class="header-actions">
        <el-button @click="exportInventory" type="success">
          <el-icon><Download /></el-icon>
          导出Excel
        </el-button>
        <el-button @click="loadInventoryList" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 库存统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-number">{{ totalItems }}</div>
        <div class="stat-label">库存种类</div>
      </div>
      <div class="stat-card">
        <div class="stat-number">{{ totalStock }}</div>
        <div class="stat-label">库存总量</div>
      </div>
      <div class="stat-card warning">
        <div class="stat-number">{{ lowStockCount }}</div>
        <div class="stat-label">预警数量</div>
      </div>
    </div>

    <!-- 搜索筛选 -->
    <el-card class="search-card">
      <div class="search-row">
        <div class="search-left">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索设备名称或编码"
            style="width: 300px"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          
          <el-select
            v-model="filterCategory"
            placeholder="设备类别"
            style="width: 150px"
            clearable
            @change="handleSearch"
          >
            <el-option label="主设备" value="main_device" />
            <el-option label="辅材" value="auxiliary" />
          </el-select>
          
          <el-select
            v-model="filterStockStatus"
            placeholder="库存状态"
            style="width: 120px"
            clearable
            @change="handleSearch"
          >
            <el-option label="正常" value="normal" />
            <el-option label="预警" value="low_stock" />
            <el-option label="缺货" value="out_of_stock" />
          </el-select>
        </div>
        
        <div class="search-right">
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetSearch">重置</el-button>
        </div>
      </div>
    </el-card>

    <!-- 库存类型选择 -->
    <el-card class="inventory-tabs-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="主设备库存" name="main_device">
          <div class="tab-stats">
            <el-tag type="primary" size="small">共 {{ mainDeviceList.length }} 种主设备</el-tag>
            <el-tag type="info" size="small">总库存量: {{ mainDeviceTotalStock }}</el-tag>
          </div>
          
          <!-- 主设备表格 -->
          <el-table
            :data="mainDeviceList"
            v-loading="loading"
            stripe
            style="width: 100%; margin-top: 16px;"
          >
            <el-table-column prop="equipment_code" label="设备编码" width="140" />
            <el-table-column prop="equipment_name" label="设备名称" min-width="200" />
            <el-table-column prop="warehouse_name" label="仓库" width="120" />
            <el-table-column prop="current_stock" label="当前库存" width="100" sortable>
              <template #default="{ row }">
                <span :class="{ 'low-stock': row.is_low_stock }">
                  {{ row.current_stock }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="available_stock" label="可用库存" width="100" />
            <el-table-column prop="allocated_stock" label="已分配" width="100" />
            <el-table-column prop="unit" label="单位" width="80" />
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="viewDeviceInstances(row)" link>
                  查看实例 ({{ row.current_stock }})
                </el-button>
                <el-button size="small" @click="viewStockHistory(row)" link>
                  出入库记录
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="辅材库存" name="auxiliary">
          <div class="tab-stats">
            <el-tag type="success" size="small">共 {{ auxiliaryList.length }} 种辅材</el-tag>
            <el-tag type="info" size="small">总库存量: {{ auxiliaryTotalStock }}</el-tag>
          </div>
          
          <!-- 辅材表格 -->
          <el-table
            :data="auxiliaryList"
            v-loading="loading"
            stripe
            style="width: 100%; margin-top: 16px;"
          >
            <el-table-column prop="equipment_code" label="设备编码" width="140" />
            <el-table-column prop="equipment_name" label="设备名称" min-width="200" />
            <el-table-column prop="warehouse_name" label="仓库" width="120" />
            <el-table-column prop="current_stock" label="当前库存" width="100" sortable>
              <template #default="{ row }">
                <span :class="{ 'low-stock': row.is_low_stock }">
                  {{ row.current_stock }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="available_stock" label="可用库存" width="100" />
            <el-table-column prop="allocated_stock" label="已分配" width="100" />
            <el-table-column prop="unit" label="单位" width="80" />
            <el-table-column prop="min_stock" label="最低库存" width="100" />
            <el-table-column label="库存状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStockStatusType(row)" size="small">
                  {{ getStockStatusText(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button size="small" @click="viewStockHistory(row)" link>
                  出入库记录
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 设备实例详情弹窗 -->
    <el-dialog
      v-model="showInstanceDialog"
      :title="`${selectedEquipment?.equipment_name} - 设备实例详情`"
      width="80%"
      top="5vh"
    >
        <div v-if="selectedEquipment">
          <div class="instance-stats">
            <el-tag type="info" size="small">总数量: {{ deviceInstances.length }}</el-tag>
            <el-tag type="success" size="small">在库: {{ getInstancesByStatus('in_stock').length }}</el-tag>
            <el-tag type="warning" size="small">待检查: {{ getInstancesByStatus('pending_inspection').length }}</el-tag>
            <el-tag type="success" size="small">已检查: {{ getInstancesByStatus('inspected').length }}</el-tag>
            <el-tag type="warning" size="small">退库待收货: {{ getInstancesByStatus('return_pending_receive').length }}</el-tag>
            <el-tag type="info" size="small">已出库: {{ getInstancesByStatus('issued').length }}</el-tag>
            <el-tag type="danger" size="small">损坏/报损: {{ getInstancesByStatus('damaged').length }}</el-tag>
          </div>

        <el-table :data="deviceInstances" stripe style="width: 100%; margin-top: 16px;" max-height="400">
          <el-table-column prop="serial_number" label="SN序列号" width="150" />
          <el-table-column prop="mac_address" label="MAC地址" width="150" />
          <el-table-column prop="imei" label="IMEI" width="150" />
          <el-table-column prop="firmware_version" label="固件版本" width="100" />
          <el-table-column prop="hardware_version" label="硬件版本" width="100" />
          <el-table-column prop="vendor" label="供应商" width="100" />
          <el-table-column prop="batch_number" label="批次号" width="100" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getInstanceStatusType(row.status)" size="small">
                {{ getInstanceStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="location" label="库位" width="100" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button size="small" @click="trackDevice(row.serial_number)" type="primary" link>
                设备追踪
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <!-- 原有的库存列表（作为备用视图） -->
    <el-card class="table-card" style="display: none;">
      <template #header>
        <div class="table-header">
          <span>库存明细</span>
          <div class="table-stats">
            <el-tag type="info" size="small">共 {{ inventoryList.length }} 种设备</el-tag>
          </div>
        </div>
      </template>

      <el-table
        :data="inventoryList"
        v-loading="loading"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="equipment_code" label="设备编码" width="140" />
        
        <el-table-column prop="equipment_name" label="设备名称" min-width="200" />
        
        <el-table-column prop="category" label="类别" width="100">
          <template #default="{ row }">
            <el-tag :type="row.category === 'main_device' ? 'primary' : 'success'" size="small">
              {{ row.category === 'main_device' ? '主设备' : '辅材' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="warehouse_name" label="仓库" width="120" />
        
        <el-table-column prop="current_stock" label="当前库存" width="100" sortable>
          <template #default="{ row }">
            <span :class="{ 'low-stock': row.is_low_stock }">
              {{ row.current_stock }}
            </span>
          </template>
        </el-table-column>
        
        <el-table-column prop="available_stock" label="可用库存" width="100" sortable>
          <template #default="{ row }">
            <span :class="{ 'low-stock': row.available_stock <= (row.min_stock || 0) }">
              {{ row.available_stock }}
            </span>
          </template>
        </el-table-column>
        
        <el-table-column prop="reserved_stock" label="预留库存" width="100" />
        
        <el-table-column prop="min_stock" label="最低库存" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.min_stock || 0 }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="unit" label="单位" width="80" />
        
        <el-table-column label="库存状态" width="120">
          <template #default="{ row }">
            <el-tag 
              :type="getStockStatusType(row)" 
              size="small"
            >
              {{ getStockStatusText(row) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="last_updated_at" label="最后更新" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.last_updated_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewDetails(row)" link>
              <el-icon><View /></el-icon>
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadInventoryList"
          @current-change="loadInventoryList"
        />
      </div>
    </el-card>

    <!-- 库存详情弹窗 -->
    <el-dialog
      v-model="showDetailDialog"
      title="库存详情"
      width="500px"
    >
      <div v-if="selectedInventory" class="detail-content">
        <div class="detail-item">
          <label>设备名称:</label>
          <span>{{ selectedInventory.equipment_name }}</span>
        </div>
        <div class="detail-item">
          <label>设备编码:</label>
          <span>{{ selectedInventory.equipment_code }}</span>
        </div>
        <div class="detail-item">
          <label>当前库存:</label>
          <span>{{ selectedInventory.current_stock }} {{ selectedInventory.unit }}</span>
        </div>
        <div class="detail-item">
          <label>可用库存:</label>
          <span>{{ selectedInventory.available_stock }} {{ selectedInventory.unit }}</span>
        </div>
        <div class="detail-item">
          <label>预留库存:</label>
          <span>{{ selectedInventory.reserved_stock }} {{ selectedInventory.unit }}</span>
        </div>
        <div class="detail-item">
          <label>最低库存:</label>
          <span>{{ selectedInventory.min_stock }} {{ selectedInventory.unit }}</span>
        </div>
      </div>
      
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { stockApi } from '../../api/stock'
import * as XLSX from 'xlsx'
import { trackOperation } from '@/utils/operationTrack'

const router = useRouter()

const loading = ref(false)
const inventoryList = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const searchKeyword = ref('')
const filterCategory = ref('')
const filterStockStatus = ref('')

const showDetailDialog = ref(false)
const selectedInventory = ref(null)

// 新增Tab页相关状态
const activeTab = ref('main_device')
const showInstanceDialog = ref(false)
const selectedEquipment = ref(null)
const deviceInstances = ref([])

// 计算属性 - 设备分类列表
const mainDeviceList = computed(() => 
  inventoryList.value.filter(item => item.category === 'main_device')
)

const auxiliaryList = computed(() => 
  inventoryList.value.filter(item => item.category === 'auxiliary')
)

// 计算属性 - 分类库存统计
const mainDeviceTotalStock = computed(() => 
  mainDeviceList.value.reduce((sum, item) => sum + item.current_stock, 0)
)

const auxiliaryTotalStock = computed(() => 
  auxiliaryList.value.reduce((sum, item) => sum + item.current_stock, 0)
)

// 计算统计数据
const totalItems = computed(() => inventoryList.value.length)
const totalStock = computed(() => 
  inventoryList.value.reduce((sum, item) => sum + item.current_stock, 0)
)
const lowStockCount = computed(() => 
  inventoryList.value.filter(item => item.is_low_stock).length
)

// 获取库存状态
const getStockStatusType = (row) => {
  if (row.current_stock <= 0) return 'danger'
  if (row.is_low_stock) return 'warning'
  return 'success'
}

const getStockStatusText = (row) => {
  if (row.current_stock <= 0) return '缺货'
  if (row.is_low_stock) return '预警'
  return '正常'
}

// 格式化时间
const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 加载库存列表
const loadInventoryList = async () => {
  try {
    loading.value = true
    const params = {}
    
    if (filterCategory.value) {
      params.category = filterCategory.value
    }
    if (filterStockStatus.value === 'low_stock') {
      params.low_stock_only = true
    }
    
    const response = await stockApi.getInventoryList(params)
    inventoryList.value = response.inventory || []
    total.value = inventoryList.value.length
    
  } catch (error) {
    console.error('加载库存列表失败:', error)
    ElMessage.error('加载库存列表失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 搜索处理
const handleSearch = () => {
  trackOperation({
    module: '库存管理',
    action: '查询',
    object_type: '库存',
    data: {
      keyword: searchKeyword.value || undefined,
      category: filterCategory.value || undefined,
      stock_status: filterStockStatus.value || undefined,
    },
  })
  loadInventoryList()
}

// 重置搜索
const resetSearch = () => {
  searchKeyword.value = ''
  filterCategory.value = ''
  filterStockStatus.value = ''
  trackOperation({
    module: '库存管理',
    action: '重置筛选',
    object_type: '库存',
  })
  loadInventoryList()
}

// 查看详情
const viewDetails = (inventory) => {
  selectedInventory.value = inventory
  showDetailDialog.value = true
}

// 导出Excel
const exportInventory = () => {
  try {
    // 根据当前选中的Tab确定导出数据
    let dataToExport = []
    let sheetName = ''
    let fileName = ''
    
    if (activeTab.value === 'main_device') {
      dataToExport = mainDeviceList.value
      sheetName = '主设备库存'
      fileName = `主设备库存_${formatExportDate()}.xlsx`
    } else {
      dataToExport = auxiliaryList.value
      sheetName = '辅材库存'
      fileName = `辅材库存_${formatExportDate()}.xlsx`
    }
    
    if (dataToExport.length === 0) {
      ElMessage.warning('暂无数据可导出')
      return
    }
    
    // 格式化导出数据
    const exportData = dataToExport.map((item, index) => {
      const baseData = {
        '序号': index + 1,
        '设备编码': item.equipment_code || '',
        '设备名称': item.equipment_name || '',
        '仓库': item.warehouse_name || '',
        '当前库存': item.current_stock || 0,
        '可用库存': item.available_stock || 0,
        '已分配': item.allocated_stock || 0,
        '单位': item.unit || '',
        '库存状态': getStockStatusText(item),
        '最后更新': formatDateTime(item.last_updated_at)
      }
      
      // 辅材增加最低库存字段
      if (activeTab.value === 'auxiliary') {
        baseData['最低库存'] = item.min_stock || 0
      }
      
      return baseData
    })
    
    // 创建工作簿
    const worksheet = XLSX.utils.json_to_sheet(exportData)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, sheetName)
    
    // 设置列宽
    const columnWidths = [
      { wch: 6 },  // 序号
      { wch: 15 }, // 设备编码
      { wch: 25 }, // 设备名称
      { wch: 12 }, // 仓库
      { wch: 10 }, // 当前库存
      { wch: 10 }, // 可用库存
      { wch: 10 }, // 已分配
      { wch: 8 },  // 单位
      { wch: 10 }, // 库存状态
      { wch: 18 }  // 最后更新
    ]
    
    if (activeTab.value === 'auxiliary') {
      columnWidths.splice(8, 0, { wch: 10 }) // 最低库存
    }
    
    worksheet['!cols'] = columnWidths
    
    // 导出文件
    XLSX.writeFile(workbook, fileName)
    
    ElMessage.success(`成功导出 ${dataToExport.length} 条数据`)
  } catch (error) {
    console.error('导出Excel失败:', error)
    ElMessage.error('导出失败: ' + error.message)
  }
}

// 格式化导出日期
const formatExportDate = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const hours = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  return `${year}${month}${day}_${hours}${minutes}`
}

// Tab切换处理
const handleTabChange = (tabName) => {
  activeTab.value = tabName
}

// 查看设备实例
const viewDeviceInstances = async (equipment) => {
  try {
    selectedEquipment.value = equipment
    
    // 调用API获取设备实例数据
    const response = await stockApi.getEquipmentInstances(equipment.equipment_id)
    deviceInstances.value = response.instances || []
    
    if (deviceInstances.value.length === 0) {
      ElMessage.info(`${equipment.equipment_name} 暂无设备实例，请先导入SN数据`)
      return
    }
    
    showInstanceDialog.value = true
  } catch (error) {
    console.error('获取设备实例失败:', error)
    ElMessage.error('获取设备实例失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 设备追踪：跳转到设备生命周期追踪页面，并自动带入 SN
const trackDevice = (serialNumber) => {
  const sn = (serialNumber || '').trim()
  if (!sn) {
    ElMessage.warning('该实例缺少 SN，无法追踪')
    return
  }
  router.push({
    name: 'EquipmentLifecycle',
    query: { sn }
  })
}

// 查看出入库历史
const viewStockHistory = (equipment) => {
  const code = (equipment?.equipment_code || '').trim()
  if (!code) {
    ElMessage.warning('缺少设备编码，无法跳转到出入库记录')
    return
  }
  router.push({
    name: 'StockHistory',
    query: {
      type: 'transaction',
      keyword: code
    }
  })
}

// 获取设备实例按状态筛选
const getInstancesByStatus = (status) => {
  return deviceInstances.value.filter(instance => instance.status === status)
}

// 获取设备实例状态标签类型
const getInstanceStatusType = (status) => {
  const statusMap = {
    'in_stock': 'success',
    'issued': 'info',
    'pending_inspection': 'warning',
    'inspected': 'success',
    'return_pending_receive': 'warning',
    'damaged': 'danger',
    // 兼容保留（历史值）
    'allocated': 'warning',
    'returned': 'info'
  }
  return statusMap[status] || 'info'
}

// 获取设备实例状态文本
const getInstanceStatusText = (status) => {
  const statusMap = {
    'in_stock': '在库',
    'issued': '已出库',
    'pending_inspection': '待检查',
    'inspected': '已检查',
    'return_pending_receive': '退库待收货',
    'damaged': '损坏/报损',
    // 兼容保留（历史值）
    'allocated': '已分配(旧)',
    'returned': '已归还(旧)'
  }
  return statusMap[status] || '未知'
}

onMounted(() => {
  loadInventoryList()
})
</script>

<style scoped lang="scss">
.inventory-page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  
  h1 {
    color: var(--text-primary);
    font-size: 28px;
    font-weight: 600;
    margin: 0;
  }
  
  .header-actions {
    display: flex;
    gap: 12px;
  }
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
  
  .stat-card {
    background: white;
    border-radius: 8px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    border: 1px solid var(--border-color);
    
    &.warning {
      border-left: 4px solid var(--warning-color);
    }
    
    .stat-number {
      font-size: 28px;
      font-weight: 700;
      color: var(--primary-color);
      margin-bottom: 8px;
    }
    
    .stat-label {
      color: var(--text-secondary);
      font-size: 14px;
    }
  }
}

.search-card {
  margin-bottom: 24px;
  border-radius: 8px;
  
  .search-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    
    .search-left {
      display: flex;
      gap: 12px;
      flex: 1;
    }
    
    .search-right {
      display: flex;
      gap: 8px;
    }
  }
}

.table-card {
  border-radius: 8px;
  
  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    color: var(--text-primary);
  }
}

.low-stock {
  color: var(--danger-color);
  font-weight: 600;
}

.detail-content {
  .detail-item {
    display: flex;
    justify-content: space-between;
    padding: 12px 0;
    border-bottom: 1px solid #f1f5f9;
    
    &:last-child {
      border-bottom: none;
    }
    
    label {
      font-weight: 500;
      color: var(--text-secondary);
    }
    
    span {
      color: var(--text-primary);
    }
  }
}

.pagination-container {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
}

.inventory-tabs-card {
  border-radius: 8px;
  
  .tab-stats {
    margin-bottom: 16px;
    display: flex;
    gap: 12px;
    align-items: center;
  }
}

.instance-stats {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
}

// 响应式设计
@media (max-width: 1200px) {
  .search-row {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
    
    .search-left {
      flex-direction: column;
    }
  }
}

@media (max-width: 768px) {
  .inventory-page {
    padding: 16px;
  }
  
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .stats-row {
    grid-template-columns: 1fr;
  }
}
</style>
