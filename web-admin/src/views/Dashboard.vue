<template>
  <div class="dashboard-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1>仪表盘</h1>
      <div class="header-actions">
        <el-button @click="refreshData" :loading="loading" type="primary">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-header">
          <el-icon class="stat-icon primary"><Box /></el-icon>
          <span class="stat-title">设备类型</span>
        </div>
        <div class="stat-body">
          <div class="stat-value">{{ dashboardData.equipment_count || 0 }}</div>
          <div class="stat-description">活跃设备类型数量</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <el-icon class="stat-icon success"><Collection /></el-icon>
          <span class="stat-title">设备套装</span>
        </div>
        <div class="stat-body">
          <div class="stat-value">{{ dashboardData.package_count || 0 }}</div>
          <div class="stat-description">已配置设备套装</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <el-icon class="stat-icon info"><TakeawayBox /></el-icon>
          <span class="stat-title">主设备库存</span>
        </div>
        <div class="stat-body">
          <div class="stat-value">{{ dashboardData.main_device_total_stock || 0 }}</div>
          <div class="stat-description">主设备库存总数量</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <el-icon class="stat-icon warning"><Warning /></el-icon>
          <span class="stat-title">库存预警</span>
        </div>
        <div class="stat-body">
          <div class="stat-value" :class="{ 'danger': dashboardData.low_stock_count > 0 }">
            {{ dashboardData.low_stock_count || 0 }}
          </div>
          <div class="stat-description">需要补货的设备</div>
        </div>
      </div>
    </div>

    <!-- 详细信息区域 -->
    <el-row :gutter="24">
      <!-- 最近出入库记录 -->
      <el-col :span="14">
        <el-card class="info-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon><Document /></el-icon>
                最近出入库记录
              </span>
              <el-button text @click="$router.push('/stock-history')">
                查看更多 <el-icon><ArrowRight /></el-icon>
              </el-button>
            </div>
          </template>
          
          <el-table :data="recentTransactions" style="width: 100%" :show-header="true">
            <el-table-column prop="document_number" label="单号" width="160" />
            <el-table-column prop="transaction_type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="row.transaction_type === 'stock_in' ? 'success' : 'info'" size="small">
                  {{ row.transaction_type === 'stock_in' ? '入库' : '出库' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="operator_name" label="操作人" width="100" />
            <el-table-column prop="total_quantity" label="数量" width="80" />
            <el-table-column prop="operation_time" label="时间" min-width="160">
              <template #default="{ row }">
                {{ formatDateTime(row.operation_time) }}
              </template>
            </el-table-column>
          </el-table>
          
          <div v-if="!recentTransactions.length" class="empty-state">
            <el-icon size="48" color="#ddd"><Document /></el-icon>
            <p>暂无出入库记录</p>
          </div>
        </el-card>
      </el-col>

      <!-- 库存预警 -->
      <el-col :span="10">
        <el-card class="info-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon><Warning /></el-icon>
                库存预警
              </span>
              <el-button text @click="$router.push('/inventory')">
                查看库存 <el-icon><ArrowRight /></el-icon>
              </el-button>
            </div>
          </template>
          
          <div class="warning-list">
            <div
              v-for="item in lowStockItems"
              :key="item.id"
              class="warning-item"
            >
              <div class="warning-info">
                <span class="equipment-name">{{ item.equipment_name }}</span>
                <span class="stock-info">
                  剩余: {{ item.current_stock }} {{ item.unit }}
                </span>
              </div>
              <el-tag type="danger" size="small">预警</el-tag>
            </div>
          </div>
          
          <div v-if="!lowStockItems.length" class="empty-state">
            <el-icon size="48" color="#10b981"><Check /></el-icon>
            <p style="color: #10b981;">库存状态正常</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷操作 -->
    <el-card class="quick-actions">
      <template #header>
        <span class="card-title">
          <el-icon><Operation /></el-icon>
          快捷操作
        </span>
      </template>
      
      <div class="action-buttons">
        <el-button type="primary" @click="$router.push('/equipment')">
          <el-icon><Box /></el-icon>
          设备类型管理
        </el-button>
        <el-button type="success" @click="$router.push('/packages')">
          <el-icon><Collection /></el-icon>
          设备套装配置
        </el-button>
        <el-button type="info" @click="$router.push('/stock-in')">
          <el-icon><Upload /></el-icon>
          设备入库
        </el-button>
        <el-button type="warning" @click="$router.push('/inventory')">
          <el-icon><TakeawayBox /></el-icon>
          设备库存管理
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { stockApi } from '../api/stock'

const loading = ref(false)
const dashboardData = ref({
  equipment_count: 0,
  package_count: 0,
  main_device_total_stock: 0,
  low_stock_count: 0
})

const recentTransactions = ref([])
const lowStockItems = ref([])

// 格式化时间
const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 加载仪表盘数据
const loadDashboardData = async () => {
  try {
    loading.value = true
    
    // 获取库存统计数据
    const inventoryResponse = await stockApi.getInventoryDashboard()
    if (inventoryResponse) {
      dashboardData.value = {
        equipment_count: inventoryResponse.summary?.total_items || 0,
        package_count: inventoryResponse.summary?.main_device_count || 0,
        main_device_total_stock: inventoryResponse.summary?.main_device_total_stock || 0,
        low_stock_count: inventoryResponse.summary?.low_stock_items || 0
      }
      
      recentTransactions.value = inventoryResponse.recent_transactions || []
    }
    
    // 获取低库存项目
    const lowStockResponse = await stockApi.getInventoryList({ low_stock_only: true })
    if (lowStockResponse?.inventory) {
      lowStockItems.value = lowStockResponse.inventory.slice(0, 5) // 只显示前5条
    }
    
  } catch (error) {
    console.error('加载仪表盘数据失败:', error)
    ElMessage.error('加载数据失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 刷新数据
const refreshData = async () => {
  await loadDashboardData()
  ElMessage.success('数据刷新成功')
}

onMounted(() => {
  loadDashboardData()
})
</script>

<style scoped lang="scss">
.dashboard-page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  
  h1 {
    color: var(--text-primary);
    font-size: 32px;
    font-weight: 700;
    margin: 0;
  }
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
  
  .stat-card {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    border: 1px solid var(--border-color);
    transition: all 0.3s ease;
    
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
    }
    
    .stat-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
      
      .stat-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        
        &.primary { background: linear-gradient(45deg, #f97316, #fb923c); color: white; }
        &.success { background: linear-gradient(45deg, #10b981, #34d399); color: white; }
        &.info { background: linear-gradient(45deg, #3b82f6, #60a5fa); color: white; }
        &.warning { background: linear-gradient(45deg, #f59e0b, #fbbf24); color: white; }
      }
      
      .stat-title {
        color: var(--text-secondary);
        font-size: 16px;
        font-weight: 500;
      }
    }
    
    .stat-body {
      .stat-value {
        font-size: 36px;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1;
        margin-bottom: 8px;
        
        &.danger {
          color: var(--danger-color);
        }
      }
      
      .stat-description {
        color: var(--text-light);
        font-size: 14px;
      }
    }
  }
}

.info-card {
  margin-bottom: 24px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    
    .card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text-primary);
      font-weight: 600;
      font-size: 16px;
    }
  }
  
  .empty-state {
    text-align: center;
    padding: 40px 20px;
    color: var(--text-light);
    
    p {
      margin: 16px 0 0 0;
      font-size: 16px;
    }
  }
}

.warning-list {
  .warning-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid #f1f5f9;
    
    &:last-child {
      border-bottom: none;
    }
    
    .warning-info {
      display: flex;
      flex-direction: column;
      gap: 4px;
      
      .equipment-name {
        color: var(--text-primary);
        font-weight: 500;
      }
      
      .stock-info {
        color: var(--text-secondary);
        font-size: 14px;
      }
    }
  }
}

.quick-actions {
  border-radius: 12px;
  border: 1px solid var(--border-color);
  
  .action-buttons {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    
    .el-button {
      height: 48px;
      font-weight: 500;
      border-radius: 8px;
      
      .el-icon {
        margin-right: 8px;
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .dashboard-page {
    padding: 16px;
  }
  
  .stats-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  
  .page-header {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }
  
  .action-buttons {
    grid-template-columns: 1fr;
  }
}
</style>