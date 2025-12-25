<template>
  <div class="page">
    <div class="page-header">
      <h1>移动端日志</h1>
    </div>

    <el-alert
      v-if="!canView"
      type="warning"
      title="当前页面仅管理员/项目经理可访问"
      :closable="false"
      show-icon
      class="mb16"
    />

    <el-card class="mb16">
      <template #header>
        <div class="card-header">
          <span>筛选</span>
          <div class="header-actions">
            <el-button @click="refresh" :loading="loading">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" class="filter-form">
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            @change="handleSearch"
          />
        </el-form-item>

        <el-form-item label="用户ID">
          <el-input
            v-model="filters.user_id"
            clearable
            placeholder="例如 1"
            style="width: 140px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
        </el-form-item>

        <el-form-item label="页面">
          <el-input
            v-model="filters.route"
            clearable
            placeholder="pages/home/home"
            style="width: 220px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
        </el-form-item>

        <el-form-item label="关键字">
          <el-input
            v-model="filters.keyword"
            clearable
            placeholder="内容/位置/页面"
            style="width: 320px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #append>
              <el-button @click="handleSearch">
                <el-icon><Search /></el-icon>
              </el-button>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button :disabled="loading" @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="说明：该页面展示移动端（UniApp）上报的 console 日志（uni.__log__），用于历史查询与排障。"
      />
    </el-card>

    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>日志列表</span>
          <span class="hint">共 {{ total }} 条</span>
        </div>
      </template>

      <el-table :data="items" size="small" stripe border style="width: 100%">
        <el-table-column label="时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.occurred_at || row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="120" show-overflow-tooltip />
        <el-table-column prop="route" label="页面" width="180" show-overflow-tooltip />
        <el-table-column label="内容" min-width="420" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="msg">
              <div class="msg-main">{{ row.message }}</div>
              <div v-if="row.at" class="msg-at">{{ row.at }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination" v-if="total > pageSize">
        <el-pagination
          background
          layout="prev, pager, next, jumper"
          :page-size="pageSize"
          :current-page="page"
          :total="total"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-drawer v-model="detailVisible" title="日志详情" size="55%">
      <div v-if="detail" class="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="时间">{{ formatDateTime(detail.occurred_at || detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="用户">{{ detail.username || '-' }}</el-descriptions-item>
          <el-descriptions-item label="设备ID">{{ detail.device_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="App版本" :span="2">
            {{ (detail.app_version_name || '-') + ' / ' + (detail.app_version_code ?? '-') }}
          </el-descriptions-item>
          <el-descriptions-item label="平台">{{ detail.platform || '-' }}</el-descriptions-item>
          <el-descriptions-item label="网络">{{ detail.network_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="页面" :span="2">{{ detail.route || '-' }}</el-descriptions-item>
          <el-descriptions-item label="位置" :span="2">{{ detail.at || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.level === 'ERROR'" label="级别">{{ detail.level }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.level === 'ERROR'" label="提示">
            ERROR 级别建议优先查看 Context
          </el-descriptions-item>
          <el-descriptions-item label="内容" :span="2">{{ detail.message || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-collapse class="mt12">
          <el-collapse-item title="Context" name="ctx">
            <pre class="json-view">{{ prettyJson(detail.context) }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { mobileClientLogsApi } from '@/api/mobileClientLogs'

const userStore = useUserStore()
const canView = computed(() => userStore.isAdmin)

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)

const timeRange = ref(null)
const filters = ref({
  keyword: '',
  user_id: '',
  route: '',
})

const detailVisible = ref(false)
const detail = ref(null)

const formatDateTime = (v) => {
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleString()
}

const prettyJson = (obj) => {
  try {
    return JSON.stringify(obj ?? null, null, 2)
  } catch (e) {
    return String(obj ?? '')
  }
}

const buildParams = () => {
  const params = {
    page: page.value,
    page_size: pageSize.value,
    tag: 'console',
  }

  const [from, to] = Array.isArray(timeRange.value) ? timeRange.value : []
  if (from) params.date_from = from
  if (to) params.date_to = to

  if (filters.value.keyword) params.keyword = filters.value.keyword
  if (filters.value.route) params.route = filters.value.route

  const userId = String(filters.value.user_id || '').trim()
  if (userId) params.user_id = Number(userId)

  return params
}

const loadPage = async () => {
  if (!canView.value) return
  try {
    loading.value = true
    const res = await mobileClientLogsApi.page(buildParams())
    items.value = res?.items || []
    total.value = res?.total || 0
  } catch (e) {
    console.error(e)
    const detailMsg = e?.response?.data?.detail
    ElMessage.error(detailMsg || '加载移动端日志失败')
  } finally {
    loading.value = false
  }
}

const refresh = () => {
  page.value = 1
  loadPage()
}

const handleSearch = () => {
  page.value = 1
  loadPage()
}

const resetFilters = () => {
  timeRange.value = null
  filters.value = {
    keyword: '',
    user_id: '',
    route: '',
  }
  page.value = 1
  loadPage()
}

const handlePageChange = (p) => {
  page.value = p
  loadPage()
}

const openDetail = async (id) => {
  try {
    const res = await mobileClientLogsApi.detail(id)
    detail.value = res
    detailVisible.value = true
  } catch (e) {
    console.error(e)
    const detailMsg = e?.response?.data?.detail
    ElMessage.error(detailMsg || '加载日志详情失败')
  }
}

onMounted(() => {
  loadPage()
})
</script>

<style scoped>
.msg-main {
  overflow: hidden;
  text-overflow: ellipsis;
}
.msg-at {
  color: #6b7280;
  font-size: 12px;
  margin-top: 2px;
}
.json-view {
  white-space: pre-wrap;
  word-break: break-word;
  background: #0b1020;
  color: #e5e7eb;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
}
</style>
