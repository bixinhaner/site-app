<template>
  <div class="page-container">
    <div class="page-header">
      <h2>出入库记录</h2>
      <el-button @click="loadTransactions" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <div class="card">
      <el-table :data="transactionList" style="width: 100%" v-loading="loading">
        <el-table-column prop="document_number" label="单据编号" width="150" />
        <el-table-column prop="transaction_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.transaction_type === 'stock_in' ? 'success' : 'warning'">
              {{ row.transaction_type === 'stock_in' ? '入库' : '出库' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operator_name" label="操作人" width="120" />
        <el-table-column prop="total_quantity" label="总数量" width="100" />
        <el-table-column prop="operation_time" label="操作时间" width="180" />
        <el-table-column prop="notes" label="备注" min-width="150" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { stockApi } from '../../api/stock'

const loading = ref(false)
const transactionList = ref([])

const loadTransactions = async () => {
  try {
    loading.value = true
    const response = await stockApi.getStockTransactions()
    transactionList.value = response.transactions || []
  } catch (error) {
    console.error('加载记录失败:', error)
    ElMessage.error('加载记录失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadTransactions()
})
</script>