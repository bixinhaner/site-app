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
        <el-button v-if="isAdmin || isManager" type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建任务</el-button>
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
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <!-- 管理端操作 -->
            <el-button
              v-if="(isAdmin || isManager) && ['submitted','under_review'].includes(row.status)"
              link type="primary" size="small" @click="openReview(row)">
              <el-icon><Stamp /></el-icon>审核
            </el-button>
            <el-button
              v-if="(isAdmin) && ['pending','assigned','rejected'].includes(row.status)"
              link type="danger" size="small" @click="deleteTask(row)">
              <el-icon><Delete /></el-icon>删除
            </el-button>

            <!-- 执行端（被分配人）快捷状态变更 -->
            <el-button v-if="isSelf(row) && row.status==='assigned'" link size="small" type="success" @click="changeStatus(row,'accepted')">
              接受
            </el-button>
            <el-button v-if="isSelf(row) && row.status==='accepted'" link size="small" type="primary" @click="changeStatus(row,'in_progress')">
              开始
            </el-button>
            <el-button v-if="isSelf(row) && row.status==='in_progress'" link size="small" type="warning" @click="submitWithComments(row)">
              提交
            </el-button>
            <el-button v-if="isSelf(row) && row.status==='approved'" link size="small" type="success" @click="changeStatus(row,'completed')">
              标记完成
            </el-button>

            <!-- 通用：详情 -->
            <el-button link size="small" @click="openDetails(row)"><el-icon><View /></el-icon>详情</el-button>
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

    <!-- 任务详情抽屉 -->
    <el-drawer v-model="detailsVisible" title="任务详情" size="50%">
      <div v-if="currentTask">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="标题">{{ currentTask.task_title }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ typeText(currentTask.task_type) }}</el-descriptions-item>
          <el-descriptions-item label="站点">{{ currentTask.site_name }} ({{ currentTask.site_code }})</el-descriptions-item>
          <el-descriptions-item label="分配给">{{ currentTask.assignee_name }}</el-descriptions-item>
          <el-descriptions-item label="优先级">{{ priorityText(currentTask.priority) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusText(currentTask.status) }}</el-descriptions-item>
          <el-descriptions-item label="分配时间">{{ formatDateTime(currentTask.assigned_at) }}</el-descriptions-item>
          <el-descriptions-item label="截止时间">{{ formatDateTime(currentTask.due_date) }}</el-descriptions-item>
        </el-descriptions>
        <div style="margin-top: 12px;">
          <div><b>任务描述：</b></div>
          <div style="white-space: pre-wrap;">{{ currentTask.task_description || '-' }}</div>
        </div>
      </div>
    </el-drawer>

    <!-- 新建任务弹窗 -->
    <el-dialog v-model="createVisible" title="新建任务" width="640px" @close="resetCreate">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="100px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="任务类型" prop="task_type">
              <el-select v-model="createForm.task_type" placeholder="选择类型">
                <el-option v-for="t in taskTypes" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="createForm.priority">
                <el-option v-for="p in priorities" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="站点" prop="site_id">
              <el-select v-model="createForm.site_id" filterable placeholder="选择站点" @visible-change="v=> v && loadSites()">
                <el-option v-for="s in siteOptions" :key="s.id" :label="s.site_name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分配给" prop="assigned_to">
              <el-select v-model="createForm.assigned_to" filterable placeholder="选择人员" @visible-change="v=> v && loadUsers()">
                <el-option v-for="u in engineerOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="任务标题" prop="task_title">
          <el-input v-model="createForm.task_title" placeholder="请输入任务标题" />
        </el-form-item>

        <el-form-item label="任务描述">
          <el-input v-model="createForm.task_description" type="textarea" :rows="3" placeholder="描述任务内容..." />
        </el-form-item>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="截止时间">
              <el-date-picker v-model="createForm.due_date" type="datetime" placeholder="选择截止时间" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预计工期">
              <el-input-number v-model="createForm.estimated_duration" :min="1" :max="240" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import apiClient from '../../api/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
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
    console.error('加载任务失败:', e?.response?.data || e?.message || e)
    // 回退：去除所有筛选重试一次，最大限度保证页面可用
    try {
      const res2 = await apiClient.get('/api/tasks/', { params: { skip: (currentPage.value - 1) * pageSize.value, limit: pageSize.value } })
      tasks.value = Array.isArray(res2) ? res2 : []
      total.value = (currentPage.value - 1) * pageSize.value + tasks.value.length + (tasks.value.length === pageSize.value ? pageSize.value : 0)
      ElMessage.warning(e?.response?.data?.detail || '筛选条件不被后端接受，已回退为基础列表')
    } catch (e2) {
      console.error('回退请求仍失败:', e2?.response?.data || e2?.message || e2)
      ElMessage.error(e?.response?.data?.detail || '加载任务失败')
    }
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

