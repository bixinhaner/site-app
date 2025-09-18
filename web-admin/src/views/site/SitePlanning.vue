<template>
  <div class="page">
    <div class="page-header">
      <h1>站点规划</h1>
      <div class="header-actions">
        <el-button @click="goBack"><el-icon><Back /></el-icon>返回</el-button>
        <el-button v-if="canEdit" type="primary" :loading="saving" @click="savePlanning">
          <el-icon><Check /></el-icon>保存为新版本
        </el-button>
      </div>
    </div>

    <el-card class="mb16">
      <div class="import-row">
        <el-button @click="downloadTemplate">
          <el-icon><Download /></el-icon>下载导入模板
        </el-button>
        <template v-if="canEdit">
          <el-switch v-model="dryRun" active-text="试运行(dry run)" />
          <el-upload :show-file-list="false" :before-upload="onBeforeUpload" :http-request="onUploadRequest">
            <el-button type="success">
              <el-icon><Upload /></el-icon>{{ dryRun ? '试运行导入' : '导入并保存' }}
            </el-button>
          </el-upload>
        </template>
        <span v-if="importInfo" class="import-info">{{ importInfo }}</span>
      </div>
    </el-card>

    <el-card>
      <div class="meta-row">
        <el-tag type="info">Site ID: {{ siteId }}</el-tag>
        <el-tag v-if="baseVersion !== null" type="success">当前版本: v{{ baseVersion }}</el-tag>
      </div>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="总览" name="overview">
          <el-form label-width="120px" class="max600">
            <el-form-item label="频段(Bands)">
              <el-select v-model="model.bands" multiple filterable allow-create default-first-option placeholder="输入或选择频段" style="width:100%">
                <el-option v-for="b in bandOptions" :key="b" :label="b" :value="b" />
              </el-select>
            </el-form-item>
            <el-form-item label="扇区数量">
              <el-input-number v-model="model.sector_count" :min="0" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="model.notes" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="扇区" name="sectors">
          <div class="table-actions">
            <el-button v-if="canEdit" @click="addSector" type="primary" size="small"><el-icon><Plus /></el-icon>新增扇区</el-button>
          </div>
          <el-table :data="model.sectors" border>
            <el-table-column label="#" width="60">
              <template #default="{ $index }">{{ $index + 1 }}</template>
            </el-table-column>
            <el-table-column label="扇区编号" width="120">
              <template #default="{ row }"><el-input-number v-model="row.sector_index" :min="1" /></template>
            </el-table-column>
            <el-table-column label="方位角(°)" width="160">
              <template #default="{ row }"><el-input-number v-model="row.azimuth_deg" :min="0" :max="360" /></template>
            </el-table-column>
            <el-table-column label="下倾角(°)" width="160">
              <template #default="{ row }"><el-input-number v-model="row.downtilt_deg" :min="0" :max="30" /></template>
            </el-table-column>
            <el-table-column label="频段" min-width="220">
              <template #default="{ row }">
                <el-select v-model="row.bands" multiple filterable allow-create default-first-option style="width:100%">
                  <el-option v-for="b in bandOptions" :key="b" :label="b" :value="b" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column v-if="canEdit" label="操作" width="100">
              <template #default="{ $index }">
                <el-button link type="danger" @click="removeSector($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="天线端口" name="antenna">
          <div class="table-actions">
            <el-button v-if="canEdit" @click="addAntenna" type="primary" size="small"><el-icon><Plus /></el-icon>新增端口</el-button>
          </div>
          <el-table :data="model.antenna_ports" border>
            <el-table-column label="#" width="60"><template #default="{ $index }">{{ $index + 1 }}</template></el-table-column>
            <el-table-column label="端口标识" width="160"><template #default="{ row }"><el-input v-model="row.port_label" /></template></el-table-column>
            <el-table-column label="扇区编号" width="120"><template #default="{ row }"><el-input-number v-model="row.sector_index" :min="1" /></template></el-table-column>
            <el-table-column label="频段" width="140"><template #default="{ row }"><el-input v-model="row.band" /></template></el-table-column>
            <el-table-column label="MIMO链路" width="140"><template #default="{ row }"><el-input v-model="row.mimo_chain" /></template></el-table-column>
            <el-table-column label="备注" min-width="220"><template #default="{ row }"><el-input v-model="row.remarks" /></template></el-table-column>
            <el-table-column v-if="canEdit" label="操作" width="100"><template #default="{ $index }"><el-button link type="danger" @click="removeAntenna($index)">删除</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="交换机端口" name="switch">
          <div class="table-actions">
            <el-button v-if="canEdit" @click="addSwitchPort" type="primary" size="small"><el-icon><Plus /></el-icon>新增端口</el-button>
          </div>
          <el-table :data="model.switch_ports" border>
            <el-table-column label="#" width="60"><template #default="{ $index }">{{ $index + 1 }}</template></el-table-column>
            <el-table-column label="端口号" width="140"><template #default="{ row }"><el-input v-model="row.port_no" /></template></el-table-column>
            <el-table-column label="VLANs" width="200">
              <template #default="{ row }">
                <el-input v-model="row.vlan_text" placeholder="逗号分隔，如 201,202" @change="syncVlans(row)" />
              </template>
            </el-table-column>
            <el-table-column label="Uplink" width="100"><template #default="{ row }"><el-switch v-model="row.is_uplink" /></template></el-table-column>
            <el-table-column label="PoE" width="100"><template #default="{ row }"><el-switch v-model="row.poe" /></template></el-table-column>
            <el-table-column label="说明" min-width="220"><template #default="{ row }"><el-input v-model="row.description" /></template></el-table-column>
            <el-table-column v-if="canEdit" label="操作" width="100"><template #default="{ $index }"><el-button link type="danger" @click="removeSwitchPort($index)">删除</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="版本" name="versions">
          <el-table :data="versions" v-loading="versionsLoading" border>
            <el-table-column prop="version" label="版本" width="100" />
            <el-table-column label="当前" width="100"><template #default="{ row }"><el-tag :type="row.is_current ? 'success' : 'info'">{{ row.is_current ? '是' : '否' }}</el-tag></template></el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="200" />
            <el-table-column prop="created_by" label="创建人" width="120" />
            <el-table-column label="备注" min-width="200"><template #default="{ row }">{{ row.notes || '-' }}</template></el-table-column>
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-button v-if="canEdit" link type="primary" size="small" @click="restore(row)">回滚到此版本</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="日志" name="logs">
          <el-table :data="logs" v-loading="logsLoading" border>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="operation" label="操作" width="120" />
            <el-table-column prop="actor_id" label="操作者" width="120" />
            <el-table-column prop="created_at" label="时间" width="200" />
            <el-table-column label="变更字段" min-width="260">
              <template #default="{ row }">
                <el-tag v-for="f in (row.diff?.changed_fields || [])" :key="f" type="info" class="mr8">{{ f }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import sitePlanningApi from '../../api/sitePlanning'
import { useUserStore } from '../../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const siteId = Number(route.params.id)
const activeTab = ref('overview')
const saving = ref(false)
const versionsLoading = ref(false)
const logsLoading = ref(false)
const dryRun = ref(true)
const importInfo = ref('')
const baseVersion = ref(null)

const downloadTemplate = async () => {
  try {
    const res = await sitePlanningApi.downloadTemplate()
    const blob = new Blob([res])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'site_planning_template.xlsx'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载模板失败')
  }
}
const bandOptions = ['n41', 'n78', 'n1', 'n3', 'B1', 'B3']
const canEdit = computed(() => ['admin', 'manager', 'planner'].includes(userStore.user?.role))

const model = reactive({
  bands: [],
  sector_count: 0,
  notes: '',
  sectors: [],
  antenna_ports: [],
  switch_ports: [],
})

const versions = ref([])
const logs = ref([])

const loadCurrent = async () => {
  try {
    const res = await sitePlanningApi.getCurrent(siteId)
    baseVersion.value = res.version
    model.bands = res.bands || []
    model.sector_count = res.sector_count || 0
    model.notes = res.notes || ''
    model.sectors = (res.sectors || []).map(s => ({ ...s }))
    model.antenna_ports = (res.antenna_ports || []).map(a => ({ ...a }))
    model.switch_ports = (res.switch_ports || []).map(sp => ({ ...sp, vlan_text: (sp.vlan_ids || []).join(',') }))
  } catch (e) {
    // 404: 尚无规划，保持空白
    baseVersion.value = 0
  }
}

const loadVersions = async () => {
  try {
    versionsLoading.value = true
    versions.value = await sitePlanningApi.listVersions(siteId)
  } catch (e) {
    // ignore
  } finally {
    versionsLoading.value = false
  }
}

const loadLogs = async () => {
  try {
    logsLoading.value = true
    logs.value = await sitePlanningApi.listLogs(siteId, { limit: 100 })
  } catch (e) {
    // ignore
  } finally {
    logsLoading.value = false
  }
}

const goBack = () => router.back()

const addSector = () => {
  const nextIdx = (model.sectors?.length || 0) + 1
  model.sectors.push({ sector_index: nextIdx, azimuth_deg: 0, downtilt_deg: 5, bands: [] })
}
const removeSector = (i) => model.sectors.splice(i, 1)

const addAntenna = () => model.antenna_ports.push({ port_label: '', sector_index: 1, band: '', mimo_chain: '', remarks: '' })
const removeAntenna = (i) => model.antenna_ports.splice(i, 1)

const addSwitchPort = () => model.switch_ports.push({ port_no: '', vlan_ids: [], vlan_text: '', is_uplink: false, poe: false, description: '' })
const removeSwitchPort = (i) => model.switch_ports.splice(i, 1)
const syncVlans = (row) => {
  const parts = (row.vlan_text || '').split(',').map(s => s.trim()).filter(Boolean)
  const ints = []
  const seen = new Set()
  for (const p of parts) {
    const n = Number(p)
    if (Number.isInteger(n) && n >= 1 && n <= 4094 && !seen.has(n)) {
      seen.add(n)
      ints.push(n)
    }
  }
  row.vlan_ids = ints
}

const savePlanning = async () => {
  try {
    saving.value = true
    const payload = {
      bands: model.bands,
      sector_count: model.sector_count,
      notes: model.notes,
      sectors: model.sectors.map(s => ({ ...s })),
      antenna_ports: model.antenna_ports.map(a => ({ ...a })),
      switch_ports: model.switch_ports.map(sp => ({ port_no: sp.port_no, vlan_ids: sp.vlan_ids || [], is_uplink: !!sp.is_uplink, poe: !!sp.poe, description: sp.description || '' })),
      base_version: baseVersion.value,
    }
    await sitePlanningApi.putPlanning(siteId, payload)
    ElMessage.success('保存成功，已生成新版本')
    await loadCurrent()
    await loadVersions()
    await loadLogs()
  } catch (e) {
    const msg = e?.response?.data?.detail || '保存失败'
    if (e?.response?.status === 409) {
      ElMessageBox.alert(msg, '版本冲突', { type: 'warning' })
    } else {
      ElMessage.error(msg)
    }
  } finally {
    saving.value = false
  }
}

const restore = async (row) => {
  try {
    await ElMessageBox.confirm(`确认回滚到版本 v${row.version} 吗？`, '提示', { type: 'warning' })
    await sitePlanningApi.restoreVersion(siteId, row.version)
    ElMessage.success('回滚成功')
    await loadCurrent()
    await loadVersions()
    await loadLogs()
  } catch (e) {
    // canceled or error
  }
}

const onBeforeUpload = () => true
const onUploadRequest = async (opts) => {
  try {
    importInfo.value = '正在解析...'
    const res = await sitePlanningApi.importPlanning(siteId, opts.file, dryRun.value)
    if (dryRun.value) {
      importInfo.value = res.success ? '试运行成功：已解析，可点击“导入并保存”执行真正导入。' : `试运行失败：${(res.errors || []).join('; ')}`
    } else {
      importInfo.value = '导入成功，已生成新版本'
      await loadCurrent()
      await loadVersions()
      await loadLogs()
    }
    opts.onSuccess(res)
  } catch (e) {
    const msg = e?.response?.data?.detail || '导入失败'
    importInfo.value = msg
    opts.onError(e)
  }
}

onMounted(async () => {
  await loadCurrent()
  await loadVersions()
  await loadLogs()
})
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
.mb16 { margin-bottom: 16px; }
.import-row { display:flex; align-items:center; gap: 12px; }
.import-info { color: #666; }
.meta-row { display:flex; gap: 12px; margin-bottom: 8px; }
.table-actions { margin-bottom: 8px; }
.mr8 { margin-right: 8px; }
.max600 { max-width: 600px; }
</style>
