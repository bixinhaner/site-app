<template>
  <div class="page">
    <div class="page-header">
      <h1>站点信息维护</h1>
      <div class="header-actions">
        <el-button @click="goBack"><el-icon><Back /></el-icon>返回</el-button>
        <el-button v-if="canAnyBatch" type="info" @click="gotoHistory"><el-icon><Document /></el-icon>导入历史</el-button>
      </div>
    </div>

    <el-card class="mb16">
      <el-tabs v-model="mode" type="card">
        <el-tab-pane v-if="canCreate" label="单个信息" name="single">
          <div class="form-grid">
            <el-form :model="form" :rules="rules" ref="formRef" label-width="110px" status-icon>
              <el-form-item label="站点编码" prop="site_code">
                <el-input v-model="form.site_code" placeholder="必填，唯一" />
              </el-form-item>
              <el-form-item label="站点名称" prop="site_name">
                <el-input v-model="form.site_name" placeholder="必填" />
              </el-form-item>
              <el-form-item label="类型">
                <el-input v-model="form.site_type" placeholder="macro/indoor..." />
              </el-form-item>
              <el-form-item label="省市区">
                <div class="row3">
                  <el-input v-model="form.province" placeholder="省" />
                  <el-input v-model="form.city" placeholder="市" />
                  <el-input v-model="form.district" placeholder="区/县" />
                </div>
              </el-form-item>
              <el-form-item label="地址">
                <el-input v-model="form.address" placeholder="详细地址" />
              </el-form-item>
              <el-form-item label="经纬度">
                <div class="row2">
                  <el-input v-model.number="form.latitude" placeholder="纬度 -90~90" />
                  <el-input v-model.number="form.longitude" placeholder="经度 -180~180" />
                </div>
              </el-form-item>
              <el-form-item label="优先级">
                <el-select v-model="form.priority" placeholder="优先级">
                  <el-option label="high" value="high" />
                  <el-option label="normal" value="normal" />
                  <el-option label="low" value="low" />
                </el-select>
              </el-form-item>
              <el-form-item label="联系人">
                <div class="row2">
                  <el-input v-model="form.contact_person" placeholder="姓名" />
                  <el-input v-model="form.contact_phone" placeholder="电话" />
                </div>
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="form.description" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="saving" @click="saveSingle">保存</el-button>
                <el-button @click="resetForm">重置</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>
        <el-tab-pane v-if="canCreate" label="批量导入（新建）" name="batchImport">
          <div class="import-row">
            <el-button @click="downloadTemplate"><el-icon><Download /></el-icon>下载模板</el-button>
            <template v-if="canCreate">
              <el-switch v-model="dryRunImport" active-text="试运行(dry run)" />
              <el-upload :show-file-list="false" :before-upload="() => true" :http-request="onImportUpload">
                <el-button type="success"><el-icon><Upload /></el-icon>{{ dryRunImport ? '试运行导入' : '导入并创建' }}</el-button>
              </el-upload>
            </template>
            <span v-if="summaryText" class="import-info">{{ summaryText }}</span>
            <el-tag v-if="batchId" type="info">批次ID: {{ batchId }}</el-tag>
          </div>
          <div class="tips">
            说明：该模式用于“新增站点”，若编码已存在会报错，不会覆盖原数据。
          </div>
        </el-tab-pane>

        <el-tab-pane v-if="canUpdate" label="批量更新（Excel回写）" name="batchUpdate">
          <div class="import-row">
            <el-button @click="goSiteListExport"><el-icon><View /></el-icon>去站点列表导出数据</el-button>
            <el-button @click="downloadUpdateTemplate"><el-icon><Download /></el-icon>下载更新模板</el-button>
            <el-switch v-model="dryRunUpdate" active-text="试运行(dry run)" />
            <el-upload :show-file-list="false" :before-upload="() => true" :http-request="onUpdateUpload">
              <el-button type="warning"><el-icon><Upload /></el-icon>{{ dryRunUpdate ? '试运行更新' : '执行更新' }}</el-button>
            </el-upload>
            <span v-if="summaryText" class="import-info">{{ summaryText }}</span>
            <el-tag v-if="batchId" type="info">批次ID: {{ batchId }}</el-tag>
          </div>
          <div class="tips">
            {{ t('siteBasicBatch.batchUpdate.contractAmountTip') }}
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-card>
      <el-table :data="results" border v-loading="loading">
        <el-table-column prop="row_index" label="行号" width="90" />
        <el-table-column prop="site_code" label="站点编码" width="180" />
        <el-table-column label="结果" width="120">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="action" label="动作" width="120" />
        <el-table-column prop="site_id" label="站点ID" width="120" />
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
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import siteBasicApi from '../../api/siteBasic'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const userStore = useUserStore()
const loading = ref(false)
const saving = ref(false)
const canCreate = computed(() => userStore.hasPermission('sites:create:write'))
const canUpdate = computed(() => userStore.hasPermission('sites:update:write'))
const canAnyBatch = computed(() => canCreate.value || canUpdate.value)
const mode = ref(canCreate.value ? 'single' : (canUpdate.value ? 'batchUpdate' : 'single'))
const dryRunImport = ref(true)
const dryRunUpdate = ref(true)
const results = ref([])
const batchId = ref('')
const summaryText = ref('')

