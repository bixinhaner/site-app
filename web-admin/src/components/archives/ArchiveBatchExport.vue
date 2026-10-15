<template>
  <el-button :disabled="!rows.length || running" :loading="starting" @click="start">
    <el-icon><Download /></el-icon>
    批量导出PDF（{{ rows.length }}）
  </el-button>

  <el-dialog v-model="visible" title="批量导出PDF" width="560px" :close-on-click-modal="false">
    <template v-if="job">
      <p class="batch-export-status">{{ statusText }}</p>
      <el-progress
        :percentage="percent"
        :status="job.status === 'done' ? 'success' : job.status === 'failed' ? 'exception' : undefined"
      />
      <p v-if="job.current_name && running" class="batch-export-current">正在导出：{{ job.current_name }}</p>
      <p v-if="job.status === 'done'" class="batch-export-current">
        成功 {{ job.success_count }} 个，失败 {{ job.errors.length }} 个
      </p>
      <el-alert
        v-if="job.status === 'failed' && job.message"
        type="error"
        :closable="false"
        :title="job.message"
        class="batch-export-alert"
      />
      <el-table v-if="job.errors.length" :data="job.errors" size="small" max-height="200" class="batch-export-alert">
        <el-table-column prop="name" label="档案" min-width="200" />
        <el-table-column prop="message" label="原因" min-width="140" />
      </el-table>
      <p v-if="running" class="batch-export-tip">照片已压缩以控制文件大小，可关闭此窗口，完成后会自动下载。</p>
    </template>
    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button v-if="job && job.status === 'done'" type="primary" @click="download">下载</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { archiveExportsApi } from '@/api/archiveExports'
import { getCurrentLocale } from '@/i18n/translator'
import { getApiErrorMessage } from '@/utils/apiError'

const MAX_BATCH = 30
const POLL_MS = 2000

const props = defineProps({
  archiveType: { type: String, required: true },
  rows: { type: Array, default: () => [] },
})
const emit = defineEmits(['done'])

const visible = ref(false)
const starting = ref(false)
const job = ref(null)
let timer = null
let downloaded = false

const running = computed(() => ['queued', 'running'].includes(job.value?.status))
const percent = computed(() => {
  if (!job.value?.total) return 0
  return Math.round((job.value.done / job.value.total) * 100)
})
const statusText = computed(() => {
  const j = job.value
  if (!j) return ''
  if (j.status === 'queued') return '排队中，请稍候…'
  if (j.status === 'running') return `已完成 ${j.done}/${j.total}`
  if (j.status === 'done') return '导出完成'
  return '导出失败'
})

const stopPolling = () => {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
}

const download = () => {
  if (!job.value) return
  const a = document.createElement('a')
  a.href = archiveExportsApi.downloadUrl(job.value.job_id)
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

const poll = async () => {
  try {
    job.value = await archiveExportsApi.get(job.value.job_id)
  } catch (e) {
    console.error(e)
    stopPolling()
    ElMessage.error(getApiErrorMessage(e, '获取导出进度失败'))
    return
  }
  if (running.value) {
    timer = setTimeout(poll, POLL_MS)
    return
  }
  stopPolling()
  if (job.value.status === 'done' && !downloaded) {
    downloaded = true
    download()
    emit('done', job.value)
  }
}

const start = async () => {
  const ids = props.rows.map(row => row.id)
  if (!ids.length) return
  if (ids.length > MAX_BATCH) {
    ElMessage.warning(`单次最多导出 ${MAX_BATCH} 个档案，当前已选 ${ids.length} 个`)
    return
  }
  try {
    starting.value = true
    stopPolling()
    downloaded = false
    job.value = await archiveExportsApi.create({
      archive_type: props.archiveType,
      ids,
      locale: getCurrentLocale(),
    })
    visible.value = true
    timer = setTimeout(poll, 500)
  } catch (e) {
    console.error(e)
    ElMessage.error(getApiErrorMessage(e, '批量导出失败，请稍后重试'))
  } finally {
    starting.value = false
  }
}

onBeforeUnmount(stopPolling)
</script>

<style scoped>
.batch-export-status { margin: 0 0 8px; font-weight: 600; }
.batch-export-current { margin: 8px 0 0; color: var(--el-text-color-secondary); word-break: break-all; }
.batch-export-alert { margin-top: 12px; }
.batch-export-tip { margin: 12px 0 0; font-size: 12px; color: var(--el-text-color-secondary); }
</style>
