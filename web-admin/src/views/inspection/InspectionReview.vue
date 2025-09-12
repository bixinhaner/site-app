<template>
  <div class="page">
    <div class="page-header">
      <h1>检查审核台</h1>
      <div>
        <el-button @click="refresh"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>
    <el-card v-loading="loading">
      <div v-if="inspection">
        <p><b>站点：</b>{{ inspection.site_name }}</p>
        <p><b>检查员：</b>{{ inspection.inspector_name }}</p>
        <p><b>状态：</b>{{ inspection.status }}</p>
        <el-space>
          <el-button type="success" @click="doReview('approve')" :disabled="inspection.status !== 'under_review'">通过</el-button>
          <el-button type="danger" @click="doReview('reject')" :disabled="inspection.status !== 'under_review'">驳回</el-button>
        </el-space>
      </div>
      <div v-else>请选择一条待审核检查或通过记录列表进入。</div>
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
const inspection = ref(null)

const refresh = async () => {
  const id = route.query.inspectionId
  if (!id) return
  try {
    loading.value = true
    inspection.value = await apiClient.get(`/api/inspections/detail/${id}`)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载检查详情失败')
  } finally {
    loading.value = false
  }
}

const doReview = async (action) => {
  try {
    await apiClient.post(`/api/inspections/review`, { action, inspection_id: inspection.value.id })
    ElMessage.success('审核已提交')
    await refresh()
  } catch (e) {
    console.error(e)
    ElMessage.error('审核失败')
  }
}

onMounted(refresh)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
</style>

