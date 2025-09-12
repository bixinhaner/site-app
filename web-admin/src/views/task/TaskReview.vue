<template>
  <div class="page">
    <div class="page-header">
      <h1>任务审核台</h1>
      <div>
        <el-button @click="refresh"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>
    <el-card v-loading="loading">
      <div v-if="task">
        <p><b>标题：</b>{{ task.task_title }}</p>
        <p><b>站点：</b>{{ task.site_name }} ({{ task.site_code }})</p>
        <p><b>状态：</b>{{ task.status }}</p>
        <el-space>
          <el-button type="success" @click="doReview('approved')" :disabled="task.status !== 'submitted'">通过</el-button>
          <el-button type="danger" @click="doReview('rejected')" :disabled="task.status !== 'submitted'">驳回</el-button>
        </el-space>
      </div>
      <div v-else>请选择一条待审核任务或通过任务列表进入。</div>
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
const task = ref(null)

const refresh = async () => {
  const id = route.query.taskId
  if (!id) return
  try {
    loading.value = true
    task.value = await apiClient.get(`/api/tasks/${id}`)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载任务失败')
  } finally {
    loading.value = false
  }
}

const doReview = async (result) => {
  try {
    await apiClient.post(`/api/tasks/${task.value.id}/review`, { result })
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

