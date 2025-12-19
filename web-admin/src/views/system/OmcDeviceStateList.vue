<template>
  <div class="page">
    <div class="page-header">
      <h1>OMC 设备状态</h1>
      <div class="filters">
        <el-input
          v-model="searchSn"
          placeholder="按设备SN搜索"
          clearable
          style="width: 260px"
          @keyup.enter="handleSearch"
        />
        <el-button type="primary" :icon="Search" @click="handleSearch">
          查询
        </el-button>
        <el-button @click="handleReset">
          重置
        </el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table
        v-loading="loading"
        :data="items"
        border
        style="width: 100%"
      >
        <el-table-column prop="sn" label="设备SN" min-width="200">
          <template #default="{ row }">
            <el-text
              tag="b"
              style="font-family: 'Courier New', monospace; font-size: 14px"
            >
              {{ row.sn }}
            </el-text>
          </template>
        </el-table-column>

        <el-table-column label="状态" min-width="220">
          <template #default="{ row }">
            <div class="status-cell">
              <div class="status-row">
                <el-tag :type="statusTagType(row.omc_online_raw)" size="small">
                  {{ onlineText(row.omc_online_raw) }}
                </el-tag>
                <el-tag
                  :type="statusTagType(row.omc_active_raw)"
                  size="small"
                >
                  {{ activeText(row.omc_active_raw) }}
                </el-tag>
              </div>
              <div class="status-row">
                <el-tag
                  :type="row.ever_online ? 'success' : 'info'"
                  size="small"
                >
                  曾上线: {{ row.ever_online ? '是' : '否' }}
                </el-tag>
                <el-tag
                  :type="row.ever_activated ? 'success' : 'info'"
                  size="small"
                >
                  曾激活: {{ row.ever_activated ? '是' : '否' }}
                </el-tag>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="last_seen_at" label="最近观测时间" min-width="180">
          <template #default="{ row }">
            {{ formatTime(row.last_seen_at) || '-' }}
          </template>
        </el-table-column>

        <el-table-column label="当前绑定站点" min-width="260">
          <template #default="{ row }">
            <div v-if="row.current_site_id">
              <div>
                {{ row.current_site_name || '-' }}
              </div>
              <div class="site-code">
                ID: {{ row.current_site_id }} / Code: {{ row.current_site_code || '-' }}
              </div>
            </div>
            <span v-else>未绑定</span>
          </template>
        </el-table-column>

        <el-table-column prop="last_source" label="最近来源" min-width="120">
          <template #default="{ row }">
            <el-tag size="small">
              {{ sourceText(row.last_source) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              text
              :loading="isRefreshing(row.sn)"
              :disabled="getCooldown(row.sn) > 0"
              @click="refreshSn(row)"
            >
              <span v-if="getCooldown(row.sn) > 0">
                实时检测 ({{ getCooldown(row.sn) }}s)
              </span>
              <span v-else>
                实时检测
              </span>
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next, jumper"
          background
          @current-change="loadData"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import { trackOperation } from '@/utils/operationTrack'

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchSn = ref('')
const refreshingSn = ref('')
const refreshCooldowns = ref({}) // { sn: remainingSeconds }
let cooldownTimer = null

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/api/omc/states', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        sn: searchSn.value || undefined
      }
    })
    items.value = res.items || []
    total.value = res.total || 0
  } catch (error) {
    console.error('加载 OMC 设备状态失败:', error)
    ElMessage.error('加载 OMC 设备状态失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  page.value = 1
  trackOperation({
    module: 'OMC配置',
    action: '查询',
    object_type: 'OMC设备状态',
    data: {
      sn: searchSn.value || undefined,
    },
  })
  loadData()
}

const handleReset = () => {
  searchSn.value = ''
  page.value = 1
  trackOperation({
    module: 'OMC配置',
    action: '重置筛选',
    object_type: 'OMC设备状态',
  })
  loadData()
}

const handleSizeChange = () => {
  page.value = 1
  loadData()
}

const refreshSn = async (row) => {
  const sn = (row && row.sn) || ''
  if (!sn) return
  const remaining = refreshCooldowns.value[sn] || 0
  if (remaining > 0) {
    ElMessage.warning(`请等待 ${remaining}s 后再检测该设备`)
    return
  }
  refreshingSn.value = sn
  try {
    trackOperation({
      module: 'OMC配置',
      action: '实时检测',
      object_type: 'OMC设备',
      object_id: sn,
    })
    await request.get(`/api/omc/devices/${sn}/status`)
    ElMessage.success('已触发实时检测，状态已更新')
    // 启动该 SN 的10秒冷却
    startCooldown(sn)
    await loadData()
  } catch (error) {
    console.error('实时检测 OMC 状态失败:', error)
    ElMessage.error('实时检测 OMC 状态失败')
  } finally {
    refreshingSn.value = ''
  }
}

const isRefreshing = (sn) => refreshingSn.value === sn

const startCooldown = (sn) => {
  refreshCooldowns.value = {
    ...refreshCooldowns.value,
    [sn]: 10
  }
  if (cooldownTimer) return
  cooldownTimer = setInterval(() => {
    const next = {}
    let hasAny = false
    Object.entries(refreshCooldowns.value).forEach(([key, val]) => {
      const n = (val || 0) - 1
      if (n > 0) {
        next[key] = n
        hasAny = true
      }
    })
    refreshCooldowns.value = next
    if (!hasAny) {
      clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

const getCooldown = (sn) => refreshCooldowns.value[sn] || 0

const statusTagType = (val) => {
  if (val === true) return 'success'
  if (val === false) return 'danger'
  return 'info'
}

const onlineText = (val) => {
  if (val === true) return '在线'
  if (val === false) return '离线'
  return '未知'
}

const activeText = (val) => {
  if (val === true) return '已激活'
  if (val === false) return '未激活'
  return '未知'
}

const sourceText = (val) => {
  if (!val) return '未知'
  if (val === 'api_poll') return 'API查询结果'
  if (val === 'monitor') return '后台监控'
  if (val === 'omc_push') return 'OMC上报告'
  if (val === 'inventory_ftp') return '库存同步'
  return val
}

const formatTime = (isoString) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  if (Number.isNaN(date.getTime())) return isoString
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

onMounted(() => {
  loadData()
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

.filters {
  display: flex;
  gap: 8px;
  align-items: center;
}

.table-footer {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.site-code {
  font-size: 12px;
  color: #909399;
}

.status-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
}

.status-row {
  display: flex;
  align-items: center;
}

.status-label {
  color: #909399;
  min-width: 48px;
}
</style>