const goBack = () => router.back()
const gotoHistory = () => router.push({ name: 'SiteBasicImportHistory' })
const goSiteListExport = () => router.push({ name: 'SiteList' })

const applyModeFromQuery = () => {
  const availableModes = []
  if (canCreate.value) {
    availableModes.push('single')
    availableModes.push('batchImport')
  }
  if (canUpdate.value) {
    availableModes.push('batchUpdate')
  }
  const queryMode = String(route.query.mode || '').trim()
  if (queryMode && availableModes.includes(queryMode)) {
    mode.value = queryMode
    return
  }
  if (!availableModes.includes(mode.value)) {
    mode.value = availableModes[0] || 'single'
  }
}

const downloadTemplate = async () => {
  try {
    const res = await siteBasicApi.downloadTemplate()
    const blob = new Blob([res])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'site_basic_template.xlsx'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载模板失败')
  }
}

const downloadUpdateTemplate = async () => {
  try {
    const res = await siteBasicApi.downloadUpdateTemplate()
    const blob = new Blob([res])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'site_basic_update_template.xlsx'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载更新模板失败')
  }
}

const applyUploadResult = (res) => {
  results.value = res.results || []
  batchId.value = res.batch_id || ''
  summaryText.value = `共 ${res.total_rows} 行，成功 ${res.success_count} 行，失败 ${res.failed_count} 行`
}

const onImportUpload = async (opts) => {
  try {
    loading.value = true
    summaryText.value = '正在解析...'
    batchId.value = ''
    const res = await siteBasicApi.batchUpload(opts.file, dryRunImport.value)
    applyUploadResult(res)
    opts.onSuccess(res)
  } catch (e) {
    const msg = e?.response?.data?.detail || '导入失败'
    summaryText.value = msg
    opts.onError(e)
  } finally {
    loading.value = false
  }
}

const onUpdateUpload = async (opts) => {
  try {
    loading.value = true
    summaryText.value = '正在解析...'
    batchId.value = ''
    const res = await siteBasicApi.batchUpdateUpload(opts.file, dryRunUpdate.value)
    applyUploadResult(res)
    opts.onSuccess(res)
  } catch (e) {
    const msg = e?.response?.data?.detail || '更新失败'
    summaryText.value = msg
    opts.onError(e)
  } finally {
    loading.value = false
  }
}

// ===== 单条录入 =====
const formRef = ref()
const form = reactive({
  site_code: '',
  site_name: '',
  site_type: '',
  province: '',
  city: '',
  district: '',
  address: '',
  latitude: undefined,
  longitude: undefined,
  priority: 'normal',
  contact_person: '',
  contact_phone: '',
  description: '',
})
const rules = {
  site_code: [{ required: true, message: '必填', trigger: 'blur' }],
  site_name: [{ required: true, message: '必填', trigger: 'blur' }],
}
const resetForm = () => {
  Object.assign(form, {
    site_code: '', site_name: '', site_type: '', province: '', city: '', district: '', address: '',
    latitude: undefined, longitude: undefined, priority: 'normal', contact_person: '', contact_phone: '', description: ''
  })
}
const saveSingle = async () => {
  if (!canCreate.value) {
    ElMessage.warning('无权限')
    return
  }
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = { ...form }
    // 清理空字符串为 undefined，避免后端存空串
    Object.keys(payload).forEach(k => { if (payload[k] === '') payload[k] = undefined })
    await siteBasicApi.createSite(payload)
    ElMessage.success('创建成功')
    resetForm()
  } catch (e) {
    if (e?.response?.data?.detail) ElMessage.error(e.response.data.detail)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  applyModeFromQuery()
})
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
.mb16 { margin-bottom: 16px; }
.import-row { display:flex; align-items:center; gap: 12px; }
.import-info { color: #666; }
.tips { margin-top: 10px; color: #666; }
.form-grid { max-width: 760px; }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; width: 100%; }
.row3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; width: 100%; }
</style>
