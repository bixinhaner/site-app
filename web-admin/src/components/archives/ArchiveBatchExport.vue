<template>
  <el-button :disabled="!rows.length || busy" :loading="loadingKind === 'selected'" @click="openPreview('selected')">
    <el-icon><Download /></el-icon>
    批量导出PDF（{{ rows.length }}）
  </el-button>
  <el-button :disabled="!total || busy" :loading="loadingKind === 'all'" @click="openPreview('all')">
    <el-icon><Download /></el-icon>
    导出全部（{{ total }}）
  </el-button>

  <el-dialog v-model="visible" title="批量导出PDF" width="560px" :close-on-click-modal="false">
    <!-- 导出前确认：数量 / 已生成 / 大小 / 分卷 / 等待时间 -->
    <template v-if="stage === 'confirm' && preview">
      <div class="batch-export-lines">
        <p class="batch-export-status">共 {{ preview.total }} 个档案</p>
        <p>已生成 {{ preview.cached_count }} 个，需新生成 {{ preview.render_count }} 个</p>
        <p v-if="preview.missing_count">{{ preview.missing_count }} 个档案不存在，将跳过</p>
        <p v-if="preview.parts > 1">预计大小：约 {{ formatSize(preview.estimated_bytes) }}，分 {{ preview.parts }} 卷下载</p>
        <p v-else>预计大小：约 {{ formatSize(preview.estimated_bytes) }}</p>
        <p>{{ waitText }}</p>
        <p v-if="preview.queue_ahead">前面有 {{ preview.queue_ahead }} 个导出任务排队</p>
      </div>
      <p class="batch-export-tip">PDF 中照片已压缩以控制文件大小；需要原图请在档案详情页「导出Zip」。</p>
    </template>

    <!-- 生成进度与下载 -->
    <template v-else-if="job">
      <p class="batch-export-status">{{ statusText }}</p>
      <el-progress
        :percentage="percent"
        :status="job.status === 'done' ? 'success' : job.status === 'failed' ? 'exception' : undefined"
      />
      <p v-if="job.current_name && running" class="batch-export-current">正在导出：{{ job.current_name }}</p>
      <template v-if="job.status === 'done'">
        <p class="batch-export-current">成功 {{ job.success_count }} 个，失败 {{ job.errors.length }} 个</p>
        <p v-if="job.cached_count" class="batch-export-current">其中 {{ job.cached_count }} 个直接使用已生成的PDF</p>
        <div v-if="job.parts.length > 1" class="batch-export-parts">
          <div v-for="part in job.parts" :key="part.index" class="batch-export-part">
            <span>第 {{ part.index }} 卷：{{ part.count }} 个档案，{{ formatSize(part.size) }}</span>
            <el-button size="small" @click="download(part.index)">下载</el-button>
          </div>
        </div>
      </template>
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
      <p v-if="running" class="batch-export-tip">可关闭此窗口继续使用本页面，完成后会自动弹出下载。</p>
    </template>

    <template #footer>
      <template v-if="stage === 'confirm'">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="starting" @click="start">开始导出</el-button>
      </template>
      <template v-else>
        <el-button @click="visible = false">关闭</el-button>
        <el-button
          v-if="job && job.status === 'done' && job.parts.length === 1"
          type="primary"
          @click="download(1)"
        >
          下载
        </el-button>
      </template>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { archiveExportsApi } from '@/api/archiveExports'
import { getCurrentLocale } from '@/i18n/translator'
import { getApiErrorMessage } from '@/utils/apiError'

const POLL_MS = 2000

const props = defineProps({
  archiveType: { type: String, required: true },
  rows: { type: Array, default: () => [] },
  // 列表页当前筛选条件：{ keyword, dateRange }，用于「导出全部」
  filters: { type: Object, default: () => ({}) },
  total: { type: Number, default: 0 },
})
const emit = defineEmits(['done'])

const visible = ref(false)
const stage = ref('confirm')
const loadingKind = ref('')
const starting = ref(false)
const preview = ref(null)
const selection = ref(null)
const job = ref(null)
let timer = null
let downloaded = false

const running = computed(() => ['queued', 'running'].includes(job.value?.status))
const busy = computed(() => running.value || !!loadingKind.value)
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
const waitText = computed(() => {
  const s = Number(preview.value?.estimated_seconds || 0)
  if (!preview.value?.render_count) return '无需等待，可直接下载'
  if (s < 60) return '预计等待：少于 1 分钟'
  const minutes = Math.ceil(s / 60)
  if (minutes < 60) return `预计等待：约 ${minutes} 分钟`
  return `预计等待：约 ${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分钟`
})

const formatSize = (bytes) => {
  const n = Number(bytes || 0)
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)} GB`
  if (n >= 1024 ** 2) return `${Math.max(1, Math.round(n / 1024 ** 2))} MB`
  return `${Math.max(1, Math.round(n / 1024))} KB`
}

const buildSelection = (kind) => {
  const base = { archive_type: props.archiveType, locale: getCurrentLocale() }
  if (kind === 'selected') return { ...base, ids: props.rows.map(row => row.id) }
  const filters = { keyword: props.filters?.keyword || undefined }
  const range = props.filters?.dateRange
  if (range && range.length === 2) {
    filters.date_from = new Date(range[0]).toISOString()
    filters.date_to = new Date(range[1]).toISOString()
  }
  return { ...base, filters }
}

const stopPolling = () => {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
}

const download = (part = 1) => {
  if (!job.value) return
  const a = document.createElement('a')
  a.href = archiveExportsApi.downloadUrl(job.value.job_id, part)
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

const openPreview = async (kind) => {
  try {
    loadingKind.value = kind
    selection.value = buildSelection(kind)
    preview.value = await archiveExportsApi.preview(selection.value)
    stage.value = 'confirm'
    visible.value = true
  } catch (e) {
    console.error(e)
    ElMessage.error(getApiErrorMessage(e, '批量导出失败，请稍后重试'))
  } finally {
    loadingKind.value = ''
  }
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
  visible.value = true
  if (job.value.status === 'done' && !downloaded) {
    downloaded = true
    // 单卷自动下载；多卷由用户在窗口中逐个点击（浏览器会拦截连续自动下载）
    if (job.value.parts.length === 1) download(1)
    emit('done', job.value)
  }
}

const start = async () => {
  try {
    starting.value = true
    stopPolling()
    downloaded = false
    job.value = await archiveExportsApi.create(selection.value)
    stage.value = 'progress'
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
.batch-export-lines p { margin: 0 0 6px; }
.batch-export-current { margin: 8px 0 0; color: var(--el-text-color-secondary); word-break: break-all; }
.batch-export-alert { margin-top: 12px; }
.batch-export-tip { margin: 12px 0 0; font-size: 12px; color: var(--el-text-color-secondary); }
.batch-export-parts { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.batch-export-part { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
</style>
