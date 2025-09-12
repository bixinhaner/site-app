<template>
  <div class="page">
    <div class="page-header">
      <h1>仓库管理</h1>
      <div class="header-actions">
        <el-button type="primary" @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>
    <el-card>
      <el-table :data="warehouses" v-loading="loading" stripe>
        <el-table-column prop="warehouse_code" label="仓库编码" width="160" />
        <el-table-column prop="warehouse_name" label="仓库名称" min-width="200" />
        <el-table-column prop="address" label="地址" min-width="240" />
        <el-table-column prop="contact_person" label="联系人" width="120" />
        <el-table-column prop="contact_phone" label="电话" width="140" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { stockApi } from '../../api/stock'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const warehouses = ref([])

const load = async () => {
  try {
    loading.value = true
    const res = await stockApi.getWarehouses()
    warehouses.value = res?.warehouses || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载仓库失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
</style>

