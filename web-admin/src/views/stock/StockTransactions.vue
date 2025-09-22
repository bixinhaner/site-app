<template>
  <div class="page-container">
    <div class="page-header">
      <h2>出入库记录查询</h2>
      <el-button @click="loadTransactions" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- 筛选条件 -->
    <div class="card">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-select v-model="filters.transaction_type" placeholder="操作类型" clearable>
            <el-option label="入库" value="stock_in" />
            <el-option label="出库" value="stock_out" />
            <el-option label="调拨" value="transfer" />
            <el-option label="退库" value="return" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="onDateRangeChange"
          />
        </el-col>
        <el-col :span="6">
          <el-input v-model="filters.search" placeholder="搜索单据号..." clearable>
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="6">
          <el-button type="primary" @click="loadTransactions">查询</el-button>
        </el-col>
      </el-row>
    </div>

    <!-- 统计信息 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-title">今日出库</div>
        <div class="stat-value">{{ todayStats.out_count || 0 }}</div>
        <div class="stat-change">笔数</div>
      </div>
      <div class="stat-card">
        <div class="stat-title">今日入库</div>
        <div class="stat-value">{{ todayStats.in_count || 0 }}</div>
        <div class="stat-change">笔数</div>
      </div>
      <div class="stat-card">
        <div class="stat-title">扫码出库</div>
        <div class="stat-value">{{ todayStats.scan_count || 0 }}</div>
        <div class="stat-change">笔数</div>
      </div>
    </div>

    <!-- 出入库记录表 -->
    <div class="card">
      <el-table :data="transactionList" style="width: 100%" v-loading="loading" expand-row-keys>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div style="padding: 20px;">
              <h4>出入库明细:</h4>
              <el-table :data="row.items" size="small">
                <el-table-column prop="equipment_code" label="设备编码" width="120" />
                <el-table-column prop="equipment_name" label="设备名称" width="180" />
                <el-table-column prop="quantity" label="数量" width="80" />
                <el-table-column prop="unit" label="单位" width="80" />
              </el-table>
              
              <div v-if="row.scan_barcode" style="margin-top: 16px; padding: 12px; background: #f8fafc; border-radius: 6px;">
                <div><strong>扫码信息:</strong></div>
                <div>扫描条码: {{ row.scan_barcode }}</div>
                <div v-if="row.package_name">关联套装: {{ row.package_name }}</div>
                <div v-if="row.task_id">关联任务: {{ row.task_id }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="document_number" label="单据编号" width="180" />
        <el-table-column prop="transaction_type" label="操作类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeColor(row.transaction_type)">
              {{ getTypeText(row.transaction_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operator_name" label="操作人" width="120" />
        <el-table-column prop="total_quantity" label="总数量" width="100" />
        <el-table-column prop="approval_status" label="审批状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getApprovalColor(row.approval_status)">
              {{ getApprovalText(row.approval_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operation_time" label="操作时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.operation_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" v-if="userStore.isWarehouseManager">
          <template #default="{ row }">
            <el-button size="small" v-if="row.approval_status === 'pending'" @click="approveTransaction(row.id)">
              审批
            </el-button>
            <el-button size="small" type="info" @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search, Plus } from '@element-plus/icons-vue'
import { stockApi } from '../../api/stock'
import { equipmentApi } from '../../api/equipment'
import { useUserStore } from '../../stores/user'

const userStore = useUserStore()

const loading = ref(false)
const submitting = ref(false)
const transactionList = ref([])
const warehouseOptions = ref([])
const equipmentOptions = ref([])
const dateRange = ref([])

const filters = ref({
  transaction_type: '',
  start_date: '',
  end_date: '',
  search: ''
})

const stockInForm = ref({
  warehouse_id: 1,
  in_type: 'purchase',
  notes: '',
  items: []
})

const todayStats = computed(() => {
  const today = new Date().toDateString()
  const todayTransactions = transactionList.value.filter(t => 
    t.operation_time && new Date(t.operation_time).toDateString() === today
  )
  
  return {
    in_count: todayTransactions.filter(t => t.transaction_type === 'stock_in').length,
    out_count: todayTransactions.filter(t => t.transaction_type === 'stock_out').length,
    scan_count: todayTransactions.filter(t => t.scan_barcode).length
  }
})

const totalAmount = computed(() => 
  stockInForm.value.items.reduce((sum, item) => 
    0
  )
)

const getTypeText = (type) => {
  const typeMap = {
    'stock_in': '入库',
    'stock_out': '出库',
    'transfer': '调拨',
    'return': '退库',
    'adjustment': '调整'
  }
  return typeMap[type] || type
}

const getTypeColor = (type) => {
  const colorMap = {
    'stock_in': 'success',
    'stock_out': 'warning',
    'transfer': 'info',
    'return': 'primary',
    'adjustment': 'danger'
  }
  return colorMap[type] || ''
}

const getApprovalText = (status) => {
  const statusMap = {
    'pending': '待审批',
    'approved': '已通过',
    'rejected': '已驳回'
  }
  return statusMap[status] || status
}

const getApprovalColor = (status) => {
  const colorMap = {
    'pending': 'warning',
    'approved': 'success',
    'rejected': 'danger'
  }
  return colorMap[status] || ''
}

const getEquipmentUnit = (equipmentId) => {
  const equipment = equipmentOptions.value.find(eq => eq.id === equipmentId)
  return equipment?.unit || '台'
}

const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

const onDateRangeChange = (dates) => {
  if (dates && dates.length === 2) {
    filters.value.start_date = dates[0]
    filters.value.end_date = dates[1]
  } else {
    filters.value.start_date = ''
    filters.value.end_date = ''
  }
}

const loadTransactions = async () => {
  try {
    loading.value = true
    const response = await stockApi.getStockTransactions(filters.value)
    transactionList.value = response.transactions || []
  } catch (error) {
    console.error('加载出入库记录失败:', error)
    ElMessage.error('加载记录失败')
  } finally {
    loading.value = false
  }
}

const loadOptions = async () => {
  try {
    const [warehousesResponse, equipmentResponse] = await Promise.all([
      stockApi.getWarehouses(),
      equipmentApi.getEquipmentList({ status: 'active' })
    ])
    
    warehouseOptions.value = warehousesResponse.warehouses || []
    equipmentOptions.value = equipmentResponse || []
  } catch (error) {
    console.error('加载选项失败:', error)
  }
}

const addStockInItem = () => {
  stockInForm.value.items.push({
    equipment_id: null,
    quantity: 1,
    batch_number: ''
  })
}

const removeStockInItem = (index) => {
  stockInForm.value.items.splice(index, 1)
}

const onEquipmentChange = (row, index) => {
  const equipment = equipmentOptions.value.find(eq => eq.id === row.equipment_id)
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

const submitStockIn = async () => {
  if (stockInForm.value.items.length === 0) {
    ElMessage.warning('请至少添加一个入库明细')
    return
  }
  
  try {
    submitting.value = true
    await stockApi.createStockIn(stockInForm.value)
    ElMessage.success('入库单创建成功')
    
    resetForm()
    loadTransactions()
  } catch (error) {
    console.error('提交入库失败:', error)
    ElMessage.error('提交失败: ' + (error.response?.data?.detail || '网络错误'))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadTransactions()
  loadOptions()
})
</script>

<style lang="scss" scoped>
.el-select {
  width: 100%;
}

h4 {
  color: var(--text-primary);
  margin-bottom: 12px;
}
</style>