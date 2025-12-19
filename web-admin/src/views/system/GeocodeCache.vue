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
        <el-tag class="mr8" type="warning">Google 调用 {{ metrics.google_call ?? 0 }}</el-tag>
        <el-tag class="mr8" type="warning">Google 直连 {{ metrics.google_direct_call ?? 0 }}</el-tag>
        <el-tag class="mr8" type="warning">Google Relay {{ metrics.google_relay_call ?? 0 }}</el-tag>
        <el-tag class="mr8" type="primary">写入 SQLite {{ metrics.l2_write ?? 0 }}</el-tag>
        <el-tag class="mr8" type="warning">负缓存命中 {{ metrics.negative_hit ?? 0 }}</el-tag>
        <el-tag class="mr8" type="danger">熔断拦截 {{ metrics.breaker_hit ?? 0 }}</el-tag>
        <el-tag class="mr8" type="danger">熔断触发 {{ metrics.breaker_set ?? 0 }}</el-tag>
      </div>
    </el-card>

    <el-card class="mb16" v-loading="testLoading">
      <template #header>
        <div class="card-header">
          <span>测试 / 预热</span>
        </div>
      </template>

      <el-alert
        type="info"
        title="输入一组经纬度，系统会调用与 App（在线逆地理）一致的后端接口 /api/geo/baidu-reverse，用于模拟不同位置并提前写入缓存。后端会自动选择 Provider：境内优先 Baidu，境外走 Google（language=en）；若 Baidu 返回 240（APP 服务被禁用），也会自动回退到 Google。"
        :closable="false"
        show-icon
        class="mb12"
      />

      <el-form :inline="true" class="test-form">
        <el-form-item label="纬度">
          <el-input
            v-model="testLat"
            placeholder="例如：22.542359"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="经度">
          <el-input
            v-model="testLng"
            placeholder="例如：113.947312"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="testLoading"
            :disabled="!canView"
            @click="runTest"
          >
            测试并预热缓存
          </el-button>
          <el-button :disabled="testLoading" @click="fillExample">填入示例</el-button>
          <el-button :disabled="testLoading" @click="clearTest">清空</el-button>
        </el-form-item>
      </el-form>

      <div v-if="testCoordKey" class="test-hint">
        标准化 Key（后端按约 30m 网格归一化）：<code>{{ testCoordKey }}</code>
      </div>

      <div v-if="testMeta || testResult || testError" class="test-result">
        <div class="test-row" v-if="testSourceText">
          <div class="test-label">本次来源</div>
          <div class="test-value">
            <el-tag :type="testSourceTagType">{{ testSourceText }}</el-tag>
          </div>
        </div>

        <div class="test-row" v-if="metricDeltas.length">
          <div class="test-label">指标变化</div>
          <div class="test-value">
            <el-tag
              v-for="d in metricDeltas"
              :key="d.key"
              class="mr8"
              :type="d.type"
            >
              {{ d.label }} +{{ d.delta }}
            </el-tag>
          </div>
        </div>

        <div class="test-row" v-if="testResult">
          <div class="test-label">地址</div>
          <div class="test-value">{{ testResult.address || '（空）' }}</div>
        </div>
        <div class="test-row" v-if="testResult">
          <div class="test-label">语义描述</div>
          <div class="test-value">{{ testResult.sematic_description || '（空）' }}</div>
        </div>
        <div class="test-row" v-if="testError">
          <div class="test-label">错误</div>
          <div class="test-value error">{{ testError }}</div>
        </div>

        <el-collapse v-if="testResult" class="mt8">
          <el-collapse-item title="查看原始返回（JSON）" name="raw">
            <pre class="json-view">{{ prettyJson(testResult) }}</pre>
          </el-collapse-item>
        </el-collapse>
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
        <el-table-column prop="provider" label="来源" width="120">
          <template #default="{ row }">
            <el-tag v-if="String(row.provider || '').startsWith('baidu')" type="success">Baidu</el-tag>
            <el-tag v-else-if="String(row.provider || '').startsWith('google')" type="warning">Google</el-tag>
            <span v-else>{{ row.provider || '-' }}</span>
          </template>
        </el-table-column>
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
import { trackOperation } from '@/utils/operationTrack'

const userStore = useUserStore()
const canView = computed(() => userStore.isAdmin)

const loading = ref(false)
const statsLoading = ref(false)
const listLoading = ref(false)
const testLoading = ref(false)

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

