<template>
  <div class="page">
    <div class="page-header">
      <h1>逆地理缓存</h1>
      <div class="header-actions">
        <el-button @click="refresh" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="!canView"
      type="warning"
      title="当前用户仅可查看，访问需要管理员或项目经理权限"
      :closable="false"
      show-icon
      class="mb16"
    />

    <el-card class="mb16" v-loading="statsLoading">
      <template #header>
        <div class="card-header">
          <span>概览</span>
        </div>
      </template>

      <el-row :gutter="12">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">有效缓存</div>
            <div class="stat-value">{{ stats.active_entries ?? 0 }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">总条目</div>
            <div class="stat-value">{{ stats.total_entries ?? 0 }}</div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="stat-item">
            <div class="stat-label">熔断状态</div>
            <div class="stat-value">
              <el-tag v-if="stats.circuit_breaker?.disabled" type="danger">
                已熔断（至 {{ formatDateTime(stats.circuit_breaker.disabled_until) }}）
              </el-tag>
              <el-tag v-else type="success">正常</el-tag>
              <span v-if="stats.circuit_breaker?.disabled && stats.circuit_breaker?.reason" class="breaker-reason">
                原因：{{ stats.circuit_breaker.reason }}
              </span>
            </div>
          </div>
        </el-col>
      </el-row>

      <div class="metrics">
        <el-tag class="mr8" type="info">请求 {{ metrics.requests ?? 0 }}</el-tag>
        <el-tag class="mr8" type="success">L1 命中 {{ metrics.hit_l1 ?? 0 }}</el-tag>
        <el-tag class="mr8" type="success">L2 命中 {{ metrics.hit_l2 ?? 0 }}</el-tag>
        <el-tag class="mr8" type="warning">百度调用 {{ metrics.baidu_call ?? 0 }}</el-tag>
        <el-tag class="mr8" type="primary">写入 SQLite {{ metrics.l2_write ?? 0 }}</el-tag>
        <el-tag class="mr8" type="warning">负缓存命中 {{ metrics.negative_hit ?? 0 }}</el-tag>
        <el-tag class="mr8" type="danger">熔断拦截 {{ metrics.breaker_hit ?? 0 }}</el-tag>
        <el-tag class="mr8" type="danger">熔断触发 {{ metrics.breaker_set ?? 0 }}</el-tag>
      </div>
    </el-card>

    <el-card v-loading="listLoading">
      <template #header>
        <div class="card-header">
          <span>缓存条目</span>
          <div class="header-actions">
            <el-input
              v-model="q"
              clearable
              placeholder="搜索坐标/地址"
              style="width: 320px"
              @keyup.enter="handleSearch"
            >
              <template #append>
                <el-button @click="handleSearch">
                  <el-icon><Search /></el-icon>
                </el-button>
              </template>
            </el-input>
            <el-checkbox v-model="includeExpired" class="ml12" @change="handleSearch">包含过期</el-checkbox>
          </div>
        </div>
      </template>

      <el-table :data="items" size="small" stripe border style="width: 100%">
        <el-table-column prop="coord_key" label="坐标Key" min-width="220" show-overflow-tooltip />
        <el-table-column label="坐标" width="200">
          <template #default="{ row }">
            {{ formatCoords(row.latitude, row.longitude) }}
          </template>
        </el-table-column>
        <el-table-column prop="address" label="地址" min-width="260" show-overflow-tooltip />
        <el-table-column prop="sematic_description" label="语义描述" min-width="220" show-overflow-tooltip />
        <el-table-column prop="hit_count" label="命中次数" width="110" />
        <el-table-column label="最近命中" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.last_hit_at) || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="过期时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.expires_at) || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.updated_at) || '-' }}
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
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { geocodeCacheApi } from '@/api/system'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const canView = computed(() => userStore.isAdmin)

const loading = ref(false)
const statsLoading = ref(false)
const listLoading = ref(false)

const stats = ref({
  total_entries: 0,
  active_entries: 0,
  circuit_breaker: {
    disabled: false,
    disabled_until: null,
    reason: null,
  },
  metrics: {},
})

const metrics = computed(() => stats.value.metrics || {})

const q = ref('')
const includeExpired = ref(false)

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const formatDateTime = (val) => {
  if (!val) return ''
  const d = new Date(val)
  if (Number.isNaN(d.getTime())) return String(val)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const formatCoords = (lat, lng) => {
  const la = Number(lat)
  const lo = Number(lng)
  if (!Number.isFinite(la) || !Number.isFinite(lo)) return '-'
  return `${la.toFixed(4)}, ${lo.toFixed(4)}`
}

const loadStats = async () => {
  statsLoading.value = true
  try {
    const res = await geocodeCacheApi.getStats()
    stats.value = res || stats.value
  } catch (e) {
    console.error(e)
    ElMessage.error('加载缓存统计失败')
  } finally {
    statsLoading.value = false
  }
}

const loadEntries = async () => {
  listLoading.value = true
  try {
    const res = await geocodeCacheApi.getEntries({
      q: q.value || undefined,
      include_expired: includeExpired.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = Array.isArray(res.items) ? res.items : []
    total.value = res.total || 0
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '加载缓存列表失败')
  } finally {
    listLoading.value = false
  }
}

const refresh = async () => {
  if (!canView.value) return
  loading.value = true
  try {
    await Promise.all([loadStats(), loadEntries()])
  } finally {
    loading.value = false
  }
}

const handleSearch = async () => {
  page.value = 1
  await loadEntries()
}

const handlePageChange = async (p) => {
  page.value = p
  await loadEntries()
}

onMounted(async () => {
  await refresh()
})
</script>

<style scoped>
.page {
  padding: 24px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.mb16 {
  margin-bottom: 16px;
}
.ml12 {
  margin-left: 12px;
}
.mr8 {
  margin-right: 8px;
}
.stat-item {
  padding: 6px 0;
}
.stat-label {
  color: #909399;
  font-size: 12px;
  margin-bottom: 6px;
}
.stat-value {
  font-size: 16px;
  font-weight: 600;
}
.breaker-reason {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}
.metrics {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>

