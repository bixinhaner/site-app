<template>
  <div class="ai-management">
    <div class="page-header">
      <div class="header-left">
        <h1>AI管理</h1>
      </div>
      <div class="header-right">
        <div v-if="activeTab !== 'config'" class="filter-group">
          <el-select v-model="selectedDays" style="width: 150px" @change="handleRefresh">
            <el-option label="最近7天" :value="7" />
            <el-option label="最近30天" :value="30" />
            <el-option label="最近90天" :value="90" />
            <el-option label="最近365天" :value="365" />
          </el-select>
          <el-button :icon="Refresh" @click="handleRefresh" :loading="loading">刷新</el-button>
        </div>
      </div>
    </div>

    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane v-if="canEditConfig" label="配置" name="config">
        <div class="config-section">
          <el-alert
            type="info"
            :closable="false"
            show-icon
            title="配置变更会实时生效（无需重启）。API Key 仅支持写入，读取时不会回显明文。"
          />

          <div class="config-grid">
            <el-card shadow="never">
              <template #header>
                <div class="card-header">
                  <span>Text 模型</span>
                </div>
              </template>

              <el-form :model="configForm.text" label-width="140px">
                <el-form-item label="Base URL">
                  <el-input v-model="configForm.text.base_url" placeholder="例如：https://api.deepseek.com 或 Azure /openai/v1" />
                </el-form-item>
                <el-form-item label="Model">
                  <el-input v-model="configForm.text.model" placeholder="例如：deepseek-chat / gpt-5-nano(部署名)" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input
                    v-model="textApiKeyInput"
                    type="password"
                    show-password
                    :placeholder="configForm.text.api_key_masked ? `已配置：${configForm.text.api_key_masked}` : '未配置'"
                  />
                  <div class="form-help">
                    <el-button link type="danger" @click="clearTextKey">清空 Key</el-button>
                  </div>
                </el-form-item>
                <el-form-item label="Chat Path">
                  <el-input v-model="configForm.text.chat_completions_path" placeholder="/v1/chat/completions" />
                </el-form-item>
                <el-form-item label="Timeout(s)">
                  <el-input-number v-model="configForm.text.timeout_seconds" :min="1" :max="600" />
                </el-form-item>
                <el-form-item label="Temperature">
                  <el-input-number v-model="configForm.text.temperature" :min="0" :max="2" :step="0.1" />
                </el-form-item>
                <el-form-item label="Max Tokens">
                  <el-input-number v-model="configForm.text.max_tokens" :min="1" :max="8192" />
                </el-form-item>
                <el-form-item label="Batch Chunk Size">
                  <el-input-number v-model="configForm.text.batch_chunk_size" :min="1" :max="100" />
                </el-form-item>
                <el-form-item label="行业语境">
                  <el-input v-model="configForm.text.domain_hint" placeholder="例如：无线通信行业（站点巡检/工单系统）" />
                </el-form-item>
              </el-form>
            </el-card>

            <el-card shadow="never">
              <template #header>
                <div class="card-header">
                  <span>Vision 模型</span>
                  <el-tag size="small" type="info">最多5张</el-tag>
                </div>
              </template>

              <el-form :model="configForm.vision" label-width="140px">
                <el-form-item label="Base URL">
                  <el-input v-model="configForm.vision.base_url" placeholder="例如：https://xxx.openai.azure.com/openai/v1" />
                </el-form-item>
                <el-form-item label="Model">
                  <el-input v-model="configForm.vision.model" placeholder="Azure 部署名（deployment_name），例如：gpt-5-nano" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input
                    v-model="visionApiKeyInput"
                    type="password"
                    show-password
                    :placeholder="configForm.vision.api_key_masked ? `已配置：${configForm.vision.api_key_masked}` : '未配置'"
                  />
                  <div class="form-help">
                    <el-button link type="danger" @click="clearVisionKey">清空 Key</el-button>
                  </div>
                </el-form-item>
                <el-form-item label="Chat Path">
                  <el-input v-model="configForm.vision.chat_completions_path" placeholder="/v1/chat/completions" />
                </el-form-item>
                <el-form-item label="Timeout(s)">
                  <el-input-number v-model="configForm.vision.timeout_seconds" :min="1" :max="600" />
                </el-form-item>
                <el-form-item label="Temperature">
                  <el-input-number v-model="configForm.vision.temperature" :min="0" :max="2" :step="0.1" />
                </el-form-item>
                <el-form-item label="Max Tokens">
                  <el-input-number v-model="configForm.vision.max_tokens" :min="1" :max="8192" />
                </el-form-item>
              </el-form>
            </el-card>
          </div>

          <el-card shadow="never" class="pricing-card">
            <template #header>
              <div class="card-header">
                <span>费用单价（tokens × 单价）</span>
                <div class="header-actions">
                  <el-select v-model="pricingCurrency" style="width: 120px">
                    <el-option label="USD" value="USD" />
                    <el-option label="CNY" value="CNY" />
                  </el-select>
                  <el-button :icon="Plus" @click="addPricingRow">新增模型</el-button>
                </div>
              </div>
            </template>

            <el-table :data="pricingRows" border style="width: 100%">
              <el-table-column label="Model" min-width="220">
                <template #default="{ row }">
                  <el-input v-model="row.model" placeholder="例如：gpt-5-nano" />
                </template>
              </el-table-column>
              <el-table-column label="Prompt / 1K tokens" min-width="200">
                <template #default="{ row }">
                  <el-input-number v-model="row.prompt_per_1k" :min="0" :step="0.0001" :precision="6" />
                </template>
              </el-table-column>
              <el-table-column label="Completion / 1K tokens" min-width="220">
                <template #default="{ row }">
                  <el-input-number v-model="row.completion_per_1k" :min="0" :step="0.0001" :precision="6" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="90" fixed="right">
                <template #default="{ $index }">
                  <el-button :icon="Delete" link type="danger" @click="removePricingRow($index)" />
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <div class="config-actions">
            <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
            <el-button :loading="testingText" @click="testText">测试 Text</el-button>
            <el-button :loading="testingVision" @click="testVision">测试 Vision</el-button>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="统计" name="stats">
        <div class="stats-section">
          <div class="stats-summary">
            <div class="stat-card">
              <div class="stat-icon calls">
                <el-icon><ChatDotRound /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ stats?.summary?.calls || 0 }}</div>
                <div class="stat-label">调用次数</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon success">
                <el-icon><CircleCheck /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ formatPercent(stats?.summary?.success_rate) }}</div>
                <div class="stat-label">成功率</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon duration">
                <el-icon><Clock /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ stats?.summary?.avg_duration_ms || 0 }}</div>
                <div class="stat-label">平均耗时(ms)</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon tokens">
                <el-icon><Tickets /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ stats?.summary?.total_tokens || 0 }}</div>
                <div class="stat-label">Tokens</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon cost">
                <el-icon><TrendCharts /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">
                  {{ formatMoney(stats?.summary?.estimated_cost) }} {{ stats?.summary?.currency || 'USD' }}
                </div>
                <div class="stat-label">估算费用</div>
              </div>
            </div>
          </div>

          <div class="charts-section">
            <div class="chart-card full-width">
              <div class="chart-header">
                <h3 class="chart-title">📈 趋势（按天）</h3>
                <el-radio-group v-model="trendMetric" size="small" @change="renderTrendChart">
                  <el-radio-button label="calls">调用次数</el-radio-button>
                  <el-radio-button label="success_calls">成功次数</el-radio-button>
                  <el-radio-button label="total_tokens">Tokens</el-radio-button>
                  <el-radio-button label="estimated_cost">费用</el-radio-button>
                </el-radio-group>
              </div>
            <div class="chart-container" ref="trendChartRef"></div>
            </div>

            <div class="chart-card">
              <h3 class="chart-title">🤖 按模型</h3>
              <div v-if="stats?.by_model?.length" class="distribution-list">
                <div v-for="(item, index) in stats.by_model" :key="`model-${index}`" class="dist-item">
                  <div class="dist-label">
                    <div class="dist-title">{{ item.key }}</div>
                    <div class="dist-sub">
                      成功率 {{ formatPercent(calcSuccessRate(item)) }} · Tokens {{ item.total_tokens || 0 }} · 费用
                      {{ formatMoney(item.estimated_cost) }} {{ stats?.summary?.currency || 'USD' }}
                    </div>
                  </div>
                  <div class="dist-bar">
                    <div
                      class="dist-bar-fill model-bar"
                      :style="{ width: getBreakdownPercentage(item.calls, stats.by_model) + '%' }"
                    ></div>
                  </div>
                  <div class="dist-count">{{ item.calls || 0 }}</div>
                </div>
              </div>
              <el-empty v-else description="暂无数据" :image-size="60" />
            </div>

            <div class="chart-card">
              <h3 class="chart-title">🧩 按业务</h3>
              <div v-if="stats?.by_operation?.length" class="distribution-list">
                <div v-for="(item, index) in stats.by_operation" :key="`op-${index}`" class="dist-item">
                  <div class="dist-label">
                    <div class="dist-title">{{ item.key }}</div>
                    <div class="dist-sub">
                      成功率 {{ formatPercent(calcSuccessRate(item)) }} · Tokens {{ item.total_tokens || 0 }} · 费用
                      {{ formatMoney(item.estimated_cost) }} {{ stats?.summary?.currency || 'USD' }}
                    </div>
                  </div>
                  <div class="dist-bar">
                    <div
                      class="dist-bar-fill op-bar"
                      :style="{ width: getBreakdownPercentage(item.calls, stats.by_operation) + '%' }"
                    ></div>
                  </div>
                  <div class="dist-count">{{ item.calls || 0 }}</div>
                </div>
              </div>
              <el-empty v-else description="暂无数据" :image-size="60" />
            </div>

            <div class="chart-card">
              <h3 class="chart-title">🖼️ 按模式</h3>
              <div v-if="stats?.by_mode?.length" class="distribution-list">
                <div v-for="(item, index) in stats.by_mode" :key="`mode-${index}`" class="dist-item">
                  <div class="dist-label">
                    <div class="dist-title">{{ item.key }}</div>
                    <div class="dist-sub">
                      成功率 {{ formatPercent(calcSuccessRate(item)) }} · Tokens {{ item.total_tokens || 0 }} · 费用
                      {{ formatMoney(item.estimated_cost) }} {{ stats?.summary?.currency || 'USD' }}
                    </div>
                  </div>
                  <div class="dist-bar">
                    <div
                      class="dist-bar-fill mode-bar"
                      :style="{ width: getBreakdownPercentage(item.calls, stats.by_mode) + '%' }"
                    ></div>
                  </div>
                  <div class="dist-count">{{ item.calls || 0 }}</div>
                </div>
              </div>
              <el-empty v-else description="暂无数据" :image-size="60" />
            </div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="日志" name="logs">
        <div class="logs-section">
          <div class="logs-toolbar">
            <el-select v-model="logFilters.success" style="width: 140px" clearable placeholder="成功/失败">
              <el-option label="成功" :value="true" />
              <el-option label="失败" :value="false" />
            </el-select>
            <el-select v-model="logFilters.mode" style="width: 140px" clearable placeholder="模式">
              <el-option label="text" value="text" />
              <el-option label="vision" value="vision" />
            </el-select>
            <el-input v-model="logFilters.model" style="width: 200px" clearable placeholder="模型（可模糊）" />
            <el-input v-model="logFilters.operation" style="width: 200px" clearable placeholder="Operation（可模糊）" />
            <el-button :icon="Search" @click="loadLogs" :loading="logLoading">查询</el-button>
          </div>

          <el-table v-loading="logLoading" :data="logs" border style="width: 100%">
            <el-table-column prop="created_at" label="时间" width="180" />
            <el-table-column prop="operator_name" label="操作人" width="140" />
            <el-table-column prop="operation" label="Operation" min-width="160" />
            <el-table-column prop="mode" label="Mode" width="90" />
            <el-table-column prop="model" label="Model" min-width="160" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="duration_ms" label="耗时(ms)" width="110" />
            <el-table-column prop="total_tokens" label="Tokens" width="110" />
            <el-table-column label="费用" width="150">
              <template #default="{ row }">
                {{ formatMoney(row.estimated_cost) }} {{ row.currency || 'USD' }}
              </template>
            </el-table-column>
            <el-table-column prop="error" label="错误" min-width="180" />
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openLogDetail(row.id)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-container">
            <el-pagination
              v-model:current-page="logPage"
              v-model:page-size="logPageSize"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              :total="logTotal"
              @size-change="handleLogSizeChange"
              @current-change="handleLogPageChange"
            />
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-drawer v-model="logDetailVisible" size="60%" title="AI 调用详情" :with-header="true">
      <div v-if="logDetail" class="log-detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="时间">{{ logDetail.created_at }}</el-descriptions-item>
          <el-descriptions-item label="操作人">{{ logDetail.operator_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="Operation">{{ logDetail.operation }}</el-descriptions-item>
          <el-descriptions-item label="Mode">{{ logDetail.mode }}</el-descriptions-item>
          <el-descriptions-item label="Model">{{ logDetail.model || '-' }}</el-descriptions-item>
          <el-descriptions-item label="Base URL">{{ logDetail.base_url || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="logDetail.success ? 'success' : 'danger'">{{ logDetail.success ? '成功' : '失败' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="耗时(ms)">{{ logDetail.duration_ms ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="Tokens">{{ logDetail.total_tokens ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="费用">
            {{ formatMoney(logDetail.estimated_cost) }} {{ logDetail.currency || 'USD' }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider />

        <el-collapse>
          <el-collapse-item title="Request Messages（已脱敏）" name="messages">
            <el-input :model-value="prettyJson(logDetail.request_messages)" type="textarea" :rows="12" readonly />
          </el-collapse-item>
          <el-collapse-item title="Request Input" name="input">
            <el-input :model-value="prettyJson(logDetail.request_input)" type="textarea" :rows="10" readonly />
          </el-collapse-item>
          <el-collapse-item title="Response Content" name="content">
            <el-input :model-value="logDetail.response_content || ''" type="textarea" :rows="10" readonly />
          </el-collapse-item>
          <el-collapse-item title="Response Raw" name="raw">
            <el-input :model-value="prettyJson(logDetail.response_raw)" type="textarea" :rows="12" readonly />
          </el-collapse-item>
          <el-collapse-item v-if="logDetail.error" title="Error" name="error">
            <el-input :model-value="String(logDetail.error || '')" type="textarea" :rows="6" readonly />
          </el-collapse-item>
          <el-collapse-item v-if="logDetail.context" title="Context" name="context">
            <el-input :model-value="prettyJson(logDetail.context)" type="textarea" :rows="6" readonly />
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, CircleCheck, Clock, Delete, Plus, Refresh, Search, Tickets, TrendCharts } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { aiAdminApi } from '@/api/system'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const canEditConfig = computed(() => userStore.hasPermission('system:ai:write'))

const activeTab = ref(canEditConfig.value ? 'config' : 'stats')
const selectedDays = ref(30)

const loading = ref(false)
const saving = ref(false)
const testingText = ref(false)
const testingVision = ref(false)

const configForm = ref({
  text: {
    base_url: '',
    model: '',
    api_key_masked: '',
    chat_completions_path: '/v1/chat/completions',
    timeout_seconds: 60,
    temperature: 0.2,
    max_tokens: 1024,
    batch_chunk_size: 20,
    domain_hint: '',
  },
  vision: {
    base_url: '',
    model: '',
    api_key_masked: '',
    chat_completions_path: '/v1/chat/completions',
    timeout_seconds: 60,
    temperature: 0.2,
    max_tokens: 1024,
  },
})

const textApiKeyInput = ref('')
const visionApiKeyInput = ref('')
const clearTextApiKeyFlag = ref(false)
const clearVisionApiKeyFlag = ref(false)

const pricingCurrency = ref('USD')
const pricingRows = ref([])

const stats = ref(null)
const trendChartRef = ref(null)
let trendChartInstance = null
const trendMetric = ref('calls')

const logs = ref([])
const logLoading = ref(false)
const logTotal = ref(0)
const logPage = ref(1)
const logPageSize = ref(20)
const logFilters = ref({
  success: undefined,
  mode: '',
  model: '',
  operation: '',
})

const logDetailVisible = ref(false)
const logDetail = ref(null)

const prettyJson = (value) => {
  try {
    if (value === null || value === undefined) return ''
    return JSON.stringify(value, null, 2)
  } catch (e) {
    return String(value || '')
  }
}

const formatPercent = (value) => {
  const v = Number(value || 0)
  return `${(v * 100).toFixed(2)}%`
}

const formatMoney = (value) => {
  const v = Number(value || 0)
  return Number.isFinite(v) ? v.toFixed(6).replace(/\.?0+$/, '') : '0'
}

const calcSuccessRate = (item) => {
  const calls = Number(item?.calls || 0)
  const succ = Number(item?.success_calls || 0)
  if (!calls) return 0
  return succ / calls
}

const getBreakdownPercentage = (value, items) => {
  if (!Array.isArray(items) || items.length === 0) return 0
  const max = Math.max(...items.map((i) => Number(i?.calls || 0))) || 1
  const v = Number(value || 0)
  return max > 0 ? (v / max) * 100 : 0
}

const hexToRgba = (hex, alpha) => {
  const h = String(hex || '').replace('#', '')
  if (h.length !== 6) return `rgba(102, 126, 234, ${alpha})`
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

const loadConfig = async () => {
  if (!canEditConfig.value) return
  loading.value = true
  try {
    const res = await aiAdminApi.getConfig()
    configForm.value.text = { ...configForm.value.text, ...(res?.text || {}) }
    configForm.value.vision = { ...configForm.value.vision, ...(res?.vision || {}) }

    pricingCurrency.value = res?.pricing?.currency || 'USD'
    const models = res?.pricing?.models || {}
    pricingRows.value = Object.keys(models).sort().map((k) => {
      const v = models[k] || {}
      return {
        model: k,
        prompt_per_1k: Number(v.prompt_per_1k || 0),
        completion_per_1k: Number(v.completion_per_1k || 0),
      }
    })

    textApiKeyInput.value = ''
    visionApiKeyInput.value = ''
    clearTextApiKeyFlag.value = false
    clearVisionApiKeyFlag.value = false
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载配置失败')
  } finally {
    loading.value = false
  }
}

const buildPricingPayload = () => {
  const models = {}
  for (const row of pricingRows.value || []) {
    const name = String(row.model || '').trim()
    if (!name) continue
    models[name] = {
      prompt_per_1k: Number(row.prompt_per_1k || 0),
      completion_per_1k: Number(row.completion_per_1k || 0),
    }
  }
  return {
    currency: String(pricingCurrency.value || 'USD'),
    models,
  }
}

const saveConfig = async () => {
  if (!canEditConfig.value) return
  saving.value = true
  try {
    const textPayload = {
      base_url: configForm.value.text.base_url,
      model: configForm.value.text.model,
      chat_completions_path: configForm.value.text.chat_completions_path,
      timeout_seconds: configForm.value.text.timeout_seconds,
      temperature: configForm.value.text.temperature,
      max_tokens: configForm.value.text.max_tokens,
      batch_chunk_size: configForm.value.text.batch_chunk_size,
      domain_hint: configForm.value.text.domain_hint,
    }
    const visionPayload = {
      base_url: configForm.value.vision.base_url,
      model: configForm.value.vision.model,
      chat_completions_path: configForm.value.vision.chat_completions_path,
      timeout_seconds: configForm.value.vision.timeout_seconds,
      temperature: configForm.value.vision.temperature,
      max_tokens: configForm.value.vision.max_tokens,
    }

    if (clearTextApiKeyFlag.value) {
      textPayload.api_key = ''
    } else if (textApiKeyInput.value.trim()) {
      textPayload.api_key = textApiKeyInput.value.trim()
    }

    if (clearVisionApiKeyFlag.value) {
      visionPayload.api_key = ''
    } else if (visionApiKeyInput.value.trim()) {
      visionPayload.api_key = visionApiKeyInput.value.trim()
    }

    const payload = {
      text: textPayload,
      vision: visionPayload,
      pricing: buildPricingPayload(),
    }

    const res = await aiAdminApi.updateConfig(payload)
    configForm.value.text = { ...configForm.value.text, ...(res?.text || {}) }
    configForm.value.vision = { ...configForm.value.vision, ...(res?.vision || {}) }
    pricingCurrency.value = res?.pricing?.currency || pricingCurrency.value

    const models = res?.pricing?.models || {}
    pricingRows.value = Object.keys(models).sort().map((k) => {
      const v = models[k] || {}
      return {
        model: k,
        prompt_per_1k: Number(v.prompt_per_1k || 0),
        completion_per_1k: Number(v.completion_per_1k || 0),
      }
    })

    textApiKeyInput.value = ''
    visionApiKeyInput.value = ''
    clearTextApiKeyFlag.value = false
    clearVisionApiKeyFlag.value = false

    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const testText = async () => {
  testingText.value = true
  try {
    const res = await aiAdminApi.test({ mode: 'text', prompt: 'ping' })
    ElMessage.success(`Text 测试成功：${res?.duration_ms || 0}ms，tokens=${res?.total_tokens ?? '-'}，model=${res?.model || ''}`)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '测试失败')
  } finally {
    testingText.value = false
  }
}

const testVision = async () => {
  testingVision.value = true
  try {
    const res = await aiAdminApi.test({ mode: 'vision', prompt: 'ping' })
    ElMessage.success(`Vision 测试成功：${res?.duration_ms || 0}ms，tokens=${res?.total_tokens ?? '-'}，model=${res?.model || ''}`)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '测试失败')
  } finally {
    testingVision.value = false
  }
}

const clearTextKey = () => {
  clearTextApiKeyFlag.value = true
  textApiKeyInput.value = ''
  ElMessage.warning('已标记：保存后将清空 Text API Key')
}

const clearVisionKey = () => {
  clearVisionApiKeyFlag.value = true
  visionApiKeyInput.value = ''
  ElMessage.warning('已标记：保存后将清空 Vision API Key')
}

const addPricingRow = () => {
  pricingRows.value.push({ model: '', prompt_per_1k: 0, completion_per_1k: 0 })
}

const removePricingRow = (index) => {
  pricingRows.value.splice(index, 1)
}

const loadStats = async () => {
  loading.value = true
  try {
    const res = await aiAdminApi.getStats({ days: selectedDays.value })
    stats.value = res || null
    await nextTick()
    renderTrendChart()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载统计失败')
  } finally {
    loading.value = false
  }
}

const loadLogs = async () => {
  logLoading.value = true
  try {
    const params = {
      days: selectedDays.value,
      skip: (logPage.value - 1) * logPageSize.value,
      limit: logPageSize.value,
    }
    if (logFilters.value.success !== undefined && logFilters.value.success !== null && logFilters.value.success !== '') {
      params.success = logFilters.value.success
    }
    if (logFilters.value.mode) params.mode = logFilters.value.mode
    if (logFilters.value.model) params.model = logFilters.value.model
    if (logFilters.value.operation) params.operation = logFilters.value.operation

    const res = await aiAdminApi.getLogs(params)
    logs.value = res?.items || []
    logTotal.value = res?.total || 0
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载日志失败')
  } finally {
    logLoading.value = false
  }
}

const openLogDetail = async (id) => {
  logDetailVisible.value = true
  logDetail.value = null
  try {
    const res = await aiAdminApi.getLogDetail(id)
    logDetail.value = res || null
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载详情失败')
  }
}

const handleLogPageChange = () => {
  loadLogs()
}

const handleLogSizeChange = () => {
  logPage.value = 1
  loadLogs()
}

const handleTabChange = () => {
  handleRefresh()
}

const handleRefresh = () => {
  if (activeTab.value === 'config') {
    loadConfig()
  } else if (activeTab.value === 'stats') {
    loadStats()
  } else if (activeTab.value === 'logs') {
    loadLogs()
  }
}

const renderTrendChart = () => {
  if (activeTab.value !== 'stats') return
  if (!trendChartRef.value) return
  if (!trendChartInstance) {
    trendChartInstance = echarts.init(trendChartRef.value)
  }

  const daily = stats.value?.daily || []
  const dates = daily.map((d) => d.date)
  const currency = stats.value?.summary?.currency || 'USD'

  const configs = {
    calls: {
      label: '调用次数',
      yAxisName: '调用次数',
      color: '#667eea',
      data: daily.map((d) => d.calls || 0),
    },
    success_calls: {
      label: '成功次数',
      yAxisName: '成功次数',
      color: '#43e97b',
      data: daily.map((d) => d.success_calls || 0),
    },
    total_tokens: {
      label: 'Tokens',
      yAxisName: 'Tokens',
      color: '#4facfe',
      data: daily.map((d) => d.total_tokens || 0),
    },
    estimated_cost: {
      label: `费用(${currency})`,
      yAxisName: currency,
      color: '#f093fb',
      data: daily.map((d) => Number(d.estimated_cost || 0)),
    },
  }

  const cfg = configs[trendMetric.value] || configs.calls
  const tooltipFormatter = (params) => {
    const p = Array.isArray(params) ? params[0] : null
    const axisValue = p?.axisValue ?? ''
    const value = p?.value ?? 0
    if (trendMetric.value === 'estimated_cost') {
      return `${axisValue}<br/>${cfg.label}: ${formatMoney(value)}`
    }
    return `${axisValue}<br/>${cfg.label}: ${value}`
  }

  trendChartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: tooltipFormatter,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        rotate: 45,
      },
    },
    yAxis: {
      type: 'value',
      name: cfg.yAxisName,
    },
    series: [
      {
        data: cfg.data,
        type: 'line',
        smooth: true,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: hexToRgba(cfg.color, 0.4) },
            { offset: 1, color: hexToRgba(cfg.color, 0.05) },
          ]),
        },
        lineStyle: {
          color: cfg.color,
          width: 3,
        },
        itemStyle: {
          color: cfg.color,
        },
      },
    ],
  })
}

const handleResize = () => {
  if (trendChartInstance) {
    trendChartInstance.resize()
  }
}

watch(
  () => stats.value?.daily,
  () => nextTick(() => renderTrendChart()),
)

watch(
  () => trendMetric.value,
  () => nextTick(() => renderTrendChart()),
)

onMounted(async () => {
  window.addEventListener('resize', handleResize)
  await loadStats()
  await loadLogs()
  await loadConfig()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (trendChartInstance) {
    trendChartInstance.dispose()
    trendChartInstance = null
  }
})
</script>

<style scoped>
.ai-management {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-group {
  display: flex;
  gap: 12px;
  align-items: center;
}

.config-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.pricing-card {
  margin-top: 4px;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.config-actions {
  display: flex;
  gap: 10px;
}

.form-help {
  margin-top: 6px;
}

.stats-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-summary {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}

.stat-card {
  background: white;
  border-radius: 16px;
  padding: 22px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: white;
}

.stat-icon.calls {
  background: linear-gradient(135deg, #667eea, #764ba2);
}

.stat-icon.success {
  background: linear-gradient(135deg, #43e97b, #38f9d7);
}

.stat-icon.duration {
  background: linear-gradient(135deg, #4facfe, #00f2fe);
}

.stat-icon.tokens {
  background: linear-gradient(135deg, #f093fb, #f5576c);
}

.stat-icon.cost {
  background: linear-gradient(135deg, #fa709a, #fee140);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1f2937;
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: #6b7280;
  margin-top: 4px;
}

.charts-section {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.chart-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}

.chart-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.chart-container {
  height: 320px;
}

.distribution-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dist-item {
  display: grid;
  grid-template-columns: 210px 1fr 70px;
  align-items: center;
  gap: 12px;
}

.dist-label {
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.dist-title {
  font-size: 13px;
  color: #4b5563;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dist-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dist-bar {
  height: 8px;
  background: #f3f4f6;
  border-radius: 4px;
  overflow: hidden;
}

.dist-bar-fill {
  height: 100%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.dist-bar-fill.op-bar {
  background: linear-gradient(135deg, #f093fb, #f5576c);
}

.dist-bar-fill.mode-bar {
  background: linear-gradient(135deg, #4facfe, #00f2fe);
}

.dist-count {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  text-align: right;
}

.logs-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.pagination-container {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.log-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@media (max-width: 1200px) {
  .config-grid {
    grid-template-columns: 1fr;
  }
  .stats-summary {
    grid-template-columns: repeat(2, 1fr);
  }
  .charts-section {
    grid-template-columns: 1fr;
  }
  .chart-card.full-width {
    grid-column: 1;
  }
  .dist-item {
    grid-template-columns: 180px 1fr 70px;
  }
}

@media (max-width: 768px) {
  .stats-summary {
    grid-template-columns: 1fr;
  }
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .dist-item {
    grid-template-columns: 1fr;
    align-items: start;
  }
  .dist-count {
    text-align: left;
  }
}
</style>
