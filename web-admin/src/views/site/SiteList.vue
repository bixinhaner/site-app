<template>
  <div class="page">
    <div class="page-header">
      <h1>{{ t('route.SiteList') }}</h1>
      <div class="header-actions">
        <el-input v-model="keyword" placeholder="搜索站点名称/编码/城市（动态生效）" clearable style="width: 260px" />
        <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 140px" @change="onStatusFilterChange">
          <el-option label="规划中" value="planning" />
          <el-option label="规划完成" value="planned" />
          <el-option label="施工中" value="construction" />
          <el-option label="已开通" value="operational" />
          <el-option label="维护中" value="maintenance" />
        </el-select>
        <el-button v-if="canManageSurveyStage" @click="openSurveyStageBatch">
          <el-icon><Operation /></el-icon>
          勘察批量
        </el-button>
        <el-popover placement="bottom" :width="280" trigger="click">
          <template #reference>
            <el-button>
              <el-icon><Sort /></el-icon>
              排序
            </el-button>
          </template>
          <div class="sort-panel">
            <el-form label-width="72px" size="small">
              <el-form-item label="字段">
                <el-select v-model="sortBy" style="width: 100%">
                  <el-option label="创建时间" value="created_at" />
                  <el-option label="更新时间" value="updated_at" />
                  <el-option label="站点编码" value="site_code" />
                  <el-option label="站点名称" value="site_name" />
                  <el-option label="城市" value="city" />
                  <el-option label="状态" value="status" />
                </el-select>
              </el-form-item>
              <el-form-item label="方向">
                <el-radio-group v-model="sortOrder">
                  <el-radio-button label="desc">降序</el-radio-button>
                  <el-radio-button label="asc">升序</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <el-form-item label=" ">
                <el-button size="small" @click="resetSort">恢复默认</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-popover>
        <el-button :loading="exporting" @click="exportSites">
          <el-icon><Download /></el-icon>
          导出Excel
        </el-button>
        <el-button v-if="canBatchEditSite" type="warning" :disabled="selectedSites.length === 0" @click="openBatchEdit">
          <el-icon><Edit /></el-icon>
          批量编辑
          <span v-if="selectedSites.length">({{ selectedSites.length }})</span>
        </el-button>
        <el-button v-if="canBatchEditSite" @click="openBatchExcelUpdate">
          <el-icon><Upload /></el-icon>
          Excel回写
        </el-button>
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
        <el-dropdown
          v-if="canRebuildSiteProgress"
          trigger="click"
          @command="handleMoreCommand"
        >
          <el-button :loading="rebuildSiteProgressLoading">
            <el-icon><Operation /></el-icon>
            {{ t('siteList.actions.more') }}
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                command="rebuild-site-progress"
                :disabled="rebuildSiteProgressLoading"
              >
                {{ t('siteList.actions.rebuildProgress') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <!-- 筛选按钮已移除：搜索栏与筛选项动态生效 -->
      </div>
    </div>

    <el-card>
      <el-table ref="siteTableRef" :data="displayedSites" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column v-if="canBatchEditSite" type="selection" width="48" />
        <el-table-column prop="site_code" label="站点编码" width="140" />
        <el-table-column prop="site_name" label="站点名称" min-width="180" />
        <el-table-column prop="site_type" label="类型" width="120" />
        <el-table-column prop="city" label="城市" width="120" />
        <el-table-column prop="status" label="状态" width="140">
          <template #default="{ row }">
            <el-tag>{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ssv_passed" label="SSV" width="120">
          <template #default="{ row }">
            <el-tag :type="row.ssv_passed ? 'success' : 'info'">{{ row.ssv_passed ? '已通过' : '未通过' }}</el-tag>
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

    <el-dialog
      v-model="batchEditVisible"
      title="批量编辑站点信息"
      width="92%"
      top="4vh"
      :close-on-click-modal="false"
    >
      <el-alert
        type="info"
        :closable="false"
        title="支持逐条编辑不同值：每行一个站点，直接修改后统一提交。"
      />
      <el-table :data="batchRows" border size="small" max-height="460" style="margin-top: 12px;">
        <el-table-column prop="site_code" label="站点编码" width="140" fixed="left" />
        <el-table-column label="站点名称" width="180" fixed="left">
          <template #default="{ row }">
            <el-input v-model="row.site_name" placeholder="必填" />
          </template>
        </el-table-column>
        <el-table-column label="类型" width="140">
          <template #default="{ row }">
            <el-input v-model="row.site_type" />
          </template>
        </el-table-column>
        <el-table-column label="省份" width="140">
          <template #default="{ row }">
            <el-input v-model="row.province" />
          </template>
        </el-table-column>
        <el-table-column label="城市" width="140">
          <template #default="{ row }">
            <el-input v-model="row.city" />
          </template>
        </el-table-column>
        <el-table-column label="区县" width="140">
          <template #default="{ row }">
            <el-input v-model="row.district" />
          </template>
        </el-table-column>
        <el-table-column label="地址" min-width="220">
          <template #default="{ row }">
            <el-input v-model="row.address" />
          </template>
        </el-table-column>
        <el-table-column label="纬度" width="140">
          <template #default="{ row }">
            <el-input-number
              v-model="row.latitude"
              :min="-90"
              :max="90"
              :step="0.000001"
              :controls="false"
              style="width: 100%"
            />
          </template>
        </el-table-column>
        <el-table-column label="经度" width="140">
          <template #default="{ row }">
            <el-input-number
              v-model="row.longitude"
              :min="-180"
              :max="180"
              :step="0.000001"
              :controls="false"
              style="width: 100%"
            />
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="120">
          <template #default="{ row }">
            <el-select v-model="row.priority" style="width: 100%">
              <el-option label="高" value="high" />
              <el-option label="普通" value="normal" />
              <el-option label="低" value="low" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="联系人" width="140">
          <template #default="{ row }">
            <el-input v-model="row.contact_person" />
          </template>
        </el-table-column>
        <el-table-column label="联系电话" width="160">
          <template #default="{ row }">
            <el-input v-model="row.contact_phone" />
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="220">
          <template #default="{ row }">
            <el-input v-model="row.description" />
          </template>
        </el-table-column>
      </el-table>

      <div v-if="batchResult" class="batch-result">
        <el-alert
          :type="failedBatchResults.length ? 'warning' : 'success'"
          :closable="false"
          :title="batchResultTitle"
        />
        <el-table v-if="failedBatchResults.length" :data="failedBatchResults" border size="small" max-height="220" style="margin-top: 8px;">
          <el-table-column prop="row_index" label="行号" width="80" />
          <el-table-column prop="site_id" label="站点ID" width="100" />
          <el-table-column prop="site_code" label="站点编码" width="140" />
          <el-table-column label="失败原因" min-width="280">
            <template #default="{ row }">
              {{ (row.errors || []).join('；') || '未知错误' }}
            </template>
          </el-table-column>
        </el-table>
      </div>

      <template #footer>
        <el-button @click="batchEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchSubmitting" @click="submitBatchEdit">提交批量修改</el-button>
      </template>
    </el-dialog>
  </div>
  
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import request from '@/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '../../stores/user'
import { createDebouncedTracker } from '@/utils/operationTrack'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const canManagePlanning = computed(() => userStore.hasPermission('sites:lld:write'))
const canCreateSite = computed(() => userStore.hasPermission('sites:create:write'))
const canManageSurveyStage = computed(() => userStore.hasPermission('sites:survey-stage:write'))
const canBatchEditSite = computed(() => userStore.hasPermission('sites:update:write'))
const canRebuildSiteProgress = computed(() => (
  userStore.isAdmin
  || userStore.isManager
  || userStore.hasPermission('sites:create:write')
  || userStore.hasPermission('sites:update:write')
  || userStore.hasPermission('sites:survey-stage:write')
))
const siteTableRef = ref(null)
const loading = ref(false)
const sites = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const statusFilter = ref('')
const assigneeFilter = ref(null)
const exporting = ref(false)
const sortBy = ref('created_at')
const sortOrder = ref('desc')

const userOptions = ref([])
const usersLoaded = ref(false)

const assignVisible = ref(false)
const assigning = ref(false)
const selectedAssignee = ref(null)
const siteToAssign = ref(null)
const selectedSites = ref([])
const batchEditVisible = ref(false)
const batchSubmitting = ref(false)
const batchRows = ref([])
const batchResult = ref(null)
const rebuildSiteProgressLoading = ref(false)

const trackSearchDebounced = createDebouncedTracker(800)
const trackSearch = () => {
  trackSearchDebounced({
    module: '站点管理',
    action: '查询',
    object_type: '站点',
    data: {
      keyword: keyword.value || undefined,
      status: statusFilter.value || undefined,
      sort_by: sortBy.value || undefined,
      sort_order: sortOrder.value || undefined,
    },
  })
}

const onStatusFilterChange = () => {
  trackSearch()
  reload()
}

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
    if (sortBy.value) params.sort_by = sortBy.value
    if (sortOrder.value) params.sort_order = sortOrder.value
    const res = await request.get('/api/sites/search', { params })
    const list = Array.isArray(res?.sites) ? res.sites : []
    sites.value = list
    total.value = typeof res?.total === 'number' ? res.total : list.length
    selectedSites.value = []
    if (siteTableRef.value?.clearSelection) siteTableRef.value.clearSelection()
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

const openSurveyStageBatch = () => {
  router.push({ name: 'SiteSurveyStageBatch' })
}

const openBatchExcelUpdate = () => {
  router.push({ name: 'SiteBasicBatch', query: { mode: 'batchUpdate' } })
}

const handleMoreCommand = async (command) => {
  if (command === 'rebuild-site-progress') {
    await rebuildAllSiteProgress()
  }
}

const handleSelectionChange = (rows) => {
  selectedSites.value = Array.isArray(rows) ? rows : []
}

const openBatchEdit = () => {
  if (!selectedSites.value.length) {
    ElMessage.warning('请先选择要编辑的站点')
    return
  }
  batchRows.value = selectedSites.value.map((site) => ({
    id: site.id,
    site_code: site.site_code || '',
    site_name: site.site_name || '',
    site_type: site.site_type || '',
    address: site.address || '',
    latitude: site.latitude ?? null,
    longitude: site.longitude ?? null,
    province: site.province || '',
    city: site.city || '',
    district: site.district || '',
    priority: site.priority || 'normal',
    description: site.description || '',
    contact_person: site.contact_person || '',
    contact_phone: site.contact_phone || '',
  }))
  batchResult.value = null
  batchEditVisible.value = true
}

const validateBatchRows = () => {
  for (let i = 0; i < batchRows.value.length; i += 1) {
    const row = batchRows.value[i]
    if (!String(row.site_name || '').trim()) {
      ElMessage.warning(`第 ${i + 1} 行站点名称不能为空`)
      return false
    }
    if (row.latitude !== null && row.latitude !== undefined && (row.latitude < -90 || row.latitude > 90)) {
      ElMessage.warning(`第 ${i + 1} 行纬度超出范围（-90 到 90）`)
      return false
    }
    if (row.longitude !== null && row.longitude !== undefined && (row.longitude < -180 || row.longitude > 180)) {
      ElMessage.warning(`第 ${i + 1} 行经度超出范围（-180 到 180）`)
      return false
    }
  }
  return true
}

const buildBatchPayload = () => ({
  updates: batchRows.value.map((row) => ({
    site_id: row.id,
    site_name: String(row.site_name || '').trim(),
    site_type: row.site_type || null,
    address: row.address || null,
    latitude: row.latitude ?? null,
    longitude: row.longitude ?? null,
    province: row.province || null,
    city: row.city || null,
    district: row.district || null,
    priority: row.priority || 'normal',
    description: row.description || null,
    contact_person: row.contact_person || null,
    contact_phone: row.contact_phone || null,
  })),
})

const submitBatchEdit = async () => {
  if (!batchRows.value.length) {
    ElMessage.warning('没有可提交的站点数据')
    return
  }
  if (!validateBatchRows()) return

  try {
    batchSubmitting.value = true
    const res = await request.put('/api/sites/batch-update', buildBatchPayload())
    batchResult.value = res
    const successCount = Number(res?.success_count || 0)
    const failedCount = Number(res?.failed_count || 0)
    if (failedCount === 0) {
      ElMessage.success(`批量修改完成，共成功 ${successCount} 条`)
      batchEditVisible.value = false
      await reload()
      return
    }
    ElMessage.warning(`批量修改完成：成功 ${successCount} 条，失败 ${failedCount} 条`)
    await reload()
  } catch (e) {
    console.error(e)
    const msg = await extractErrorDetail(e)
    ElMessage.error('批量修改失败: ' + msg)
  } finally {
    batchSubmitting.value = false
  }
}

const formatExportDate = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const hours = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  return `${year}${month}${day}_${hours}${minutes}`
}

const resetSort = () => {
  sortBy.value = 'created_at'
  sortOrder.value = 'desc'
}

const extractErrorDetail = async (error) => {
  const data = error?.response?.data
  if (!data) return error?.message || '网络错误'
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      try {
        const json = JSON.parse(text)
        return json?.detail || text || error?.message || '网络错误'
      } catch {
        return text || error?.message || '网络错误'
      }
    } catch {
      return error?.message || '网络错误'
    }
  }
  return data?.detail || error?.message || '网络错误'
}

