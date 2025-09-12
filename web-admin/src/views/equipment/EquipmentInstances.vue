<template>
  <div class="page">
    <div class="page-header">
      <h1>设备实例清单</h1>
      <div class="header-actions">
        <el-input v-model="equipmentId" placeholder="输入设备类型ID" style="width: 220px" />
        <el-select v-model="status" clearable placeholder="状态" style="width: 160px">
          <el-option label="库存中" value="in_stock" />
          <el-option label="已分配" value="allocated" />
          <el-option label="已出库" value="issued" />
          <el-option label="已退库" value="returned" />
        </el-select>
        <el-button type="primary" @click="load"><el-icon><Search /></el-icon>查询</el-button>
      </div>
    </div>
    <el-card>
      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column prop="serial_number" label="SN" width="200" />
        <el-table-column prop="barcode" label="条码" width="200" />
        <el-table-column prop="vendor" label="供应商" width="140" />
        <el-table-column prop="warehouse_name" label="所在仓库" width="160" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { stockApi } from '../../api/stock'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const equipmentId = ref('')
const status = ref('')
const items = ref([])

const load = async () => {
  if (!equipmentId.value) {
    ElMessage.info('请输入设备类型ID')
    return
  }
  try {
    loading.value = true
    const res = await stockApi.getEquipmentInstances(equipmentId.value, status.value ? { status: status.value } : {})
    items.value = res?.instances || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载设备实例失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
</style>

