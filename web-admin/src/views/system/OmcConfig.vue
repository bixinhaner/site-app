<template>
  <div class="page">
    <div class="page-header">
      <h1>OMC API 配置</h1>
      <div class="header-actions">
        <el-button @click="refreshPage" :loading="loading || runtimeLoading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button @click="testConnection" :loading="testing">
          <el-icon><Cpu /></el-icon>测试连接
        </el-button>
        <el-button type="primary" @click="save" :loading="saving">
          <el-icon><Document /></el-icon>保存
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="!canManageOmc"
      type="error"
      title="当前账号无 OMC 配置管理权限"
      :closable="false"
      show-icon
      class="mb16"
    />

    <el-card v-loading="loading">
      <el-form :model="form" label-width="140px" :disabled="!canManageOmc">
        <el-form-item label="OMC 基础地址">
          <el-input
            v-model="form.base_url"
            placeholder="例如：http://172.21.175.129:8081"
          />
          <div class="tip">
            后端会在此基础上拼接 <code>/northboundApi/v1/...</code> 路径。
          </div>
        </el-form-item>
        <el-form-item label="API 用户名">
          <el-input
            v-model="form.username"
            placeholder="用于调用 OMC API 的用户名"
          />
        </el-form-item>
        <el-form-item label="API 密码">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="用于调用 OMC API 的密码（留空则保持不变）"
            show-password
          />
        </el-form-item>
        <el-form-item label="超时时间(秒)">
          <el-input-number v-model="form.timeout_seconds" :min="3" :max="60" />
        </el-form-item>
        <el-form-item label="手工确认开关">
          <el-switch
            v-model="form.manual_confirm_enabled"
            active-text="开启"
            inactive-text="关闭"
          />
          <div class="tip">
            开启后，工单审核台将显示“手工确认已上线/已激活”按钮（适用于项目服务器无法与 OMC 通信的场景）。
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-loading="loading" class="mt16">
      <template #header>请求保护</template>
      <el-form :model="form" label-width="180px" :disabled="!canManageOmc">
        <el-form-item label="每分钟请求上限">
          <el-input-number
            v-model="form.rate_limit_per_minute"
            :min="1"
            :max="3000"
            :step="10"
          />
          <div class="tip">
            后台轮询、手动刷新、单 SN 查询和 cellName 同步都会共用这个出口额度。
          </div>
        </el-form-item>
        <el-form-item label="短时突发上限">
          <el-input-number
            v-model="form.rate_limit_burst"
            :min="1"
            :max="500"
            :step="1"
          />
          <div class="tip">
            允许短时间内连续放行的请求数；建议明显小于每分钟上限。
          </div>
        </el-form-item>
        <el-form-item label="Token缓存时间(秒)">
          <el-input-number
            v-model="form.token_ttl_seconds"
            :min="60"
            :max="86400"
            :step="60"
          />
          <div class="tip">
            缓存 OMC access token，避免每个 SN 查询都重复获取 token；遇到 401 会自动刷新一次。
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-loading="loading" class="mt16">
      <template #header>设备快照</template>
      <el-form :model="form" label-width="180px" :disabled="!canManageOmc">
        <el-form-item label="启用device/query快照">
          <el-switch
            v-model="form.inventory_snapshot_enabled"
            active-text="开启"
            inactive-text="关闭"
          />
          <div class="tip">
            开启后，后台轮询会先批量读取 OMC 设备表，再只对快照覆盖到的 SN 继续查实时状态，避免未知 SN 反复触发 OMC 权限错误。
          </div>
        </el-form-item>
        <el-form-item label="快照周期(秒)">
          <el-input-number
            v-model="form.inventory_snapshot_interval_seconds"
            :min="60"
            :max="86400"
            :step="60"
          />
          <div class="tip">
            默认 300 秒；周期未到时复用上一轮快照覆盖集合，不重复请求设备表。
          </div>
        </el-form-item>
        <el-form-item label="设备分组ID">
          <el-input
            v-model="form.inventory_device_group_ids_text"
            placeholder="例如：30，多个用逗号分隔"
          />
          <div class="tip">
            当前 Savanna 生产验证过的默认分组是 <code>30</code>（Default Device Group）。
          </div>
        </el-form-item>
        <el-form-item label="每页设备数">
          <el-input-number
            v-model="form.inventory_page_size"
            :min="1"
            :max="5000"
            :step="100"
          />
          <div class="tip">
            设备量低于该值时，通常每个分组只消耗一次 <code>/device/query</code> 请求。
          </div>
        </el-form-item>
        <el-form-item label="offlineDays补曾上线">
          <el-switch
            v-model="form.offline_days_marks_ever_online"
            active-text="开启"
            inactive-text="关闭"
          />
          <div class="tip">
            开启后，离线设备只要 <code>offlineDays</code> 有值，就视为 OMC 曾观察到上线；该接口不能证明曾激活。
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-loading="runtimeLoading" class="mt16 runtime-card">
      <template #header>
        <div class="card-header">
          <span>运行状态</span>
          <el-button size="small" @click="loadRuntime" :loading="runtimeLoading">
            <el-icon><Refresh /></el-icon>刷新状态
          </el-button>
        </div>
      </template>
      <div class="metric-grid">
        <div class="metric-item">
          <div class="metric-label">最近1分钟</div>
          <div class="metric-value">{{ runtime?.stats?.requests_last_1m ?? 0 }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">最近5分钟</div>
          <div class="metric-value">{{ runtime?.stats?.requests_last_5m ?? 0 }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">最近15分钟</div>
          <div class="metric-value">{{ runtime?.stats?.requests_last_15m ?? 0 }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">15分钟失败</div>
          <div class="metric-value danger">{{ runtime?.stats?.failed_last_15m ?? 0 }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">轮询队列</div>
          <div class="metric-value">{{ runtime?.stats?.monitor_queue_depth ?? 0 }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">等待请求</div>
          <div class="metric-value">{{ runtime?.limiter?.waiting_requests ?? 0 }}</div>
        </div>
      </div>

      <el-descriptions :column="3" border class="runtime-details">
        <el-descriptions-item label="当前上限">
          {{ runtime?.config?.rate_limit_per_minute ?? form.rate_limit_per_minute }}/min
        </el-descriptions-item>
        <el-descriptions-item label="突发桶">
          {{ runtime?.config?.rate_limit_burst ?? form.rate_limit_burst }}
        </el-descriptions-item>
        <el-descriptions-item label="Token缓存">
          {{ runtime?.config?.token_ttl_seconds ?? form.token_ttl_seconds }}s
        </el-descriptions-item>
        <el-descriptions-item label="快照周期">
          {{ form.inventory_snapshot_enabled ? `${form.inventory_snapshot_interval_seconds}s` : '关闭' }}
        </el-descriptions-item>
        <el-descriptions-item label="快照分组">
          {{ form.inventory_device_group_ids_text || '30' }}
        </el-descriptions-item>
        <el-descriptions-item label="Token命中">
          {{ runtime?.token_cache?.hits ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="Token未命中">
          {{ runtime?.token_cache?.misses ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="累计等待">
          {{ runtime?.limiter?.total_wait_seconds ?? 0 }}s
        </el-descriptions-item>
      </el-descriptions>

      <el-table
        :data="runtime?.stats?.recent_requests || []"
        size="small"
        class="recent-table"
        empty-text="暂无 OMC 出口请求"
      >
        <el-table-column prop="time" label="时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.time) }}</template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="110" />
        <el-table-column prop="method" label="方法" width="80" />
        <el-table-column prop="endpoint" label="接口" min-width="240" show-overflow-tooltip />
        <el-table-column prop="status_code" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small">
              {{ row.status_code || 'ERR' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="wait_seconds" label="等待(s)" width="90" />
        <el-table-column prop="duration_seconds" label="耗时(s)" width="90" />
      </el-table>
    </el-card>

    <el-card v-loading="loading" class="mt16">
      <template #header>SSV 创建规则</template>
      <el-form :model="form" label-width="180px" :disabled="!canManageOmc">
        <el-form-item label="站点设备激活即可创建SSV">
          <el-switch
            v-model="form.ssv_create_by_ever_activated_only"
            active-text="开启"
            inactive-text="关闭"
          />
          <div class="tip">
            关闭后：沿用旧规则，仅当站点状态为 <code>operational</code> 时允许创建 SSV。
          </div>
          <div class="tip">
            开启后：不再判断站点状态，只要站点设备全部 <code>ever_activated</code> 即允许创建 SSV；包括 <code>maintenance</code> 等非运营中状态。
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-loading="loading" class="mt16">
      <template #header>站点进度统计口径</template>
      <el-form :model="form" label-width="180px" :disabled="!canManageOmc">
        <el-form-item label="全局统计口径">
          <el-radio-group v-model="form.site_progress_metric_mode">
            <el-radio label="workflow">流程口径</el-radio>
            <el-radio label="device_fact">设备事实口径</el-radio>
          </el-radio-group>
          <div class="tip">
            流程口径：上线=开站工单 <code>activated_at</code>，激活=开站工单 <code>completed_at</code>。
          </div>
          <div class="tip">
            设备事实口径：上线/激活不依赖工单状态，按开站阶段有效设备集合全部达到 <code>ever_online / ever_activated</code> 的时间计算。
          </div>
          <div class="tip">
            此开关会统一影响仪表盘站点概况、站点事件趋势，以及站点详情关键节点时间中的“上线 / 激活”。
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Document, Cpu } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const runtimeLoading = ref(false)
const runtime = ref(null)
const form = ref({
  base_url: '',
  username: '',
  password: '',
  timeout_seconds: 10,
  rate_limit_per_minute: 120,
  rate_limit_burst: 10,
  token_ttl_seconds: 600,
  inventory_snapshot_enabled: true,
  inventory_snapshot_interval_seconds: 300,
  inventory_device_group_ids_text: '30',
  inventory_page_size: 1000,
  offline_days_marks_ever_online: true,
  manual_confirm_enabled: false,
  ssv_create_by_ever_activated_only: false,
  site_progress_metric_mode: 'workflow',
})

const canManageOmc = computed(() => userStore.hasPermission('system:mobile-settings:write'))

const formatGroupIds = (value) => {
  if (Array.isArray(value) && value.length) {
    return value.join(',')
  }
  if (typeof value === 'string' && value.trim()) {
    return value
  }
  return '30'
}

const parseGroupIds = (value) => {
  const text = String(value || '').trim()
  if (!text) return [30]
  const seen = new Set()
  return text
    .split(/[,，]/)
    .map(item => Number.parseInt(item.trim(), 10))
    .filter((id) => {
      if (!Number.isInteger(id) || id <= 0 || seen.has(id)) return false
      seen.add(id)
      return true
    })
}

const loadConfig = async () => {
  try {
    loading.value = true
    const res = await request.get('/api/omc/config')
    form.value.base_url = res.base_url || ''
    form.value.username = res.username || ''
    form.value.password = ''
    form.value.timeout_seconds = res.timeout_seconds || 10
    form.value.rate_limit_per_minute = res.rate_limit_per_minute || 120
    form.value.rate_limit_burst = res.rate_limit_burst || 10
    form.value.token_ttl_seconds = res.token_ttl_seconds || 600
    form.value.inventory_snapshot_enabled = res.inventory_snapshot_enabled !== false
    form.value.inventory_snapshot_interval_seconds = res.inventory_snapshot_interval_seconds || 300
    form.value.inventory_device_group_ids_text = formatGroupIds(res.inventory_device_group_ids)
    form.value.inventory_page_size = res.inventory_page_size || 1000
    form.value.offline_days_marks_ever_online = res.offline_days_marks_ever_online !== false
    form.value.manual_confirm_enabled = !!res.manual_confirm_enabled
    form.value.ssv_create_by_ever_activated_only = !!res.ssv_create_by_ever_activated_only
    form.value.site_progress_metric_mode = res.site_progress_metric_mode || 'workflow'
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '加载 OMC 配置失败')
  } finally {
    loading.value = false
  }
}

const loadRuntime = async () => {
  if (!canManageOmc.value) return
  try {
    runtimeLoading.value = true
    runtime.value = await request.get('/api/omc/runtime')
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '加载 OMC 运行状态失败')
  } finally {
    runtimeLoading.value = false
  }
}

const refreshPage = async () => {
  await loadConfig()
  await loadRuntime()
}

const save = async () => {
  if (!canManageOmc.value) {
    ElMessage.error('当前账号无权限保存配置')
    return
  }
  try {
    saving.value = true
    const inventoryGroupIds = parseGroupIds(form.value.inventory_device_group_ids_text)
    if (!inventoryGroupIds.length) {
      ElMessage.error('设备分组ID不能为空')
      return
    }
    const payload = {
      base_url: form.value.base_url,
      username: form.value.username,
      password: form.value.password || undefined,
      timeout_seconds: form.value.timeout_seconds || 10,
      rate_limit_per_minute: form.value.rate_limit_per_minute || 120,
      rate_limit_burst: form.value.rate_limit_burst || 10,
      token_ttl_seconds: form.value.token_ttl_seconds || 600,
      inventory_snapshot_enabled: !!form.value.inventory_snapshot_enabled,
      inventory_snapshot_interval_seconds: form.value.inventory_snapshot_interval_seconds || 300,
      inventory_device_group_ids: inventoryGroupIds,
      inventory_page_size: form.value.inventory_page_size || 1000,
      offline_days_marks_ever_online: !!form.value.offline_days_marks_ever_online,
      manual_confirm_enabled: !!form.value.manual_confirm_enabled,
      ssv_create_by_ever_activated_only: !!form.value.ssv_create_by_ever_activated_only,
      site_progress_metric_mode: form.value.site_progress_metric_mode || 'workflow',
    }
    await request.put('/api/omc/config', payload)
    await refreshPage()
    ElMessage.success('保存成功')
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    let msg = '保存失败'
    if (typeof detail === 'string') {
      msg = detail
    } else if (Array.isArray(detail)) {
      msg = detail.map(d => d.msg || JSON.stringify(d)).join('；')
    }
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

const testConnection = async () => {
  if (!canManageOmc.value) {
    ElMessage.error('当前账号无权限测试连接')
    return
  }
  try {
    testing.value = true
    const res = await request.post('/api/omc/test')
    if (res?.success) {
      ElMessage.success(res.message || 'OMC API 测试成功')
    } else {
      ElMessage.error(res?.message || 'OMC API 测试失败')
    }
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    let msg = 'OMC API 测试失败'
    if (typeof detail === 'string') {
      msg = detail
    } else if (Array.isArray(detail)) {
      msg = detail.map(d => d.msg || JSON.stringify(d)).join('；')
    }
    ElMessage.error(msg)
  } finally {
    testing.value = false
  }
}

const formatTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

onMounted(() => {
  if (canManageOmc.value) {
    refreshPage()
  }
})
</script>

<style scoped>
.page { padding: 24px; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.mb16 { margin-bottom: 16px; }
.mt16 { margin-top: 16px; }
.tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}
.metric-item {
  min-width: 0;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #fafafa;
}
.metric-label {
  color: #606266;
  font-size: 12px;
}
.metric-value {
  margin-top: 6px;
  color: #303133;
  font-size: 22px;
  line-height: 1.2;
  font-weight: 600;
}
.metric-value.danger {
  color: #f56c6c;
}
.runtime-details {
  margin-top: 16px;
}
.recent-table {
  margin-top: 16px;
}
@media (max-width: 1200px) {
  .metric-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .page-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
