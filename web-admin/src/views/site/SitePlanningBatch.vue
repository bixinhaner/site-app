<template>
  <div class="page">
    <div class="page-header">
      <h1>规划信息导入</h1>
      <div class="header-actions">
        <el-button @click="goBack"><el-icon><Back /></el-icon>返回</el-button>
      </div>
    </div>

    <el-card class="mb16">
      <el-tabs v-model="mode" type="card">
        <el-tab-pane label="单个信息" name="single">
          <div class="form-grid">
            <el-form :model="pForm" ref="pFormRef" label-width="120px">
              <el-form-item label="选择站点" required>
                <el-select v-model="pForm.site_id" filterable remote reserve-keyword :remote-method="searchSites" :loading="siteLoading" placeholder="输入站点编码/名称搜索" style="width: 420px">
                  <el-option v-for="s in siteOptions" :key="s.id" :label="`${s.site_code} / ${s.site_name}`" :value="s.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="频段(Bands)">
                <el-input v-model="pForm.bands_text" placeholder="逗号分隔，如 n41,n78" />
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="pForm.notes" type="textarea" :rows="2" />
              </el-form-item>

              <el-divider>扇区设置</el-divider>
              <div class="row-actions">
                <el-button size="small" @click="quick3Sectors">快速生成3扇区(0/120/240)</el-button>
                <el-button size="small" @click="addSector">新增扇区</el-button>
              </div>
              <el-table :data="pForm.sectors" border size="small" class="mb8">
                <el-table-column label="#" width="60">
                  <template #default="{ $index }">{{ $index + 1 }}</template>
                </el-table-column>
                <el-table-column label="扇区号" width="120">
                  <template #default="{ row }"><el-input v-model.number="row.sector_index" /></template>
                </el-table-column>
                <el-table-column label="方位角" width="120">
                  <template #default="{ row }"><el-input v-model.number="row.azimuth_deg" /></template>
                </el-table-column>
                <el-table-column label="下倾角" width="120">
                  <template #default="{ row }"><el-input v-model.number="row.downtilt_deg" /></template>
                </el-table-column>
                <el-table-column label="频段(逗号)" min-width="200">
                  <template #default="{ row }"><el-input v-model="row.bands_text" placeholder="如 n41" /></template>
                </el-table-column>
                <el-table-column label="操作" width="100">
                  <template #default="{ $index }">
                    <el-button link type="danger" @click="removeSector($index)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>

              <el-divider>天线端口(可选)</el-divider>
              <div class="row-actions">
                <el-button size="small" @click="addAnt">新增端口</el-button>
              </div>
              <el-table :data="pForm.antenna_ports" border size="small" class="mb8">
                <el-table-column label="标签" width="160">
                  <template #default="{ row }"><el-input v-model="row.port_label" /></template>
                </el-table-column>
                <el-table-column label="扇区号" width="120">
                  <template #default="{ row }"><el-input v-model.number="row.sector_index" /></template>
                </el-table-column>
                <el-table-column label="Band" width="140">
                  <template #default="{ row }"><el-input v-model="row.band" /></template>
                </el-table-column>
                <el-table-column label="MIMO" width="140">
                  <template #default="{ row }"><el-input v-model="row.mimo_chain" /></template>
                </el-table-column>
                <el-table-column label="备注" min-width="200">
                  <template #default="{ row }"><el-input v-model="row.remarks" /></template>
                </el-table-column>
                <el-table-column label="操作" width="100">
                  <template #default="{ $index }">
                    <el-button link type="danger" @click="removeAnt($index)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>

              <el-divider>交换机端口(可选)</el-divider>
              <div class="row-actions">
                <el-button size="small" @click="addSw">新增端口</el-button>
              </div>
              <el-table :data="pForm.switch_ports" border size="small" class="mb8">
                <el-table-column label="端口号" width="140">
                  <template #default="{ row }"><el-input v-model="row.port_no" /></template>
                </el-table-column>
                <el-table-column label="VLAN(逗号)" width="180">
                  <template #default="{ row }"><el-input v-model="row.vlan_text" placeholder="如 201,202" /></template>
                </el-table-column>
                <el-table-column label="Uplink" width="100">
                  <template #default="{ row }"><el-switch v-model="row.is_uplink" /></template>
                </el-table-column>
                <el-table-column label="POE" width="100">
                  <template #default="{ row }"><el-switch v-model="row.poe" /></template>
                </el-table-column>
                <el-table-column label="描述" min-width="200">
                  <template #default="{ row }"><el-input v-model="row.description" /></template>
                </el-table-column>
                <el-table-column label="操作" width="100">
                  <template #default="{ $index }">
                    <el-button link type="danger" @click="removeSw($index)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>

              <el-form-item>
                <el-button type="primary" :loading="saving" @click="submitSingle">保存为新版本</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>

        <el-tab-pane label="批量导入" name="batch">
          <div class="import-row">
            <el-button @click="downloadBatchTemplate"><el-icon><Download /></el-icon>下载批量模板</el-button>
            <template v-if="canEdit">
              <el-switch v-model="dryRun" active-text="试运行(dry run)" />
              <el-upload :show-file-list="false" :before-upload="() => true" :http-request="onUploadRequest">
                <el-button type="success"><el-icon><Upload /></el-icon>{{ dryRun ? '试运行导入' : '导入并保存' }}</el-button>
              </el-upload>
            </template>
            <span v-if="importInfo" class="import-info">{{ importInfo }}</span>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-card>
      <el-table :data="results" border v-loading="loading">
        <el-table-column prop="site_code" label="站点编码" width="180" />
        <el-table-column prop="site_id" label="站点ID" width="120" />
        <el-table-column label="结果" width="120">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version_created" label="新版本" width="120" />
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
import { ref, computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import sitePlanningApi from '../../api/sitePlanning'
import { useUserStore } from '../../stores/user'
import siteBasicApi from '../../api/siteBasic'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const dryRun = ref(true)
const importInfo = ref('')
const results = ref([])
const canEdit = computed(() => ['admin', 'manager', 'planner'].includes(userStore.user?.role))
const mode = ref('single')
const saving = ref(false)

// 站点搜索
const siteLoading = ref(false)
const siteOptions = ref([])
const searchSites = async (q) => {
  try {
    siteLoading.value = true
    const res = await siteBasicApi.listSites({ limit: 200 })
    const list = Array.isArray(res) ? res : []
    const kw = (q || '').toLowerCase()
    siteOptions.value = list.filter(s => `${s.site_code} ${s.site_name}`.toLowerCase().includes(kw))
  } finally {
    siteLoading.value = false
  }
}

// 单条规划表单
const pFormRef = ref()
const pForm = reactive({
  site_id: null,
  bands_text: '',
  notes: '',
  sectors: [],
  antenna_ports: [],
  switch_ports: [],
})

const addSector = () => { pForm.sectors.push({ sector_index: pForm.sectors.length + 1, azimuth_deg: 0, downtilt_deg: 5, bands_text: '' }) }
const removeSector = (idx) => { pForm.sectors.splice(idx, 1) }
const quick3Sectors = () => {
  pForm.sectors = [
    { sector_index: 1, azimuth_deg: 0, downtilt_deg: 5, bands_text: '' },
    { sector_index: 2, azimuth_deg: 120, downtilt_deg: 5, bands_text: '' },
    { sector_index: 3, azimuth_deg: 240, downtilt_deg: 5, bands_text: '' },
  ]
}

const addAnt = () => { pForm.antenna_ports.push({ port_label: '', sector_index: 1, band: '', mimo_chain: '', remarks: '' }) }
const removeAnt = (idx) => { pForm.antenna_ports.splice(idx, 1) }
const addSw = () => { pForm.switch_ports.push({ port_no: '', vlan_text: '', is_uplink: false, poe: false, description: '' }) }
const removeSw = (idx) => { pForm.switch_ports.splice(idx, 1) }

const submitSingle = async () => {
  if (!canEdit.value) { ElMessage.warning('无权限'); return }
  if (!pForm.site_id) { ElMessage.warning('请选择站点'); return }
  try {
    saving.value = true
    const toArr = (s) => (s || '').split(',').map(x => x.trim()).filter(Boolean)
    const sectors = pForm.sectors.map(r => ({
      sector_index: Number(r.sector_index) || 0,
      azimuth_deg: Number(r.azimuth_deg) || 0,
      downtilt_deg: Number(r.downtilt_deg) || 0,
      bands: toArr(r.bands_text),
    }))
    const vlanArr = (t) => (t || '').split(',').map(x => x.trim()).filter(x => /^\d+$/.test(x)).map(x => Number(x))
    const sws = pForm.switch_ports.map(r => ({
      port_no: r.port_no || '',
      vlan_ids: vlanArr(r.vlan_text),
      is_uplink: !!r.is_uplink,
      poe: !!r.poe,
      description: r.description || undefined,
    }))
    const ants = pForm.antenna_ports.map(r => ({
      port_label: r.port_label || '',
      sector_index: Number(r.sector_index) || 1,
      band: r.band || undefined,
      mimo_chain: r.mimo_chain || undefined,
      remarks: r.remarks || undefined,
    }))
    const payload = {
      bands: toArr(pForm.bands_text),
      sector_count: sectors.length || 0,
      notes: pForm.notes || undefined,
      sectors,
      antenna_ports: ants,
      switch_ports: sws,
    }
    await sitePlanningApi.putPlanning(pForm.site_id, payload)
    ElMessage.success('已保存为新版本')
  } catch (e) {
    const msg = e?.response?.data?.detail || '保存失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

const goBack = () => router.back()

const downloadBatchTemplate = async () => {
  try {
    const res = await sitePlanningApi.downloadBatchTemplate()
    const blob = new Blob([res])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'site_planning_batch_template.xlsx'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载模板失败')
  }
}

const onUploadRequest = async (opts) => {
  try {
    loading.value = true
    importInfo.value = '正在解析...'
    const res = await sitePlanningApi.batchImportPlanning(opts.file, dryRun.value)
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
.form-grid { max-width: 980px; }
.row-actions { display:flex; gap: 8px; margin-bottom: 8px; }
.mb8 { margin-bottom: 8px; }
</style>
