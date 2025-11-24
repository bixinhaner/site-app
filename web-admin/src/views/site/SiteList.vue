<template>
  <div class="page">
    <div class="page-header">
      <h1>站点列表</h1>
      <div class="header-actions">
        <el-input v-model="keyword" placeholder="搜索站点名称/编码/城市（动态生效）" clearable style="width: 260px" />
        <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 140px" @change="reload">
          <el-option label="规划中" value="planning" />
          <el-option label="规划完成" value="planned" />
          <el-option label="施工中" value="construction" />
          <el-option label="已开通" value="operational" />
          <el-option label="维护中" value="maintenance" />
        </el-select>
        <!-- <el-select v-model="assigneeFilter" placeholder="指派给" clearable style="width: 200px" filterable @visible-change="v=> v && loadUsers()" @change="reload">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
        </el-select> -->
        <el-button v-if="canCreateSite" type="primary" @click="createSite">
          <el-icon><Plus /></el-icon>
          新增站点
        </el-button>
        <el-button v-if="canManagePlanning" type="success" @click="openBatchPlanning">
          <el-icon><Operation /></el-icon>
          规划信息导入
        </el-button>
        <!-- 筛选按钮已移除：搜索栏与筛选项动态生效 -->
      </div>
    </div>

    <el-card>
      <el-table :data="displayedSites" v-loading="loading" stripe>
        <el-table-column prop="site_code" label="站点编码" width="140" />
        <el-table-column prop="site_name" label="站点名称" min-width="180" />
        <el-table-column prop="site_type" label="类型" width="120" />
        <el-table-column prop="city" label="城市" width="120" />
        <el-table-column prop="status" label="状态" width="140">
          <template #default="{ row }">
            <el-tag>{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <!-- <el-table-column prop="assigned_to" label="指派给" width="140">
          <template #default="{ row }">
            <span>{{ userName(row.assigned_to) }}</span>
          </template>
        </el-table-column> -->
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row)">
              <el-icon><View /></el-icon>
              详情
            </el-button>
            <el-button link type="success" size="small" @click="viewPlanning(row)">
              <el-icon><Operation /></el-icon>
              规划
            </el-button>
            <!-- <el-button link type="success" size="small" @click="openAssign(row)">
              <el-icon><User /></el-icon>
              分配
            </el-button> -->
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
          @size-change="reload"
          @current-change="reload"
        />
      </div>
    </el-card>

    <!-- 分配弹窗 -->
    <el-dialog v-model="assignVisible" title="分配站点" width="420px">
      <div>
        <el-select v-model="selectedAssignee" placeholder="选择人员" style="width: 100%" filterable @visible-change="v=> v && loadUsers()">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
        </el-select>
      </div>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="assigning" @click="confirmAssign">确定</el-button>
      </template>
    </el-dialog>
  </div>
  
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const userStore = useUserStore()
const canManagePlanning = computed(() => ['admin', 'manager', 'planner'].includes(userStore.user?.role))
const canCreateSite = computed(() => ['admin', 'manager'].includes(userStore.user?.role))
const loading = ref(false)
const sites = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const statusFilter = ref('')
const assigneeFilter = ref(null)

const userOptions = ref([])
const usersLoaded = ref(false)

const assignVisible = ref(false)
const assigning = ref(false)
const selectedAssignee = ref(null)
const siteToAssign = ref(null)

const reload = async () => {
  try {
    loading.value = true
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
    }
    if (keyword.value) params.keyword = keyword.value
    if (statusFilter.value) params.status = statusFilter.value
    if (assigneeFilter.value) params.assigned_to = assigneeFilter.value
    const res = await request.get('/api/sites/search', { params })
    const list = Array.isArray(res?.sites) ? res.sites : []
    sites.value = list
    total.value = typeof res?.total === 'number' ? res.total : list.length
  } catch (e) {
    console.error(e)
    ElMessage.error('加载站点失败')
  } finally {
    loading.value = false
  }
}

const viewDetail = (row) => {
  router.push({ name: 'SiteDetail', params: { id: row.id } })
}

const viewPlanning = (row) => {
  // 默认跳转到 LLD 新版站点规划页面
  router.push({ name: 'SitePlanningLld', params: { id: row.id } })
}

const createSite = () => {
  router.push({ name: 'SiteBasicBatch' })
}

const openBatchPlanning = () => {
  // 默认跳转到 LLD 新版规划导入页面
  router.push({ name: 'SitePlanningBatchLld' })
}

const openAssign = (row) => {
  siteToAssign.value = row
  selectedAssignee.value = row.assigned_to || null
  assignVisible.value = true
}

const confirmAssign = async () => {
  if (!siteToAssign.value) return
  if (!selectedAssignee.value) {
    ElMessage.warning('请选择人员')
    return
  }
  try {
    assigning.value = true
    await request.put(`/api/sites/${siteToAssign.value.id}`, { assigned_to: selectedAssignee.value })
    ElMessage.success('分配成功')
    assignVisible.value = false
    await reload()
  } catch (e) {
    console.error(e)
    ElMessage.error('分配失败')
  } finally {
    assigning.value = false
  }
}

const loadUsers = async () => {
  if (usersLoaded.value) return
  try {
    const res = await request.get('/api/users/', { params: { limit: 100 } })
    userOptions.value = res || []
    usersLoaded.value = true
  } catch (e) {
    // 非 admin/manager 会 403，忽略
    usersLoaded.value = true
  }
}

const displayedSites = computed(() => sites.value)

const userName = (id) => {
  const u = userOptions.value.find(u => u.id === id)
  return u ? (u.full_name || u.username) : (id || '-')
}

onMounted(() => {
  reload()
  // 预热用户列表（仅管理员有效）
  loadUsers()
})

// 关键字动态生效：重置到第1页并走后端搜索
watch(keyword, () => {
  currentPage.value = 1
  reload()
})
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
.pagination { margin-top: 12px; display:flex; justify-content: flex-end; }
</style>
