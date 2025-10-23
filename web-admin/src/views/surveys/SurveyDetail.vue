<template>
  <div class="page">
    <div class="page-header">
      <h1>勘察详情</h1>
      <div class="header-actions">
        <el-button @click="goBack"><el-icon><Back /></el-icon>返回</el-button>
        <el-button type="primary" @click="toggleEdit" v-if="!editing && isAdmin"><el-icon><Edit /></el-icon>编辑</el-button>
        <el-button type="primary" :loading="saving" @click="save" v-else-if="isAdmin"><el-icon><Check /></el-icon>保存</el-button>
        <el-dropdown>
          <el-button>
            导出
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="exportZip"><el-icon><Download /></el-icon>导出Zip</el-dropdown-item>
              <el-dropdown-item @click="exportPdf"><el-icon><Document /></el-icon>导出PDF</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

  <el-row :gutter="16">
    <el-col :span="10">
      <el-card>
          <template #header>基本信息</template>
          <el-form :model="form" label-width="120px" :disabled="!editing">
            <el-form-item label="站点">{{ survey?.site_name || '-' }} ({{ survey?.site_code || '-' }})</el-form-item>
            <el-form-item label="勘察日期">
              <el-date-picker v-model="form.survey_date" type="datetime" style="width:100%" />
            </el-form-item>
            <el-form-item label="勘察人">
              <el-input v-model="form.surveyor_name" />
            </el-form-item>
            <el-form-item label="勘察人电话">
              <el-input v-model="form.surveyor_phone" />
            </el-form-item>
            <el-form-item label="结论">
              <el-select v-model="form.feasibility" style="width:100%">
                <el-option label="可行" value="feasible" />
                <el-option label="有条件可行" value="conditionally_feasible" />
                <el-option label="不可行" value="infeasible" />
              </el-select>
            </el-form-item>
            <el-form-item label="地址">
              <el-input v-model="form.address" />
            </el-form-item>
            <el-form-item label="坐标">
              <div class="coords">
                <el-input-number v-model="form.latitude" :step="0.000001" :precision="6" :controls="false" />
                <span class="sep">,</span>
                <el-input-number v-model="form.longitude" :step="0.000001" :precision="6" :controls="false" />
                <el-button size="small" @click="copyCoords">复制</el-button>
              </div>
            </el-form-item>
            <el-form-item label="GPS精度(m)">
              <el-input-number v-model="form.gps_accuracy" :step="1" :controls="false" />
            </el-form-item>
            <el-form-item label="风险">
              <el-input v-model="form.risks" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="建议">
              <el-input v-model="form.recommendations" type="textarea" :rows="3" />
            </el-form-item>

            <el-divider>场地与结构</el-divider>
            <el-form-item label="站点类型"><el-input v-model="form.site_type" /></el-form-item>
            <el-form-item label="塔型"><el-input v-model="form.tower_type" /></el-form-item>
            <el-form-item label="可用挂高(m)"><el-input-number v-model="form.available_height_m" :step="0.5" :controls="false" /></el-form-item>
            <el-form-item label="荷载(kg)"><el-input-number v-model="form.load_capacity_kg" :step="10" :controls="false" /></el-form-item>

            <el-divider>供电与回传</el-divider>
            <el-form-item label="市电可用"><el-switch v-model="form.power_available" /></el-form-item>
            <el-form-item label="电源距离(m)"><el-input-number v-model="form.power_distance_m" :step="1" :controls="false" /></el-form-item>
            <el-form-item label="容量(kW)"><el-input-number v-model="form.power_capacity_kw" :step="0.1" :precision="1" :controls="false" /></el-form-item>
            <el-form-item label="接地可行"><el-switch v-model="form.earthing_feasible" /></el-form-item>
            <el-form-item label="光纤可用"><el-switch v-model="form.fiber_available" /></el-form-item>
            <el-form-item label="光纤距离(m)"><el-input-number v-model="form.fiber_distance_m" :step="1" :controls="false" /></el-form-item>
            <el-form-item label="微波LoS"><el-switch v-model="form.microwave_los" /></el-form-item>
            <el-form-item label="方位角(°)"><el-input-number v-model="form.los_azimuth_deg" :step="1" :controls="false" /></el-form-item>
            <el-form-item label="距离(km)"><el-input-number v-model="form.los_distance_km" :step="0.1" :precision="1" :controls="false" /></el-form-item>

            <el-divider>环境与进场</el-divider>
            <el-form-item label="敏感点"><el-input v-model="form.sensitive_points" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="安全/隐患"><el-input v-model="form.safety_notes" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="审批/物业限制"><el-input v-model="form.permits_constraints" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="进场限制"><el-input v-model="form.entry_constraints" type="textarea" :rows="2" /></el-form-item>

            <el-divider>业主信息</el-divider>
            <el-form-item label="业主姓名"><el-input v-model="form.owner_name" /></el-form-item>
            <el-form-item label="业主电话"><el-input v-model="form.owner_phone" /></el-form-item>
            <el-form-item label="时间窗口"><el-input v-model="form.access_time_window" /></el-form-item>
          </el-form>
        </el-card>

      </el-col>
      <el-col :span="14">
        <!-- 上传照片卡片：移动至照片墙上方，操作更就近 -->
        <el-card>
          <template #header>上传照片</template>
          <div class="upload-bar">
            <el-select v-model="uploadCategory" placeholder="选择分类" style="width:200px">
              <el-option label="全景" value="overview" />
              <el-option label="电力/配电" value="power" />
              <el-option label="机房/机柜" value="room" />
              <el-option label="管道/弱电" value="duct" />
              <el-option label="屋面/塔体" value="roof" />
              <el-option label="隐患" value="hazard" />
              <el-option label="其他" value="custom" />
            </el-select>
            <el-upload
              :disabled="!uploadCategory || !isAdmin"
              :show-file-list="false"
              multiple
              :http-request="doUpload"
              accept="image/*"
            >
              <el-button type="primary" :disabled="!uploadCategory || !isAdmin"><el-icon><Upload /></el-icon>选择图片</el-button>
            </el-upload>
          </div>
          <div class="tips">请先选择分类再上传；支持jpg/png，单张≤10MB</div>
        </el-card>

        <el-card style="margin-top: 16px;">
          <template #header>
            <div style="display:flex; justify-content: space-between; align-items:center;">
              <span>照片墙</span>
              <div class="header-actions" v-if="isAdmin">
                <el-button size="small" type="danger" :disabled="selectedIds.length===0" @click="batchDelete">删除所选</el-button>
              </div>
            </div>
          </template>
          <div v-if="photosByCatKeys.length === 0" class="empty">暂无照片</div>
          <div v-else class="photo-groups">
            <div v-for="cat in photosByCatKeys" :key="cat" class="group">
              <h4 class="group-title">{{ catLabel(cat) }}</h4>
              <div class="grid">
                <div v-for="(p, idx) in photosByCat[cat]" :key="p.id" class="item">
                  <el-image :src="fileUrl(p.file_path)" :preview-src-list="[fileUrl(p.file_path)]" fit="cover" />
                  <div class="meta compact">
                    <el-checkbox v-model="selectedMap[p.id]" size="small" />
                    <el-select size="small" v-model="p.category" class="cat-select" @change="updateCategory(p)" v-if="isAdmin">
                      <el-option label="全景" value="overview" />
                      <el-option label="电力/配电" value="power" />
                      <el-option label="机房/机柜" value="room" />
                      <el-option label="管道/弱电" value="duct" />
                      <el-option label="屋面/塔体" value="roof" />
                      <el-option label="隐患" value="hazard" />
                      <el-option label="其他" value="custom" />
                    </el-select>
                    <div class="meta-actions">
                      <el-button link type="danger" size="small" @click="delPhoto(p)" v-if="isAdmin" title="删除" aria-label="删除">
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>

        <el-card style="margin-top: 16px;">
          <template #header>上传附件（非图片）</template>
          <div class="upload-bar">
            <el-upload
              :disabled="!isAdmin"
              :show-file-list="false"
              multiple
              :http-request="doUploadAttachment"
              accept="*/*"
            >
              <el-button :disabled="!isAdmin"><el-icon><Upload /></el-icon>选择文件</el-button>
            </el-upload>
          </div>
          <div class="tips">将文件作为“附件”分类上传；支持PDF/CAD/Office等。</div>
          <div class="attachments" v-if="attachments.length">
            <ul>
              <li v-for="a in attachments" :key="a.id">
                <a :href="fileUrl(a.file_path)" target="_blank">{{ a.original_name || a.file_path }}</a>
                <el-tag size="small">{{ a.mime_type }}</el-tag>
                <el-button link type="danger" size="small" @click="delPhoto(a)" v-if="isAdmin">删除</el-button>
              </li>
            </ul>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 16px;">
      <template #header>变更历史</template>
      <el-table :data="auditLogs" height="320" v-loading="auditLoading">
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="operator_name" label="操作人" width="140" />
        <el-table-column label="动作" width="140">
          <template #default="{ row }">{{ actionLabel(row.action) }}</template>
        </el-table-column>
        <el-table-column label="摘要">
          <template #default="{ row }">
            {{ historySummary(row) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { siteSurveysApi } from '@/api/siteSurveys'
import { useUserStore } from '@/stores/user'
import config from '@/config/env.js'

const router = useRouter()
const route = useRoute()
const id = route.params.id

const survey = ref(null)
const form = ref({})
const photos = ref([])
const selectedMap = ref({})
const selectedIds = computed(() => Object.keys(selectedMap.value).filter(k => selectedMap.value[k]))
const attachments = computed(() => (photos.value || []).filter(p => (p.mime_type || '').startsWith('image/') === false))
const editing = ref(route.query.edit === '1')
const saving = ref(false)
const uploadCategory = ref('')

const load = async () => {
  const res = await siteSurveysApi.get(id)
  survey.value = res
  form.value = {
    survey_date: res.survey_date ? new Date(res.survey_date) : new Date(),
    surveyor_name: res.surveyor_name,
    surveyor_phone: res.surveyor_phone,
    feasibility: res.feasibility,
    address: res.address,
    latitude: res.latitude,
    longitude: res.longitude,
    gps_accuracy: res.gps_accuracy,
    risks: res.risks,
    recommendations: res.recommendations,
    // extra sections
    site_type: res.site_type,
    tower_type: res.tower_type,
    available_height_m: res.available_height_m,
    load_capacity_kg: res.load_capacity_kg,
    power_available: res.power_available,
    power_distance_m: res.power_distance_m,
    power_capacity_kw: res.power_capacity_kw,
    earthing_feasible: res.earthing_feasible,
    fiber_available: res.fiber_available,
    fiber_distance_m: res.fiber_distance_m,
    microwave_los: res.microwave_los,
    los_azimuth_deg: res.los_azimuth_deg,
    los_distance_km: res.los_distance_km,
    sensitive_points: res.sensitive_points,
    safety_notes: res.safety_notes,
    permits_constraints: res.permits_constraints,
    entry_constraints: res.entry_constraints,
    owner_name: res.owner_name,
    owner_phone: res.owner_phone,
    access_time_window: res.access_time_window
  }
  photos.value = res.photos || []
}

  const save = async () => {
  try {
    saving.value = true
    // 仅提交变更字段，提升历史摘要可读性
    const keys = [
      'survey_date','surveyor_name','surveyor_phone','feasibility','address','latitude','longitude','gps_accuracy',
      'risks','recommendations',
      // extra sections
      'site_type','tower_type','available_height_m','load_capacity_kg',
      'power_available','power_distance_m','power_capacity_kw','earthing_feasible',
      'fiber_available','fiber_distance_m','microwave_los','los_azimuth_deg','los_distance_km',
      'sensitive_points','safety_notes','permits_constraints','entry_constraints',
      'owner_name','owner_phone','access_time_window'
    ]
    const payload = {}
    for (const k of keys) {
      const cur = form.value[k]
      const orig = survey.value ? (
        k === 'survey_date' ? (survey.value.survey_date ? new Date(survey.value.survey_date) : null) : survey.value[k]
      ) : null
      const changed = (k === 'survey_date')
        ? (!!cur && (!!orig ? cur.getTime() !== new Date(orig).getTime() : true))
        : (cur !== orig)
      if (changed) {
        payload[k] = (k === 'survey_date' && cur instanceof Date) ? cur.toISOString() : cur
      }
    }
    await siteSurveysApi.update(id, payload)
      ElMessage.success('保存成功')
      editing.value = false
      await load()
      await loadAuditLogs()
    } catch (e) {
    console.error(e)
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

  const doUpload = async (opt) => {
    try {
      const fd = new FormData()
      fd.append('file', opt.file)
      fd.append('category', uploadCategory.value)
      const res = await siteSurveysApi.uploadPhoto(id, fd)
      photos.value.unshift(res)
      ElMessage.success('上传成功')
      await loadAuditLogs()
    } catch (e) {
    console.error(e)
    ElMessage.error('上传失败')
  }
}

  const delPhoto = async (p) => {
    try {
      await siteSurveysApi.deletePhoto(p.id)
      photos.value = photos.value.filter(x => x.id !== p.id)
      ElMessage.success('已删除')
      await loadAuditLogs()
    } catch (e) {
    console.error(e)
    ElMessage.error('删除失败')
  }
}

  const updateCategory = async (p) => {
    try {
      const fd = new FormData()
      fd.append('category', p.category || '')
      await siteSurveysApi.updatePhoto(p.id, fd)
      ElMessage.success('已更新分类')
      await loadAuditLogs()
    } catch (e) {
    console.error(e)
    ElMessage.error('更新失败')
  }
}

  const batchDelete = async () => {
    try {
      if (selectedIds.value.length === 0) return
      await siteSurveysApi.deletePhotosBatch(id, selectedIds.value)
      photos.value = photos.value.filter(x => !selectedIds.value.includes(x.id))
      selectedMap.value = {}
      ElMessage.success('已删除所选')
      await loadAuditLogs()
    } catch (e) {
    console.error(e)
    ElMessage.error('删除失败')
  }
}

  const doUploadAttachment = async (opt) => {
    try {
      const fd = new FormData()
      fd.append('files', opt.file)
      fd.append('category', 'attachment')
      const res = await siteSurveysApi.uploadPhotosBatch(id, fd)
      await load()
      ElMessage.success(`已上传 ${res.count || 1} 个附件`)
      await loadAuditLogs()
    } catch (e) {
    console.error(e)
    ElMessage.error('上传失败')
  }
}

// 排序与EXIF功能已移除

const photosByCat = computed(() => {
  const map = {}
  for (const p of photos.value) {
    const k = p.category || 'uncategorized'
    if (!map[k]) map[k] = []
    map[k].push(p)
  }
  return map
})

const photosByCatKeys = computed(() => Object.keys(photosByCat.value))

const catLabel = (k) => ({
  overview: '全景', power: '电力/配电', room: '机房/机柜', duct: '管道/弱电', roof: '屋面/塔体', hazard: '隐患', custom: '其他', uncategorized: '未分类'
}[k] || k)

const fileUrl = (filePath) => {
  if (!filePath) return ''
  // absolute or data URL
  if (/^https?:\/\//i.test(filePath) || filePath.startsWith('data:')) return filePath
  // common case: backend returns paths like 'uploads/xxx' (no leading slash)
  if (filePath.startsWith('uploads/')) return `${config.API_BASE_URL}/${filePath}`
  // leading slash paths like '/uploads/xxx' should also point to backend host
  if (filePath.startsWith('/uploads/')) return `${config.API_BASE_URL}${filePath}`
  // fallback: resolve relative to backend base
  return `${config.API_BASE_URL}/${filePath.replace(/^\//, '')}`
}
const formatDate = (iso) => iso ? new Date(iso).toLocaleString() : '-'

const toggleEdit = () => { editing.value = true }
const goBack = () => router.back()
const copyCoords = () => {
  const t = `${form.value.latitude || ''},${form.value.longitude || ''}`
  navigator.clipboard.writeText(t)
  ElMessage.success('已复制坐标')
}

const exportZip = async () => {
  try {
    const blob = await siteSurveysApi.exportZip(id)
    const url = window.URL.createObjectURL(new Blob([blob]))
    const a = document.createElement('a')
    a.href = url
    a.download = `site_survey_${id}.zip`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败')
  }
}

const exportPdf = async () => {
  try {
    const blob = await siteSurveysApi.exportPdf(id)
    const url = window.URL.createObjectURL(new Blob([blob]))
    const a = document.createElement('a')
    a.href = url
    a.download = `site_survey_${id}.pdf`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败')
  }
}

onMounted(load)

// audit logs
const auditLogs = ref([])
const auditLoading = ref(false)
const loadAuditLogs = async () => {
  try {
    auditLoading.value = true
    const res = await siteSurveysApi.getAuditLogs(id, { limit: 100 })
    auditLogs.value = Array.isArray(res) ? res : []
  } catch (e) {
    console.error(e)
  } finally {
    auditLoading.value = false
  }
}
onMounted(loadAuditLogs)
const actionLabel = (a) => ({
  create: '创建', update: '更新', delete: '删除', import: '导入',
  photo_upload: '上传照片', photo_delete: '删除照片',
  photo_batch_upload: '批量上传照片', photo_batch_delete: '批量删除照片',
  photo_update: '照片信息变更', photo_reorder: '照片排序调整'
}[a] || a)

const labelMap = {
  feasibility: '结论', surveyor_name: '勘察人', survey_date: '勘察日期', surveyor_phone: '勘察人电话', address: '地址',
  latitude: '纬度', longitude: '经度', gps_accuracy: 'GPS精度', risks: '风险', recommendations: '建议',
  site_type: '站点类型', tower_type: '塔型', available_height_m: '可用挂高', load_capacity_kg: '荷载',
  power_available: '市电可用', power_distance_m: '电源距离', power_capacity_kw: '容量(kW)', earthing_feasible: '接地可行',
  fiber_available: '光纤可用', fiber_distance_m: '光纤距离', microwave_los: '微波LoS', los_azimuth_deg: '方位角', los_distance_km: '距离(km)',
  sensitive_points: '敏感点', safety_notes: '安全/隐患', permits_constraints: '审批/物业限制', entry_constraints: '进场限制',
  owner_name: '业主姓名', owner_phone: '业主电话', access_time_window: '时间窗口',
  category: '分类', taken_at: '拍摄时间', sort_order: '显示顺序'
}
const feasibilityLabel = (v) => ({ feasible: '可行', conditionally_feasible: '有条件可行', infeasible: '不可行' }[v] || v)
const formatVal = (k, v) => {
  if (k === 'feasibility') return feasibilityLabel(v)
  if (k === 'survey_date' || k === 'taken_at' || k === 'created_at') return formatDate(v)
  if (typeof v === 'number' && (k === 'latitude' || k === 'longitude')) return v.toFixed(6)
  if (typeof v === 'boolean' && ['power_available','fiber_available','earthing_feasible','microwave_los'].includes(k)) return v ? '是' : '否'
  if (v === null || v === undefined || v === '') return '-'
  return v
}
const historySummary = (row) => {
  const a = row.action
  const d = row.details || {}
  if (a === 'update' && Array.isArray(d.changed) && d.changed.length) {
    return d.changed.map(ch => `${labelMap[ch.field] || ch.field}：${formatVal(ch.field, ch.before)} → ${formatVal(ch.field, ch.after)}`).join('；')
  }
  if (a === 'create') return '创建勘察'
  if (a === 'delete') return '删除勘察'
  if (a === 'import') return `批量导入：成功${d.success||0} 失败${d.failed||0}`
  if (a === 'photo_upload') return `上传照片：${(d.category && labelMap[d.category]) ? labelMap[d.category] : (d.category || '未分类')} - ${d.original_name || d.photo_id}`
  if (a === 'photo_delete') return `删除照片：${d.original_name || d.photo_id}`
  if (a === 'photo_batch_upload') return `批量上传照片：${d.count || 0} 张`
  if (a === 'photo_batch_delete') return `批量删除照片：${d.count || 0} 张`
  if (a === 'photo_update' && Array.isArray(d.changed) && d.changed.length) {
    return d.changed.map(ch => `${labelMap[ch.field] || ch.field}：${formatVal(ch.field, ch.before)} → ${formatVal(ch.field, ch.after)}`).join('；')
  }
  if (a === 'photo_reorder') return '调整了照片排序'
  // fallback
  if (d.changed_keys && d.changed_keys.length) return `变更字段：${d.changed_keys.join(', ')}`
  if (d.after) return `变更字段：${Object.keys(d.after).join(', ')}`
  return a
}

const userStore = useUserStore()
const isAdmin = userStore.isAdmin
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
.coords { display:flex; gap:8px; align-items:center; }
.coords .sep { color:#999; }
.upload-bar { display:flex; gap:12px; align-items:center; margin-bottom: 8px; }
.tips { color:#999; font-size: 12px; }
.empty { color:#999; }
.photo-groups { display:flex; flex-direction: column; gap: 20px; }
.group-title { margin:0 0 8px 0; font-weight: 600; }
/* 更灵活的自适应网格，最小宽 240px */
.grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.item { border:1px solid #eee; border-radius: 10px; overflow:hidden; background:#fff; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.item .el-image { width:100%; height:auto; aspect-ratio: 4 / 3; }
.meta { display:flex; justify-content: space-between; align-items:center; padding:6px 8px; font-size:12px; background:#fafafa; }
.meta.compact { gap: 8px; }
.cat-select { width: 110px; }
/* 让复选框更紧凑，隐藏文字标签 */
.meta :deep(.el-checkbox__label) { display:none; }
/* 压缩链接按钮内边距 */
.meta :deep(.el-button.is-link) { padding: 0 6px; }
@media (max-width: 1280px) {
  .grid { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
}
@media (max-width: 960px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