// 角色判断
const isAdmin = computed(() => userStore.user?.role === 'admin')
const isManager = computed(() => userStore.user?.role === 'manager')
const isInspector = computed(() => userStore.user?.role === 'inspector')
const isSelf = (row) => userStore.user && row.assigned_to === userStore.user.id

// 详情抽屉
const detailsVisible = ref(false)
const currentTask = ref(null)
const openDetails = async (row) => {
  try {
    currentTask.value = await apiClient.get(`/api/tasks/${row.id}`)
    detailsVisible.value = true
  } catch (e) {
    ElMessage.error('加载任务详情失败')
  }
}

// 快捷状态变更
const changeStatus = async (row, newStatus, comments) => {
  try {
    await apiClient.post(`/api/tasks/${row.id}/status`, { status: newStatus, comments })
    ElMessage.success('状态已更新')
    await reload()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '状态更新失败')
  }
}

// 提交时可附备注
const submitWithComments = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入提交备注（可选）', '提交任务', {
      confirmButtonText: '提交',
      cancelButtonText: '取消',
      inputPlaceholder: '本次提交说明...'
    })
    await changeStatus(row, 'submitted', value)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('提交已取消或失败')
  }
}

// 删除任务（仅管理员）
const deleteTask = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除任务“${row.task_title}”吗？`, '删除任务', {
      type: 'warning'
    })
    await apiClient.delete(`/api/tasks/${row.id}`)
    ElMessage.success('已删除')
    await reload()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

// 创建任务
const createVisible = ref(false)
const creating = ref(false)
const createFormRef = ref()
const createForm = ref({
  task_type: 'opening_inspection',
  priority: 'normal',
  site_id: null,
  assigned_to: null,
  task_title: '',
  task_description: '',
  due_date: '',
  estimated_duration: null
})
const createRules = {
  task_type: [{ required: true, message: '请选择任务类型', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  site_id: [{ required: true, message: '请选择站点', trigger: 'change' }],
  assigned_to: [{ required: true, message: '请选择人员', trigger: 'change' }],
  task_title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }]
}
const siteOptions = ref([])
const engineerOptions = ref([])
const loadSites = async () => {
  try {
    const res = await apiClient.get('/api/sites/', { params: { limit: 200 } })
    siteOptions.value = Array.isArray(res) ? res : []
  } catch (e) { /* ignore */ }
}
// 使用现有的 userOptions 过滤出工程师
const userOptions = ref([])
const loadUsers = async () => {
  try {
    const res = await apiClient.get('/api/users/', { params: { limit: 200 } })
    userOptions.value = res || []
    engineerOptions.value = userOptions.value.filter(u => u.role === 'inspector')
  } catch (e) { /* ignore */ }
}
const openCreate = () => { createVisible.value = true; loadSites(); loadUsers() }
const resetCreate = () => {
  createForm.value = { task_type: 'opening_inspection', priority: 'normal', site_id: null, assigned_to: null, task_title: '', task_description: '', due_date: '', estimated_duration: null }
  if (createFormRef.value) createFormRef.value.clearValidate()
}
const submitCreate = async () => {
  try {
    await createFormRef.value.validate()
    creating.value = true
    const payload = {
      task_title: createForm.value.task_title,
      task_type: createForm.value.task_type,
      task_description: createForm.value.task_description || undefined,
      priority: createForm.value.priority,
      site_id: createForm.value.site_id,
      assigned_to: createForm.value.assigned_to,
      due_date: createForm.value.due_date ? new Date(createForm.value.due_date).toISOString() : undefined,
      estimated_duration: createForm.value.estimated_duration || undefined
    }
    await apiClient.post('/api/tasks/', payload)
    ElMessage.success('任务创建成功')
    createVisible.value = false
    resetCreate()
    await reload()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.detail || '创建失败，可能是权限不足或参数错误')
    }
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pagination { margin-top: 12px; display:flex; justify-content: flex-end; }
</style>
