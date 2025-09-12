<template>
  <div class="page">
    <div class="page-header">
      <h1>任务审核台</h1>
      <div>
        <el-button @click="refresh"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>
    <el-card v-loading="loading">
      <template v-if="task">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="标题">{{ task.task_title }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ typeText(task.task_type) }}</el-descriptions-item>
          <el-descriptions-item label="站点">{{ task.site_name }} ({{ task.site_code }})</el-descriptions-item>
          <el-descriptions-item label="分配给">{{ task.assignee_name }}</el-descriptions-item>
          <el-descriptions-item label="优先级">{{ priorityText(task.priority) }}</el-descriptions-item>
          <el-descriptions-item label="状态"><el-tag>{{ statusText(task.status) }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="截止时间">{{ formatDateTime(task.due_date) }}</el-descriptions-item>
          <el-descriptions-item label="分配时间">{{ formatDateTime(task.assigned_at) }}</el-descriptions-item>
        </el-descriptions>

        <el-divider />
        <el-form label-width="100px">
          <el-form-item label="审核意见">
            <el-input v-model="comments" type="textarea" :rows="3" placeholder="请输入审核意见" />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="requireRecheck">驳回后要求重新检查（会回到已分配状态）</el-checkbox>
          </el-form-item>
          <el-form-item>
            <el-space>
              <el-button type="success" :disabled="task.status !== 'submitted'" @click="doReview('approved')">通过</el-button>
              <el-button type="danger" :disabled="task.status !== 'submitted'" @click="doReview('rejected')">驳回</el-button>
            </el-space>
          </el-form-item>
        </el-form>
      </template>
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
const comments = ref('')
const requireRecheck = ref(false)

const statuses = [
  { label: '已提交', value: 'submitted' },
  { label: '待审核', value: 'under_review' },
  { label: '已通过', value: 'approved' },
  { label: '已驳回', value: 'rejected' }
]
const taskTypes = [
  { label: '新站点设备安装', value: 'opening_inspection' },
  { label: '断电问题', value: 'power_issue' },
  { label: '传输问题', value: 'transmission_issue' },
  { label: 'GPS问题', value: 'gps_issue' },
  { label: '信号问题', value: 'signal_issue' }
]
const priorities = [
  { label: '低', value: 'low' },
  { label: '普通', value: 'normal' },
  { label: '高', value: 'high' },
  { label: '紧急', value: 'urgent' }
]

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
    await apiClient.post(`/api/tasks/${task.value.id}/review`, { result, comments: comments.value, require_recheck: requireRecheck.value })
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
const statusText = (v) => (statuses.find(s => s.value === v)?.label || v)
const typeText = (v) => (taskTypes.find(t => t.value === v)?.label || v)
const priorityText = (v) => (priorities.find(p => p.value === v)?.label || v)
const formatDateTime = (val) => val ? new Date(val).toLocaleString() : '-'
