<template>
  <div class="page">
    <div class="page-header">
      <h1>勘察阶段批量设置</h1>
      <div class="header-actions">
        <el-button @click="goBack"><el-icon><Back /></el-icon>返回</el-button>
      </div>
    </div>

    <el-card class="mb16">
      <el-tabs v-model="mode" type="card">
        <el-tab-pane label="批量跳过勘察" name="skip">
          <el-alert
            title="仅对处于勘察阶段（survey_pending）、且不存在进行中勘察工单的站点生效。"
            type="info"
            :closable="false"
            class="mb12"
          />
        </el-tab-pane>
        <el-tab-pane label="批量恢复需要勘察" name="require">
          <el-alert
            title="仅对规划阶段（planning）、且未形成任何规划版本的站点生效（将回退到 survey_pending）。"
            type="info"
            :closable="false"
            class="mb12"
          />
        </el-tab-pane>
      </el-tabs>

      <div class="import-row">
        <el-button @click="downloadTemplate"><el-icon><Download /></el-icon>下载模板</el-button>
        <template v-if="canEdit">
          <el-switch v-model="dryRun" active-text="试运行(dry run)" />
          <el-upload :show-file-list="false" :before-upload="() => true" :http-request="onUpload">
            <el-button type="success" :loading="uploading">
              <el-icon><Upload /></el-icon>{{ dryRun ? '试运行' : '执行批量' }}
            </el-button>
          </el-upload>
        </template>
        <span v-if="summaryText" class="import-info">{{ summaryText }}</span>
        <el-tag v-if="batchId" type="info">批次ID: {{ batchId }}</el-tag>
      </div>
    </el-card>

    <el-card>
      <el-table :data="results" border v-loading="loading">
        <el-table-column prop="row_index" label="行号" width="90" />
        <el-table-column prop="site_code" label="站点编码" width="180" />
        <el-table-column prop="site_name" label="站点名称" min-width="180" />
        <el-table-column label="结果" width="120">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="action" label="动作" width="140">
          <template #default="{ row }">
            <span>{{ actionText(row.action) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提示" min-width="240">
          <template #default="{ row }">
            <div v-if="row.warnings && row.warnings.length">
              <div v-for="(w, i) in row.warnings" :key="i">• {{ w }}</div>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="错误" min-width="320">
          <template #default="{ row }">
            <div v-if="row.errors && row.errors.length">
              <div v-for="(e, i) in row.errors" :key="i">- {{ e }}</div>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import siteSurveyStageApi from '@/api/siteSurveyStage'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const userStore = useUserStore()
const canEdit = computed(() => ['admin', 'manager'].includes(userStore.user?.role))

const mode = ref('skip')
const dryRun = ref(true)
const loading = ref(false)
const uploading = ref(false)
const results = ref([])
const batchId = ref('')
const summaryText = ref('')

const goBack = () => router.back()

const actionText = (action) => {
  const map = {
    noop: '无需变更',
    skipped: '已跳过勘察',
    required: '已恢复需要勘察',
    would_skip: '将跳过勘察',
    would_require: '将恢复需要勘察'
  }
  return map[action] || (action || '-')
}

const downloadTemplate = async () => {
  try {
    const res = await siteSurveyStageApi.downloadTemplate(mode.value)
    const blob = new Blob([res])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = mode.value === 'require'
      ? 'site_survey_stage_require_template.xlsx'
      : 'site_survey_stage_skip_template.xlsx'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error(e)
    ElMessage.error('下载模板失败')
  }
}

const onUpload = async (opts) => {
  try {
    uploading.value = true
    loading.value = true
    summaryText.value = '正在解析...'
    batchId.value = ''
    results.value = []

    const res = await siteSurveyStageApi.batchUpload(opts.file, mode.value, dryRun.value)
    results.value = res.results || []
    batchId.value = res.batch_id || ''
    summaryText.value = `共 ${res.total_rows} 行，成功 ${res.success_count} 行，失败 ${res.failed_count} 行`
    opts.onSuccess(res)
  } catch (e) {
    console.error(e)
    const msg = e?.response?.data?.detail || '执行失败'
    summaryText.value = msg
    ElMessage.error(msg)
    opts.onError(e)
  } finally {
    uploading.value = false
    loading.value = false
  }
}
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
.mb16 { margin-bottom: 16px; }
.mb12 { margin-bottom: 12px; }
.import-row { display:flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.import-info { color: var(--text-secondary); }
</style>

