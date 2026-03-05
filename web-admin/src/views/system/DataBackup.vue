<template>
  <div class="page">
    <div class="page-header">
      <h1>数据备份</h1>
      <div class="header-actions">
        <el-button @click="loadAll" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <el-card class="mb16">
      <template #header>
        <div class="card-header">
          <span>备份策略配置</span>
        </div>
      </template>
      <el-form :model="configForm" label-width="120px" :inline="false">
        <el-form-item label="启用定时备份">
          <el-switch v-model="configForm.enabled" />
        </el-form-item>
        <el-form-item label="备份周期">
          <el-radio-group v-model="configForm.mode">
            <el-radio label="hours">每 N 小时</el-radio>
            <el-radio label="days">每 N 天</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="时间间隔">
          <el-input-number v-model="configForm.interval" :min="1" :max="365" />
          <span class="ml8 hint" v-if="configForm.mode === 'hours'">单位：小时</span>
          <span class="ml8 hint" v-else>单位：天</span>
        </el-form-item>
        <el-form-item label="上次执行时间">
          <span>{{ formatDateTime(configMeta.last_run_at) || '-' }}</span>
        </el-form-item>
        <el-form-item label="上次成功时间">
          <span>{{ formatDateTime(configMeta.last_success_at) || '-' }}</span>
        </el-form-item>
        <el-form-item label="下一次执行时间">
          <span>{{ formatDateTime(configMeta.next_run_at) || '-' }}</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveConfig">
            保存配置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="mb16">
      <template #header>
        <div class="card-header">
          <span>手动备份</span>
        </div>
      </template>
      <p class="hint">
        手动备份会立即对当前所有数据库文件进行打包备份，备份结果会记录在下方的备份历史中。
      </p>
      <el-button
        type="primary"
        :loading="manualLoading"
        @click="runManualBackup"
      >
        <el-icon><Upload /></el-icon>
        <span v-if="manualLoading">正在执行备份...</span>
        <span v-else>立即备份</span>
      </el-button>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>备份历史记录</span>
        </div>
      </template>
      <el-table
        :data="historyItems"
        v-loading="historyLoading"
        size="small"
        stripe
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="trigger_type" label="触发方式" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="row.trigger_type === 'manual' ? 'primary' : 'info'">
              {{ triggerTypeText(row.trigger_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="trigger_user_name" label="触发人" width="140" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.status === 'success' ? 'success' : 'danger'"
            >
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" min-width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.started_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="finished_at" label="完成时间" min-width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.finished_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="duration_seconds" label="耗时(秒)" width="100">
          <template #default="{ row }">
            {{ row.duration_seconds != null ? row.duration_seconds.toFixed(1) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="backup_file" label="备份文件" min-width="220">
          <template #default="{ row }">
            <span class="mono">{{ row.backup_file || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" min-width="260">
          <template #default="{ row }">
            <span class="error-text" v-if="row.error_message">
              {{ row.error_message }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'success'"
              link
              type="primary"
              size="small"
              :loading="downloadingId === row.id"
              @click="downloadBackup(row)"
            >
              下载
            </el-button>
            <el-button
              v-if="row.status === 'success'"
              link
              type="danger"
              size="small"
              :loading="restoringId === row.id"
              @click="confirmRestore(row)"
            >
              恢复
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination" v-if="historyTotal > historyPageSize">
        <el-pagination
          background
          layout="prev, pager, next, jumper"
          :page-size="historyPageSize"
          :current-page="historyPage"
          :total="historyTotal"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-card class="mt16">
      <template #header>
        <div class="card-header">
          <span>恢复操作记录</span>
        </div>
      </template>
      <el-table
        :data="restoreHistoryItems"
        v-loading="restoreHistoryLoading"
        size="small"
        stripe
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="timestamp" label="时间" min-width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="140" />
        <el-table-column prop="action" label="操作" width="180">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.action === 'data_backup_restore_success' ? 'success' : 'danger'"
            >
              {{ row.action === 'data_backup_restore_success' ? '恢复成功' : '恢复失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="record_id" label="备份记录ID" width="120" />
        <el-table-column prop="backup_file" label="备份文件" min-width="220">
          <template #default="{ row }">
            <span class="mono">{{ row.backup_file || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误信息" min-width="260">
          <template #default="{ row }">
            <span class="error-text" v-if="row.error">
              {{ row.error }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination" v-if="restoreHistoryTotal > restoreHistoryPageSize">
        <el-pagination
          background
          layout="prev, pager, next, jumper"
          :page-size="restoreHistoryPageSize"
          :current-page="restoreHistoryPage"
          :total="restoreHistoryTotal"
          @current-change="handleRestorePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Upload } from '@element-plus/icons-vue'
import { systemBackupApi } from '@/api/system'

const loading = ref(false)
const saving = ref(false)
const manualLoading = ref(false)
const historyLoading = ref(false)
const restoreHistoryLoading = ref(false)

const configForm = ref({
  enabled: false,
  mode: 'days',
  interval: 1,
})

const configMeta = ref({
  last_run_at: null,
  last_success_at: null,
  next_run_at: null,
})

const historyItems = ref([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = ref(10)
const restoringId = ref(null)
const downloadingId = ref(null)

const restoreHistoryItems = ref([])
const restoreHistoryTotal = ref(0)
const restoreHistoryPage = ref(1)
const restoreHistoryPageSize = ref(10)

const formatDateTime = (val) => {
  if (!val) return ''
  const d = new Date(val)
  if (Number.isNaN(d.getTime())) return val
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const triggerTypeText = (type) => {
  const map = {
    manual: '手动',
    scheduled: '定时',
  }
  return map[type] || type
}

const loadConfig = async () => {
  loading.value = true
  try {
    const res = await systemBackupApi.getConfig()
    configForm.value.enabled = !!res.enabled
    configForm.value.mode = res.mode || 'days'
    configForm.value.interval = res.interval || 1
    configMeta.value.last_run_at = res.last_run_at || null
    configMeta.value.last_success_at = res.last_success_at || null
    configMeta.value.next_run_at = res.next_run_at || null
  } catch (e) {
    console.error(e)
    ElMessage.error('加载备份配置失败')
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  if (!configForm.value.interval || configForm.value.interval < 1) {
    ElMessage.warning('请填写有效的时间间隔')
    return
  }
  saving.value = true
  try {
    const res = await systemBackupApi.updateConfig({
      enabled: configForm.value.enabled,
      mode: configForm.value.mode,
      interval: configForm.value.interval,
    })
    configMeta.value.last_run_at = res.last_run_at || null
    configMeta.value.last_success_at = res.last_success_at || null
    configMeta.value.next_run_at = res.next_run_at || null
    ElMessage.success('备份配置已保存')
  } catch (e) {
    console.error(e)
    ElMessage.error('保存备份配置失败')
  } finally {
    saving.value = false
  }
}

const loadHistory = async () => {
  historyLoading.value = true
  try {
    const res = await systemBackupApi.getHistory({
      page: historyPage.value,
      page_size: historyPageSize.value,
    })
    historyItems.value = Array.isArray(res.items) ? res.items : []
    historyTotal.value = res.total || 0
  } catch (e) {
    console.error(e)
    ElMessage.error('加载备份历史失败')
  } finally {
  historyLoading.value = false
  }
}

const handlePageChange = (page) => {
  historyPage.value = page
  loadHistory()
}

const loadRestoreHistory = async () => {
  restoreHistoryLoading.value = true
  try {
    const res = await systemBackupApi.getRestoreHistory({
      page: restoreHistoryPage.value,
      page_size: restoreHistoryPageSize.value,
    })
    restoreHistoryItems.value = Array.isArray(res.items) ? res.items : []
    restoreHistoryTotal.value = res.total || 0
  } catch (e) {
    console.error(e)
    ElMessage.error('加载恢复记录失败')
  } finally {
    restoreHistoryLoading.value = false
  }
}

const handleRestorePageChange = (page) => {
  restoreHistoryPage.value = page
  loadRestoreHistory()
}

const getBackupZipName = (row) => {
  const fallback = `db_backup_${row?.id || Date.now()}.zip`
  const source = row?.backup_file
  if (!source) return fallback

  const parts = String(source).split(/[\\/]/)
  const fileName = parts[parts.length - 1]
  if (!fileName) return fallback
  return fileName.endsWith('.zip') ? fileName : fallback
}

const parseBlobErrorMessage = async (error, fallback = '下载备份失败') => {
  const payload = error?.response?.data
  if (payload instanceof Blob) {
    try {
      const text = await payload.text()
      const obj = JSON.parse(text)
      if (obj?.detail) return obj.detail
      if (obj?.message) return obj.message
    } catch {
      // 忽略 Blob 解析失败
    }
  }
  return error?.response?.data?.detail || error?.message || fallback
}

const downloadBackup = async (row) => {
  if (!row || row.status !== 'success') return
  if (downloadingId.value) return

  downloadingId.value = row.id
  try {
    const res = await systemBackupApi.downloadBackup(row.id)
    const blob = res instanceof Blob ? res : new Blob([res], { type: 'application/zip' })
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = getBackupZipName(row)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
    ElMessage.success('备份文件下载已开始')
  } catch (e) {
    console.error(e)
    ElMessage.error(await parseBlobErrorMessage(e))
  } finally {
    downloadingId.value = null
  }
}

const confirmRestore = (row) => {
  if (restoringId.value) return

  ElMessageBox.prompt(
    `此操作会用该备份中的数据库文件覆盖当前系统数据，最近的变更将丢失。\n\n备份文件：${row.backup_file || '-'}\n\n请在下方输入大写 RESTORE 以确认：`,
    '确认恢复到此备份',
    {
      confirmButtonText: '恢复',
      cancelButtonText: '取消',
      type: 'warning',
      inputValidator: (val) => {
        if (val !== 'RESTORE') return '请输入大写 RESTORE 以确认'
        return true
      },
    },
  )
    .then(async ({ value }) => {
      restoringId.value = row.id
      ElMessage.info('正在从备份恢复数据，请稍候...')
      try {
        const res = await systemBackupApi.restore(row.id, value)
        if (res.success) {
          ElMessage.success('恢复完成，建议刷新页面并重新登录')
          await loadRestoreHistory()
        } else {
          ElMessage.error(res.error || '恢复失败，请查看系统日志')
        }
      } catch (e) {
        console.error(e)
        ElMessage.error('恢复请求失败')
      } finally {
        restoringId.value = null
      }
    })
    .catch(() => {
      // 用户取消
    })
}

const runManualBackup = async () => {
  if (manualLoading.value) return
  manualLoading.value = true
  ElMessage.info('开始执行备份，请稍候...')
  try {
    const res = await systemBackupApi.runBackup()
    if (res.success) {
      ElMessage.success('备份成功')
    } else {
      ElMessage.error(res.error || '备份失败，请查看备份历史或系统日志')
    }
    await loadHistory()
    await loadConfig()
  } catch (e) {
    console.error(e)
    ElMessage.error('备份请求失败')
  } finally {
    manualLoading.value = false
  }
}

const loadAll = async () => {
  await Promise.all([loadConfig(), loadHistory(), loadRestoreHistory()])
}

onMounted(() => {
  loadAll()
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
.ml8 {
  margin-left: 8px;
}
.hint {
  color: #909399;
  font-size: 13px;
}
.mono {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}
.error-text {
  color: #f56c6c;
  font-size: 12px;
}
.pagination {
  margin-top: 12px;
  text-align: right;
}
</style>
