<template>
  <div class="page">
    <div class="page-header">
      <h1>站点详情</h1>
      <el-button @click="$router.back()"><el-icon><Back /></el-icon>返回</el-button>
    </div>
    <el-card v-loading="loading">
      <div class="info-grid" v-if="site">
        <div class="item"><span class="label">站点名称</span><span class="value">{{ site.site_name }}</span></div>
        <div class="item"><span class="label">站点编码</span><span class="value">{{ site.site_code }}</span></div>
        <div class="item"><span class="label">类型</span><span class="value">{{ site.site_type || '-' }}</span></div>
        <div class="item"><span class="label">状态</span><span class="value">{{ site.status }}</span></div>
        <div class="item"><span class="label">地址</span><span class="value">{{ site.address || '-' }}</span></div>
        <div class="item"><span class="label">负责人</span><span class="value">{{ site.assigned_to || '-' }}</span></div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import apiClient from '../../api/auth'
import { ElMessage } from 'element-plus'

const route = useRoute()
const loading = ref(false)
const site = ref(null)

const load = async () => {
  try {
    loading.value = true
    const res = await apiClient.get(`/api/sites/${route.params.id}`)
    site.value = res
  } catch (e) {
    console.error(e)
    ElMessage.error('加载站点详情失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.info-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.item .label { color: var(--text-secondary); margin-right:8px; }
.item .value { color: var(--text-primary); font-weight: 500; }
</style>

