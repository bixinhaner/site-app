<template>
  <div class="page">
    <div class="page-header">
      <h1>勘察档案</h1>
      <div class="header-actions">
        <el-button type="success" @click="createNew" v-if="isAdmin">
          <el-icon><Plus /></el-icon>
          新建勘察
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-input v-model="keyword" placeholder="搜索站点/勘察人/结论" clearable style="width: 260px" @keyup.enter="reload" />
      <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 320px" @change="reload" />
      <el-select v-model="feasibility" placeholder="结论" clearable style="width: 180px" @change="reload">
        <el-option label="可行" value="feasible" />
        <el-option label="有条件可行" value="conditionally_feasible" />
        <el-option label="不可行" value="infeasible" />
      </el-select>
      <el-button type="primary" @click="reload">
        <el-icon><Search /></el-icon>
        筛选
      </el-button>
      <el-dropdown>
        <el-button>
          工具
          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="downloadTemplate">下载导入模板</el-dropdown-item>
            <el-dropdown-item @click="openImport" v-if="isAdmin">批量导入Excel</el-dropdown-item>
            <el-dropdown-item divided @click="exportCurrent">按筛选导出Zip</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <el-card>
      <el-table :data="items" v-loading="loading" stripe @sort-change="onSortChange">
        <el-table-column prop="site_code" label="站点编码" width="140" />
        <el-table-column prop="site_name" label="站点名称" min-width="180" sortable="custom" />
        <el-table-column prop="surveyor_name" label="勘察人" width="140" />
        <el-table-column prop="survey_date" label="勘察日期" width="180" sortable="custom">
          <template #default="{ row }">{{ formatDate(row.survey_date) }}</template>
        </el-table-column>
        <el-table-column prop="feasibility" label="结论" width="150">
          <template #default="{ row }">
            <el-tag :type="tagType(row.feasibility)">{{ label(row.feasibility) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row)">
              <el-icon><View /></el-icon>
              查看
            </el-button>
            <el-button link type="success" size="small" @click="editSurvey(row)" v-if="isAdmin">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button link type="danger" size="small" @click="remove(row)" v-if="isAdmin">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          :current-page="page"
          :page-size="pageSize"
          :page-sizes="[10,20,50,100]"
          @current-change="p => { page = p; reload() }"
          @size-change="s => { pageSize = s; page = 1; reload() }"
        />
      </div>
    </el-card>

    <el-dialog v-model="importVisible" title="批量导入勘察" width="560px">
      <el-upload
        ref="uploader"
        drag
        :show-file-list="false"
        :http-request="doImport"
        accept=".xlsx,.xls"
        style="width:100%"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或 <em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">仅支持 Excel；建议先下载模板。</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="importVisible = false">关闭</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="importResultVisible" title="导入结果" width="720px">
      <div class="import-summary">成功: {{ importResult?.success || 0 }}，失败: {{ importResult?.failed || 0 }}</div>
      <el-table :data="importResult?.errors || []" height="360">
        <el-table-column prop="row_index" label="行号" width="80" />
        <el-table-column prop="error" label="原因" min-width="200" />
        <el-table-column label="原始数据" min-width="320">
          <template #default="{ row }">
            <div class="row-json">{{ formatRow(row.row_values) }}</div>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button type="primary" @click="importResultVisible = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { siteSurveysApi } from '@/api/siteSurveys'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const sortBy = ref('created_at')
const sortDir = ref('desc')
const keyword = ref('')
const feasibility = ref('')
const dateRange = ref(null)
const importVisible = ref(false)
const importResultVisible = ref(false)
const importResult = ref(null)

const routeSiteId = ref(null)
const reload = async () => {
  try {
    loading.value = true
    const params = { page: page.value, page_size: pageSize.value, keyword: keyword.value || undefined, sort_by: sortBy.value, sort_dir: sortDir.value }
    if (feasibility.value) params.feasibility = feasibility.value
    if (routeSiteId.value) params.site_id = routeSiteId.value
    if (dateRange.value && dateRange.value.length === 2) {
      params.date_from = new Date(dateRange.value[0]).toISOString()
      params.date_to = new Date(dateRange.value[1]).toISOString()
    }
    const res = await siteSurveysApi.page(params)
    items.value = Array.isArray(res?.items) ? res.items : []
    total.value = Number(res?.total || 0)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const onSortChange = (e) => {
  if (e.prop === 'survey_date') sortBy.value = 'survey_date'
  else if (e.prop === 'site_name') sortBy.value = 'site_code'
  else sortBy.value = 'created_at'
  sortDir.value = e.order === 'ascending' ? 'asc' : 'desc'
  page.value = 1
  reload()
}

const createNew = () => {
  const query = routeSiteId.value ? { site_id: routeSiteId.value } : undefined
  router.push({ name: 'SiteSurveyNew', query })
}
const viewDetail = (row) => router.push({ name: 'SiteSurveyDetail', params: { id: row.id } })
const editSurvey = (row) => router.push({ name: 'SiteSurveyDetail', params: { id: row.id }, query: { edit: '1' } })

const remove = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除勘察记录：${row.site_name} / ${row.surveyor_name}？`, '提示', { type: 'warning' })
    await siteSurveysApi.remove(row.id)
    ElMessage.success('删除成功')
    reload()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
      ElMessage.error('删除失败')
    }
  }
}

const downloadTemplate = async () => {
  try {
    const blob = await siteSurveysApi.downloadImportTemplate()
    const url = window.URL.createObjectURL(new Blob([blob]))
    const a = document.createElement('a')
    a.href = url
    a.download = 'site_survey_import_template.xlsx'
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error(e)
    ElMessage.error('下载失败')
  }
}

const openImport = () => { importVisible.value = true }
const doImport = async (opt) => {
  try {
    const fd = new FormData()
    fd.append('file', opt.file)
    const res = await siteSurveysApi.importExcel(fd)
    importResult.value = res
    importResultVisible.value = true
    importVisible.value = false
    reload()
  } catch (e) {
    console.error(e)
    ElMessage.error('导入失败')
  }
}

const exportCurrent = async () => {
  try {
    const params = { keyword: keyword.value || undefined, sort_by: sortBy.value, sort_dir: sortDir.value }
    if (feasibility.value) params.feasibility = feasibility.value
    if (routeSiteId.value) params.site_id = routeSiteId.value
    if (dateRange.value && dateRange.value.length === 2) {
      params.date_from = new Date(dateRange.value[0]).toISOString()
      params.date_to = new Date(dateRange.value[1]).toISOString()
    }
    params.include_photos = true
    const blob = await siteSurveysApi.exportBatch(params)
    const url = window.URL.createObjectURL(new Blob([blob]))
    const a = document.createElement('a')
    a.href = url
    a.download = 'site_surveys_batch.zip'
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error(e)
    if (e?.response?.status === 404) {
      ElMessage.warning('没有匹配的勘察记录，无法导出')
    } else {
      ElMessage.error('导出失败')
    }
  }
}

const label = (v) => ({
  feasible: '可行',
  conditionally_feasible: '有条件可行',
  infeasible: '不可行'
}[v] || v)

const tagType = (v) => ({
  feasible: 'success',
  conditionally_feasible: 'warning',
  infeasible: 'danger'
}[v] || 'info')

const formatDate = (iso) => iso ? new Date(iso).toLocaleString() : '-'
const formatRow = (obj) => { try { return JSON.stringify(obj || {}, null, 0) } catch { return '-' } }

import { useRoute } from 'vue-router'
const route = useRoute()
onMounted(() => {
  if (route.query.site_id) routeSiteId.value = Number(route.query.site_id)
  reload()
})

const userStore = useUserStore()
const isAdmin = userStore.isAdmin
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:flex-end; margin-bottom: 12px; }
.page-header h1 { white-space: nowrap; line-height: 24px; margin: 0; }
.header-actions { display:flex; gap: 12px; }
.filter-bar { display:flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 16px; }
.pager { display:flex; justify-content: flex-end; padding: 12px 0 4px; }
.row-json { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; color: #666; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
