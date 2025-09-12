<template>
  <div class="page">
    <div class="page-header">
      <h1>任务列表</h1>
      <div class="header-actions">
        <el-input v-model="keyword" placeholder="搜索任务标题/站点" clearable style="width: 240px" />
        <el-select v-model="typeFilter" clearable placeholder="任务类型" style="width: 160px">
          <el-option v-for="t in taskTypes" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-select v-model="statusFilter" clearable placeholder="状态" style="width: 140px">
          <el-option v-for="s in statuses" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="priorityFilter" clearable placeholder="优先级" style="width: 120px">
          <el-option v-for="p in priorities" :key="p.value" :label="p.label" :value="p.value" />
        </el-select>
        <el-select v-model="assigneeFilter" clearable filterable placeholder="分配给" style="width: 180px" @visible-change="v=> v && loadUsers()">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
        </el-select>
        <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 260px" />
        <el-switch v-model="onlyMine" active-text="只看我的" />
        <el-button type="primary" @click="reload"><el-icon><Search /></el-icon>筛选</el-button>
      </div>
    </div>

    <el-card>
      <el-table :data="displayedTasks" v-loading="loading" stripe>
        <el-table-column prop="task_title" label="任务标题" min-width="240" />
        <el-table-column prop="task_type" label="类型" width="140">
          <template #default="{ row }">{{ typeText(row.task_type) }}</template>
        </el-table-column>
        <el-table-column prop="site_name" label="站点" width="160" />
        <el-table-column prop="assignee_name" label="分配给" width="120" />
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }"><el-tag :type="priorityTag(row.priority)">{{ priorityText(row.priority) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }"><el-tag>{{ statusText(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="due_date" label="截止时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.due_date) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openReview(row)" v-if="['submitted','under_review'].includes(row.status)"><el-icon><Stamp /></el-icon>审核</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="reload"
          @size-change="reload"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import apiClient from '../../api/auth'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const tasks = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const typeFilter = ref('')
const statusFilter = ref('')
const priorityFilter = ref('')
const assigneeFilter = ref(null)
const onlyMine = ref(false)
const dateRange = ref(null)
const userOptions = ref([])
const statuses = [
  { label: '待分配', value: 'pending' },
  { label: '已分配', value: 'assigned' },
  { label: '已接受', value: 'accepted' },
  { label: '进行中', value: 'in_progress' },
  { label: '已提交', value: 'submitted' },
  { label: '待审核', value: 'under_review' },
  { label: '已通过', value: 'approved' },
  { label: '已驳回', value: 'rejected' },
  { label: '已完成', value: 'completed' }
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

const reload = async () => {
  try {
    loading.value = true
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value
    }
    if (typeFilter.value) params.task_type = typeFilter.value
    if (statusFilter.value) params.status = statusFilter.value
    if (priorityFilter.value) params.priority = priorityFilter.value
    if (assigneeFilter.value) params.assigned_to = assigneeFilter.value
    if (onlyMine.value && userStore.user) params.assigned_to = userStore.user.id
    if (dateRange.value && dateRange.value.length === 2) {
      params.date_from = new Date(dateRange.value[0]).toISOString()
      params.date_to = new Date(dateRange.value[1]).toISOString()
    }
    const res = await apiClient.get('/api/tasks/', { params })
    tasks.value = Array.isArray(res) ? res : []
    total.value = (currentPage.value - 1) * pageSize.value + tasks.value.length + (tasks.value.length === pageSize.value ? pageSize.value : 0)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载任务失败')
  } finally {
    loading.value = false
  }
}

const loadUsers = async () => {
  try {
    const res = await apiClient.get('/api/users/', { params: { limit: 100 } })
    userOptions.value = res || []
  } catch (e) {
    // 权限不足时忽略
  }
}

const displayedTasks = computed(() => {
  if (!keyword.value) return tasks.value
  const kw = keyword.value.toLowerCase()
  return tasks.value.filter(t =>
    (t.task_title || '').toLowerCase().includes(kw) ||
    (t.site_name || '').toLowerCase().includes(kw)
  )
})

const typeText = (v) => (taskTypes.find(t => t.value === v)?.label || v)
const statusText = (v) => (statuses.find(s => s.value === v)?.label || v)
const priorityText = (v) => (priorities.find(p => p.value === v)?.label || v)
const priorityTag = (v) => ({ low: 'info', normal: 'success', high: 'warning', urgent: 'danger' }[v] || 'info')
const formatDateTime = (val) => val ? new Date(val).toLocaleString() : '-'

const openReview = (row) => {
  router.push({ name: 'TaskReview', query: { taskId: row.id } })
}

onMounted(() => {
  reload()
  loadUsers()
})
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pagination { margin-top: 12px; display:flex; justify-content: flex-end; }
</style>
