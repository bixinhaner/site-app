<template>
  <div class="page">
    <div class="page-header">
      <h1>规划信息导入（LLD）</h1>
      <div class="header-actions">
        <el-button @click="goBack"><el-icon><Back /></el-icon>返回</el-button>
      </div>
    </div>

    <el-card class="mb16">
      <div class="import-row">
        <el-button @click="downloadBatchTemplate">
          <el-icon><Download /></el-icon>下载 LLD 模板
        </el-button>
        <el-switch v-model="dryRun" active-text="试运行(dry run)" />
        <el-upload
          :show-file-list="false"
          :before-upload="onBeforeUpload"
          :http-request="onUploadRequest"
        >
          <el-button type="primary" :loading="loading" :disabled="!canEdit">
            <el-icon><Upload /></el-icon>{{ dryRun ? '试运行导入' : '导入并保存' }}
          </el-button>
        </el-upload>
        <span v-if="importInfo" class="import-info">{{ importInfo }}</span>
      </div>
    </el-card>

    <el-card>
      <el-table :data="results" border size="small">
        <el-table-column prop="site_code" label="SiteCode" width="160" />
        <el-table-column prop="site_id" label="站点ID" width="80" />
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version_created" label="新版本" width="90" />
        <el-table-column prop="bands" label="Bands" min-width="120">
          <template #default="{ row }">
            <span v-if="row.bands && row.bands.length">{{ row.bands.join(', ') }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="4G/5G Cells" width="140">
          <template #default="{ row }">
            <span>4G: {{ row.lte_cell_count || 0 }}, 5G: {{ row.nr_cell_count || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="变更详情" min-width="220">
          <template #default="{ row }">
            <template v-if="row.success">
              <!-- dry run 且有预览 diff：预览变更 -->
              <template v-if="lastDryRun && row.preview_diff">
                <el-tag type="warning" class="mr8">preview</el-tag>
                <el-button link size="small" @click="openDetail(row)">变更详情</el-button>
              </template>
              <!-- 非 dry run 且有站点ID：已保存的变更 -->
              <template v-else-if="!lastDryRun && row.site_id">
                <el-tag type="success" class="mr8">changed</el-tag>
                <el-button link size="small" @click="openDetail(row)">变更详情</el-button>
              </template>
              <!-- 成功但无任何变更 -->
              <template v-else>
                <el-tag type="info" class="mr8">no change</el-tag>
              </template>
            </template>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="错误" min-width="220">
          <template #default="{ row }">
            <div v-if="row.errors && row.errors.length">
              <div v-for="(e, i) in row.errors" :key="i">- {{ e }}</div>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 批量导入站点的规划变更详情 -->
    <el-dialog
      v-model="detailVisible"
      title="规划变更详情"
      width="760px"
    >
      <div v-if="detailLog">
        <el-descriptions :column="2" border size="small" class="mb16">
          <el-descriptions-item label="站点ID">{{ detailSite?.site_id }}</el-descriptions-item>
          <el-descriptions-item label="SiteCode">
            {{ detailSite?.site_code || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="操作">{{ detailLog.operation }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ detailLog.created_at }}</el-descriptions-item>
          <el-descriptions-item label="操作者">
            {{ detailLog.actor_name || detailLog.actor_id || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="摘要">
            {{ detailLog.summary || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="mb16">
          <div class="section-title">变更字段</div>
          <div>
            <el-tag
              v-for="f in (detailLog.diff?.changed_fields || [])"
              :key="f"
              type="info"
              class="mr8"
            >
              {{ f }}
            </el-tag>
            <span v-if="!(detailLog.diff?.changed_fields || []).length" class="muted">
              无结构化变更字段
            </span>
          </div>
        </div>

        <div>
          <div class="section-title">Cell 级变更</div>
          <div v-if="Array.isArray(detailLog.diff?.cell_changes) && detailLog.diff.cell_changes.length">
            <el-timeline>
              <el-timeline-item
                v-for="(chg, idx) in detailLog.diff.cell_changes"
                :key="idx"
              >
                <div class="cell-change-header">
                  <span class="mono">
                    {{ chg.key?.rat || '-' }} / {{ chg.key?.band_code || '-' }} / LCID={{ chg.key?.local_cell_id ?? '-' }}
                  </span>
                  <el-tag
                    size="small"
                    :type="chg.change_type === 'created' ? 'success' : chg.change_type === 'deleted' ? 'danger' : 'warning'"
                  >
                    {{ chg.change_type || 'updated' }}
                  </el-tag>
                </div>
                <ul class="change-list">
                  <li v-for="(f, i) in (chg.changes || [])" :key="i">
                    <span class="field-name">{{ f.field }}</span>
                    ：<span class="old-val">{{ f.old ?? '∅' }}</span>
                    →
                    <span class="new-val">{{ f.new ?? '∅' }}</span>
                  </li>
                </ul>
              </el-timeline-item>
            </el-timeline>
          </div>
          <div v-else class="muted">
            本次变更未记录 Cell 级差异（可能为早期导入或仅概要变更）。
          </div>
        </div>
      </div>
      <div v-else class="muted">
        未找到该站点的规划变更日志。
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import sitePlanningApi from '../../api/sitePlanning'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const dryRun = ref(true)
const importInfo = ref('')
const results = ref([])
// 记录最近一次导入是否为 dry run，用于决定“变更详情”的展示逻辑
const lastDryRun = ref(true)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailSite = ref(null)
const detailLog = ref(null)

const canEdit = computed(() => ['admin', 'manager', 'planner'].includes(userStore.user?.role))

const goBack = () => router.back()

const onBeforeUpload = () => {
  if (!canEdit.value) {
    ElMessage.warning('无权限执行导入')
    return false
  }
  return true
}

const downloadBatchTemplate = async () => {
  try {
    const res = await sitePlanningApi.downloadLldBatchTemplate()
    const blob = new Blob([res])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'site_planning_lld_template.xlsx'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载 LLD 模板失败')
  }
}

const onUploadRequest = async (opts) => {
  try {
    loading.value = true
    importInfo.value = '正在解析 LLD 文件...'
    const res = await sitePlanningApi.lldBatchImportPlanning(opts.file, dryRun.value)
    lastDryRun.value = !!res.dry_run
    results.value = res.results || []
    importInfo.value = `共 ${res.total_sites} 个站点，成功 ${res.success_count} 个，失败 ${res.failed_count} 个`
    opts.onSuccess(res)
  } catch (e) {
    const msg = e?.response?.data?.detail || '导入失败'
    importInfo.value = msg
    opts.onError(e)
  } finally {
    loading.value = false
  }
}

const openDetail = async (row) => {
  detailSite.value = row
  detailVisible.value = true
  detailLoading.value = true
  detailLog.value = null

  // 如果是最近一次 dry run 且后端返回了 preview_diff，则直接在前端基于预览展示，不请求日志接口
  if (lastDryRun.value && row.preview_diff) {
    detailLog.value = {
      operation: 'lld_import_preview',
      actor_id: null,
      actor_name: null,
      summary: 'LLD 试运行预览',
      created_at: new Date().toISOString(),
      diff: row.preview_diff,
    }
    detailLoading.value = false
    return
  }

  // 非 dry run 或没有预览数据时，回退到查询后端日志（最新一条）
  if (!row.site_id) {
    ElMessage.warning('该行未关联到站点ID，无法查询变更详情')
    detailLoading.value = false
    return
  }

  try {
    const logs = await sitePlanningApi.listLogs(row.site_id, { limit: 1 })
    if (Array.isArray(logs) && logs.length) {
      detailLog.value = logs[0]
    } else {
      detailLog.value = null
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('加载变更详情失败')
    detailLog.value = null
  } finally {
    detailLoading.value = false
  }
}
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
.mb16 { margin-bottom: 16px; }
.import-row { display:flex; align-items:center; gap: 12px; }
.import-info { color: #666; }
.muted { color: #999; font-size: 12px; }
.section-title { font-weight: 600; margin-bottom: 4px; }
.mr8 { margin-right: 8px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.cell-change-header { display:flex; align-items:center; gap: 8px; margin-bottom: 4px; }
.change-list { margin: 0; padding-left: 18px; }
.change-list li { line-height: 1.6; }
.field-name { font-weight: 500; }
.old-val { color: #999; }
.new-val { color: #409EFF; }
</style>