const exportSites = async () => {
  try {
    exporting.value = true
    const params = {}
    if (keyword.value) params.keyword = keyword.value
    if (statusFilter.value) params.status = statusFilter.value
    if (assigneeFilter.value) params.assigned_to = assigneeFilter.value

    const blob = await request.get('/api/sites/export', { params, responseType: 'blob' })
    const fileName = `站点列表_${formatExportDate()}.xlsx`

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    ElMessage.success('导出成功')
  } catch (e) {
    console.error(e)
    const msg = await extractErrorDetail(e)
    ElMessage.error('导出失败: ' + msg)
  } finally {
    exporting.value = false
  }
}

const rebuildAllSiteProgress = async () => {
  if (rebuildSiteProgressLoading.value) return

  try {
    await ElMessageBox.confirm(
      t('siteList.progressRebuild.confirm.message'),
      t('siteList.progressRebuild.confirm.title'),
      {
        type: 'warning',
        confirmButtonText: t('siteList.progressRebuild.confirm.confirmButton'),
        cancelButtonText: t('common.cancel'),
        closeOnClickModal: false,
      },
    )
  } catch {
    return
  }

  try {
    rebuildSiteProgressLoading.value = true
    const res = await request.post(
      '/api/sites/progress/rebuild',
      {
        force: true,
        reason: 'manual_site_progress_rebuild_from_web',
      },
      {
        timeout: 300000,
      },
    )
    await reload()
    ElMessage.success(
      t('siteList.progressRebuild.messages.success', {
        requestedCount: Number(res?.requested_count || 0),
        rebuiltCount: Number(res?.rebuilt_count || 0),
        skippedCount: Number(res?.skipped_count || 0),
      }),
    )
  } catch (e) {
    console.error(e)
    const msg = await extractErrorDetail(e)
    ElMessage.error(t('siteList.progressRebuild.messages.failed', { message: msg }))
  } finally {
    rebuildSiteProgressLoading.value = false
  }
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
const failedBatchResults = computed(() => {
  const rows = Array.isArray(batchResult.value?.results) ? batchResult.value.results : []
  return rows.filter(row => !row.success)
})
const batchResultTitle = computed(() => {
  if (!batchResult.value) return ''
  return `提交完成：成功 ${batchResult.value.success_count || 0} 条，失败 ${batchResult.value.failed_count || 0} 条`
})

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
  trackSearch()
  reload()
})

watch([sortBy, sortOrder], () => {
  currentPage.value = 1
  trackSearch()
  reload()
})

watch(batchEditVisible, (visible) => {
  if (visible) return
  batchRows.value = []
  batchResult.value = null
})
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; flex-wrap: wrap; }
.pagination { margin-top: 12px; display:flex; justify-content: flex-end; }
.sort-panel :deep(.el-radio-group) { width: 100%; }
.sort-panel :deep(.el-radio-button) { width: 50%; }
.sort-panel :deep(.el-radio-button__inner) { width: 100%; text-align: center; }
.batch-result { margin-top: 12px; }
</style>
