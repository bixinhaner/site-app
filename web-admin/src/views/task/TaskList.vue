<template>
  <div class="page">
    <div class="page-header">
      <h1>任务列表</h1>
      <div class="header-actions">
        <el-select v-model="status" clearable placeholder="状态筛选" style="width: 160px">
          <el-option v-for="s in statuses" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-button @click="loadTasks"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <el-card>
      <el-table :data="tasks" v-loading="loading" stripe>
        <el-table-column prop="task_title" label="任务标题" min-width="220" />
        <el-table-column prop="site_name" label="站点" width="160" />
        <el-table-column prop="assignee_name" label="分配给" width="120" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }"><el-tag>{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="review(row)"><el-icon><Stamp /></el-icon>审核</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import apiClient from '../../api/auth'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
const loading = ref(false)
const tasks = ref([])
const status = ref('')
const statuses = [
  { label: '待分配', value: 'pending' },
  { label: '已分配', value: 'assigned' },
  { label: '进行中', value: 'in_progress' },
  { label: '待审核', value: 'under_review' },
  { label: '已完成', value: 'completed' }
]

const loadTasks = async () => {
  try {
    loading.value = true
    const res = await apiClient.get('/api/tasks/', { params: status.value ? { status: status.value } : {} })
    tasks.value = res || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载任务失败')
  } finally {
    loading.value = false
  }
}

const review = (row) => {
  router.push({ name: 'TaskReview', query: { taskId: row.id } })
}

onMounted(loadTasks)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
</style>

