<template>
  <div class="page">
    <div class="page-header">
      <h1>规划信息导入（LLD新）</h1>
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
        <el-table-column prop="site_code" label="TOWER ID / SiteCode" width="220" />
        <el-table-column prop="site_id" label="站点ID" width="100" />
        <el-table-column label="结果" width="100">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version_created" label="新版本" width="120" />
        <el-table-column prop="bands" label="Bands" min-width="160">
          <template #default="{ row }">
            <span v-if="row.bands && row.bands.length">{{ row.bands.join(', ') }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="4G/5G Cells" width="160">
          <template #default="{ row }">
            <span>4G: {{ row.lte_cell_count || 0 }}, 5G: {{ row.nr_cell_count || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提示" min-width="220">
          <template #default="{ row }">
            <div v-if="row.warnings && row.warnings.length">
              <div v-for="(w, i) in row.warnings" :key="i">• {{ w }}</div>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="错误" min-width="280">
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
import sitePlanningApi from '../../api/sitePlanning'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const dryRun = ref(true)
const importInfo = ref('')
const results = ref([])

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
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
.mb16 { margin-bottom: 16px; }
.import-row { display:flex; align-items:center; gap: 12px; }
.import-info { color: #666; }
</style>