const testLat = ref('')
const testLng = ref('')
const testResult = ref(null)
const testError = ref('')
const testMeta = ref(null)

const parseCoord = (val) => {
  const s = String(val ?? '').trim()
  if (!s) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

const buildCoordKey = (lat, lng, gridStepUnits = 3) => {
  const scale = 10000 // 1e-4 度
  const step = Math.max(1, Number(gridStepUnits) || 1)
  const normalize = (n) => {
    const units = Math.round(Number(n) * scale / step) * step
    const normalized = Math.abs(units) < 1 ? 0 : units / scale
    const fixed = normalized.toFixed(4)
    return fixed === '-0.0000' ? '0.0000' : fixed
  }
  return `wgs84ll:${normalize(lat)},${normalize(lng)}`
}

const testCoordKey = computed(() => {
  const lat = parseCoord(testLat.value)
  const lng = parseCoord(testLng.value)
  if (lat === null || lng === null) return ''
  return buildCoordKey(lat, lng, 3)
})

const calcMetricsDiff = (after, before) => {
  const keys = [
    'requests',
    'hit_l1',
    'hit_l2',
    'baidu_call',
    'google_call',
    'google_direct_call',
    'google_relay_call',
    'l2_write',
    'negative_hit',
    'breaker_hit',
    'breaker_set',
  ]
  const diff = {}
  keys.forEach((k) => {
    diff[k] = (Number(after?.[k] || 0) - Number(before?.[k] || 0))
  })
  return diff
}

const inferSourceFromDiff = (diff, hasError) => {
  if ((diff?.hit_l1 || 0) > 0) return 'l1'
  if ((diff?.hit_l2 || 0) > 0) return 'l2'
  if ((diff?.breaker_hit || 0) > 0) return 'breaker'
  if ((diff?.negative_hit || 0) > 0) return 'negative'
  if ((diff?.baidu_call || 0) > 0 && ((diff?.google_relay_call || 0) > 0 || (diff?.google_direct_call || 0) > 0 || (diff?.google_call || 0) > 0)) {
    return 'baidu_fallback_google'
  }
  if ((diff?.baidu_call || 0) > 0) return hasError ? 'baidu_error' : 'baidu'
  if ((diff?.google_relay_call || 0) > 0) return hasError ? 'google_relay_error' : 'google_relay'
  if ((diff?.google_direct_call || 0) > 0) return hasError ? 'google_error' : 'google'
  if ((diff?.google_call || 0) > 0) return hasError ? 'google_error' : 'google'
  if (hasError) return 'error'
  return 'unknown'
}

const testSourceText = computed(() => {
  const source = testMeta.value?.source
  if (!source) return ''
  if (source === 'l1') return 'L1 内存缓存命中'
  if (source === 'l2') return 'L2 SQLite 缓存命中'
  if (source === 'baidu') return '调用 Baidu API（并写入缓存）'
  if (source === 'baidu_error') return '调用 Baidu API 失败（未写入缓存）'
  if (source === 'baidu_fallback_google') return 'Baidu 调用失败/不支持，已回退到 Google'
  if (source === 'google_relay') return '通过境外 Relay 调用 Google（并写入缓存）'
  if (source === 'google_relay_error') return '通过境外 Relay 调用 Google 失败（未写入缓存）'
  if (source === 'google') return '调用 Google API（并写入缓存）'
  if (source === 'google_error') return '调用 Google API 失败（未写入缓存）'
  if (source === 'breaker') return '熔断拦截（未调用 Baidu）'
  if (source === 'negative') return '负缓存命中（短期失败拦截）'
  if (source === 'error') return '请求失败（未识别来源）'
  return '未知来源'
})

const testSourceTagType = computed(() => {
  const source = testMeta.value?.source
  if (source === 'l1' || source === 'l2') return 'success'
  if (source === 'baidu') return 'warning'
  if (source === 'baidu_error') return 'danger'
  if (source === 'baidu_fallback_google') return 'warning'
  if (source === 'google_relay') return 'warning'
  if (source === 'google_relay_error') return 'danger'
  if (source === 'google') return 'warning'
  if (source === 'google_error') return 'danger'
  if (source === 'breaker') return 'danger'
  if (source === 'negative') return 'warning'
  if (source === 'error') return 'danger'
  return 'info'
})

const metricDeltas = computed(() => {
  const diff = testMeta.value?.diff || {}
  const mapping = [
    { key: 'hit_l1', label: 'L1', type: 'success' },
    { key: 'hit_l2', label: 'L2', type: 'success' },
    { key: 'baidu_call', label: '百度调用', type: 'warning' },
    { key: 'google_direct_call', label: 'Google 直连', type: 'warning' },
    { key: 'google_relay_call', label: 'Google Relay', type: 'warning' },
    { key: 'google_call', label: 'Google(总)', type: 'warning' },
    { key: 'l2_write', label: '写入 SQLite', type: 'primary' },
    { key: 'negative_hit', label: '负缓存', type: 'warning' },
    { key: 'breaker_hit', label: '熔断拦截', type: 'danger' },
  ]
  return mapping
    .map((m) => ({ ...m, delta: Number(diff[m.key] || 0) }))
    .filter((x) => x.delta > 0)
})

const prettyJson = (obj) => {
  try {
    return JSON.stringify(obj, null, 2)
  } catch (e) {
    return String(obj)
  }
}

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

const runTest = async () => {
  if (!canView.value) return

  testError.value = ''
  testResult.value = null
  testMeta.value = null

  const lat = parseCoord(testLat.value)
  const lng = parseCoord(testLng.value)
  if (lat === null || lng === null) {
    ElMessage.error('请输入合法的经纬度（数字）')
    return
  }
  if (lat < -90 || lat > 90) {
    ElMessage.error('纬度范围应为 -90 ~ 90')
    return
  }
  if (lng < -180 || lng > 180) {
    ElMessage.error('经度范围应为 -180 ~ 180')
    return
  }

  testLoading.value = true
  let beforeMetrics = {}
  let hasError = false

  try {
    const before = await geocodeCacheApi.getStats()
    beforeMetrics = before?.metrics || {}

    const payload = await geocodeCacheApi.reverseGeocode({ lat, lng })
    testResult.value = payload
    ElMessage.success('测试完成（已刷新缓存列表）')
  } catch (e) {
    console.error(e)
    hasError = true
    const detail = e?.response?.data?.detail
    testError.value = detail || e.message || '请求失败'
    ElMessage.error(testError.value)
  } finally {
    try {
      const after = await geocodeCacheApi.getStats()
      stats.value = after || stats.value
      const afterMetrics = after?.metrics || {}
      const diff = calcMetricsDiff(afterMetrics, beforeMetrics)
      testMeta.value = {
        before: beforeMetrics,
        after: afterMetrics,
        diff,
        source: inferSourceFromDiff(diff, hasError),
      }
    } catch (e) {
      console.warn('刷新统计失败:', e)
    }

    try {
      // 列表排序按“最近命中/更新时间”，执行测试后刷新可快速看到最新条目
      page.value = 1
      await loadEntries()
    } catch (e) {
      console.warn('刷新列表失败:', e)
    }

    testLoading.value = false
  }
}

const fillExample = () => {
  // 使用中国境内坐标作为默认示例（百度逆地理对部分境外坐标可能返回 240）
  testLat.value = '22.542359'
  testLng.value = '113.947312'
}

const clearTest = () => {
  testLat.value = ''
  testLng.value = ''
  testResult.value = null
  testError.value = ''
  testMeta.value = null
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
  trackOperation({
    module: '系统配置',
    action: '查询',
    object_type: '逆地理缓存',
    data: {
      q: q.value || undefined,
      include_expired: includeExpired.value ? true : undefined,
    },
  })
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
.mb12 {
  margin-bottom: 12px;
}
.mt8 {
  margin-top: 8px;
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

.test-form {
  margin-bottom: 8px;
}

.test-hint {
  color: #909399;
  font-size: 12px;
  margin-bottom: 8px;
}

.test-result {
  border-top: 1px solid #ebeef5;
  padding-top: 12px;
}

.test-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 10px;
}

.test-label {
  width: 110px;
  color: #909399;
  font-size: 12px;
  line-height: 20px;
  flex: 0 0 auto;
}

.test-value {
  flex: 1;
  line-height: 20px;
  word-break: break-word;
}

.test-value.error {
  color: #f56c6c;
}

.json-view {
  font-size: 12px;
  line-height: 18px;
  background: #0b1020;
  color: #d1d5db;
  padding: 12px;
  border-radius: 6px;
  overflow: auto;
}
</style>
