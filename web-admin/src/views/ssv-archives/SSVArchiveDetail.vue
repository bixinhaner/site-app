<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <h1>SSV 档案详情</h1>
      <div class="header-actions">
        <el-button @click="goBack"><el-icon><Back /></el-icon>返回</el-button>
        <el-tag>当前版本：{{ archive?.current_version }}</el-tag>
        <el-button v-if="!editing && isAdmin" type="primary" @click="startEdit">
          <el-icon><Edit /></el-icon>
          编辑
        </el-button>
        <el-button v-else-if="editing && isAdmin" type="primary" :disabled="saving" @click="saveChanges">
          <el-icon><Check /></el-icon>
          保存
        </el-button>
        <el-button v-if="editing" @click="cancelEdit">取消编辑</el-button>
        <el-dropdown>
          <el-button :loading="exporting">
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
        <el-button @click="openHistory">历史</el-button>
      </div>
    </div>

    <el-card v-if="content">
      <div class="meta">
        <div>站点：{{ content.meta?.site_name }}（{{ content.meta?.site_code }}）</div>
        <div>工单：{{ content.meta?.work_order_id }}</div>
        <div>检查：{{ content.meta?.inspection_id }}</div>
        <div>模板：{{ content.meta?.template?.name }} v{{ content.meta?.template?.version }}</div>
      </div>

	      <archive-form-renderer
	        :content="content"
	        :disabled="!editing"
	        @change="onFieldChange"
	        @upload-photo="onUploadPhoto"
	        @delete-photo="onDeletePhoto"
	      />

	      <el-divider />
	      <div class="attachments">
	        <div class="attachments-header">
	          <div class="attachments-title">附件</div>
	          <el-upload
	            v-if="editing && isAdmin"
	            multiple
	            :show-file-list="false"
	            :http-request="onUploadAttachment"
	          >
	            <el-button size="small" type="primary" plain>上传附件</el-button>
	          </el-upload>
	        </div>

	        <el-table
	          v-if="Array.isArray(content.attachments) && content.attachments.length"
	          :data="content.attachments"
	          size="small"
	          border
	        >
	          <el-table-column label="文件名" min-width="260">
	            <template #default="{ row }">
	              <div class="att-name">
	                <el-link :href="fileUrl(row.file_path)" target="_blank" :underline="false">
	                  {{ row.original_name || row.file_name || row.file_path }}
	                </el-link>
	                <el-tag v-if="row.pending" size="small" type="warning" class="att-pending">未保存</el-tag>
	              </div>
	              <div v-if="row.description" class="att-desc">{{ row.description }}</div>
	            </template>
	          </el-table-column>
	          <el-table-column label="大小" width="120">
	            <template #default="{ row }">{{ formatBytes(row.file_size) }}</template>
	          </el-table-column>
	          <el-table-column label="类型" min-width="160">
	            <template #default="{ row }">{{ row.mime_type || '-' }}</template>
	          </el-table-column>
	          <el-table-column label="操作" width="140" fixed="right">
	            <template #default="{ row }">
	              <el-link :href="fileUrl(row.file_path)" target="_blank" :underline="false">下载</el-link>
	              <el-button
	                v-if="editing && isAdmin"
	                link
	                type="danger"
	                size="small"
	                @click="onDeleteAttachment(row)"
	              >
	                删除
	              </el-button>
	            </template>
	          </el-table-column>
	        </el-table>
	        <div v-else class="muted">暂无附件</div>
	      </div>
	    </el-card>

    <el-drawer v-model="historyVisible" title="变更历史" size="60%">
      <el-table :data="history" height="70vh" v-loading="historyLoading">
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ formatDate(row.changed_at) }}</template>
        </el-table-column>
        <el-table-column label="操作人" width="160">
          <template #default="{ row }">{{ formatOperator(row) }}</template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="100" />
        <el-table-column label="摘要">
          <template #default="{ row }">{{ row.summary || row.change_summary || '-' }}</template>
        </el-table-column>
        <el-table-column label="明细" min-width="360">
          <template #default="{ row }">
            <div v-if="Array.isArray(row.details) && row.details.length">
              <ul class="hist-lines">
                <li v-for="(line, idx) in row.details" :key="idx">{{ line }}</li>
              </ul>
            </div>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ssvArchivesApi } from '@/api/ssvArchives'
import ArchiveFormRenderer from '@/components/archives/ArchiveFormRenderer.vue'
import { useUserStore } from '@/stores/user'
import { resolveImageUrl } from '@/utils/imageLoader'
import { getCurrentLocale } from '@/i18n/translator'
import { buildArchiveExportName } from '@/utils/archiveExportFilename'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const id = route.params.id

const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const editing = ref(false)
const isAdmin = userStore.isAdmin
const archive = ref(null)
const origin = ref(null)
const content = ref(null)
const edits = reactive(new Map()) // key: json pointer, value: new value
// 照片变更在前端暂存，保存时一次性通过 JSON Patch 提交
const photoAdds = ref([]) // { categoryId, itemId, level, sectorId?, cellId?, photo }
const photoDeletes = ref([]) // { categoryId, itemId, level, sectorId?, cellId?, photoId }
// 附件变更：编辑态先预上传，保存时再写入 content.attachments[]
const attachmentAdds = ref([]) // { attachment }
const attachmentDeletes = ref([]) // { attachmentId }

const history = ref([])
const historyLoading = ref(false)
const historyVisible = ref(false)

const safeClone = (obj) => {
  // 优先使用 JSON 深拷贝，避免 structuredClone 在含有不可克隆对象时报错
  try {
    return JSON.parse(JSON.stringify(obj))
  } catch (e) {
    try {
      if (typeof globalThis.structuredClone === 'function') {
        return globalThis.structuredClone(obj)
      }
    } catch (_) { /* ignore */ }
    // 最后兜底：返回浅拷贝
    if (obj && typeof obj === 'object') {
      return Array.isArray(obj) ? obj.slice() : { ...obj }
    }
    return obj
  }
}

const load = async (preserveEdits = false) => {
  try {
    loading.value = true
    const res = await ssvArchivesApi.get(id)
    archive.value = res
    origin.value = safeClone(res.content)
    content.value = safeClone(res.content)
    if (preserveEdits) {
      applyLocalEdits()
	    } else {
	      edits.clear()
	      editing.value = false
	      photoAdds.value = []
	      photoDeletes.value = []
	      attachmentAdds.value = []
	      attachmentDeletes.value = []
	    }
	  } catch (e) {
    console.error(e)
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function exportZip() {
  try {
    exporting.value = true
    ElMessage.info('正在生成Zip压缩包，请稍候…')
    const currentLocale = getCurrentLocale()
    const blob = await ssvArchivesApi.exportZip(id, { locale: currentLocale })
    const url = window.URL.createObjectURL(new Blob([blob]))
    const a = document.createElement('a')
    a.href = url
    a.download = buildExportName('zip', currentLocale)
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('Zip导出成功，浏览器将开始下载')
  } catch (e) {
    console.error(e)
    ElMessage.error('导出Zip失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

async function exportPdf() {
  try {
    exporting.value = true
    ElMessage.info('正在生成PDF，请稍候…')
    const currentLocale = getCurrentLocale()
    const blob = await ssvArchivesApi.exportPdf(id, { locale: currentLocale })
    const url = window.URL.createObjectURL(new Blob([blob]))
    const a = document.createElement('a')
    a.href = url
    a.download = buildExportName('pdf', currentLocale)
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('PDF导出成功，浏览器将开始下载')
  } catch (e) {
    console.error(e)
    ElMessage.error('导出PDF失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

function buildExportName(ext, locale) {
  return buildArchiveExportName({
    archiveType: 'ssv',
    locale,
    siteCode: content.value?.meta?.site_code,
    siteName: content.value?.meta?.site_name,
    version: archive.value?.current_version,
    updatedAt: archive.value?.updated_at,
    ext,
  })
}

const jsonPointerEscape = (s) => String(s).replaceAll('~', '~0').replaceAll('/', '~1')
const jsonPointerUnescape = (s) => String(s).replaceAll('~1', '/').replaceAll('~0', '~')

const normalizeId = (v) => String(v ?? '').trim()

const normalizeLevel = (level) => {
  const lv = String(level || 'site').trim().toLowerCase()
  if (lv === 'sector') return 'sector'
  if (lv === 'cell') return 'cell'
  return 'site'
}

function resolvePhotosContainer(root, categoryId, itemId, level, sectorId, cellId) {
  const cats = root?.check_categories || []
  const catIndex = cats.findIndex((x) => String(x.category_id) === String(categoryId))
  if (catIndex < 0) return null
  const items = cats[catIndex]?.items || []
  const itemIndex = items.findIndex((x) => String(x.item_id) === String(itemId))
  if (itemIndex < 0) return null
  const item = items[itemIndex]

  const lv = normalizeLevel(level)
  if (lv === 'sector') {
    const secIndex = (item?.sectors || []).findIndex((x) => String(x.sector_id) === String(sectorId))
    if (secIndex < 0) return null
    const sec = item.sectors[secIndex]
    return {
      catIndex,
      itemIndex,
      level: 'sector',
      container: sec,
      photosPathBase: `/check_categories/${catIndex}/items/${itemIndex}/sectors/${secIndex}/photos`,
    }
  }
  if (lv === 'cell') {
    const cellIndex = (item?.cells || []).findIndex((x) => String(x.cell_id) === String(cellId))
    if (cellIndex < 0) return null
    const cell = item.cells[cellIndex]
    return {
      catIndex,
      itemIndex,
      level: 'cell',
      container: cell,
      photosPathBase: `/check_categories/${catIndex}/items/${itemIndex}/cells/${cellIndex}/photos`,
    }
  }
  return {
    catIndex,
    itemIndex,
    level: 'site',
    container: item,
    photosPathBase: `/check_categories/${catIndex}/items/${itemIndex}/photos`,
  }
}

function applyLocalEdits() {
  try {
    for (const [path, value] of edits.entries()) {
      const parts = String(path).split('/').filter(Boolean)
      if (parts.length < 6) continue
      const catIndex = Number(parts[1])
      const itemIndex = Number(parts[3])
      const fieldKey = jsonPointerUnescape(parts[5])
      const cat = content.value?.check_categories?.[catIndex]
      const item = cat?.items?.[itemIndex]
      if (!item) continue
      if (!item.values) item.values = {}
      item.values[fieldKey] = value
    }
    for (const rec of photoAdds.value) {
      const { categoryId, itemId, level, sectorId, cellId, photo } = rec
      const loc = resolvePhotosContainer(content.value, categoryId, itemId, level, sectorId, cellId)
      if (!loc) continue
      const photos = loc.container.photos || (loc.container.photos = [])
      if (!photos.find((p) => String(p.id) === String(photo.id))) {
        photos.push(photo)
      }
    }
	    for (const rec of photoDeletes.value) {
	      const { categoryId, itemId, level, sectorId, cellId, photoId } = rec
	      const loc = resolvePhotosContainer(content.value, categoryId, itemId, level, sectorId, cellId)
	      if (!loc) continue
	      const photos = Array.isArray(loc.container.photos) ? loc.container.photos : []
	      const idx = photos.findIndex((p) => String(p.id) === String(photoId))
	      if (idx >= 0) photos.splice(idx, 1)
	    }
	    if (!Array.isArray(content.value.attachments)) content.value.attachments = []
	    for (const rec of attachmentAdds.value) {
	      const att = rec?.attachment
	      if (!att) continue
	      if (!content.value.attachments.find((x) => String(x.id) === String(att.id))) {
	        content.value.attachments.push(att)
	      }
	    }
	    for (const rec of attachmentDeletes.value) {
	      const attachmentId = rec?.attachmentId
	      if (!attachmentId) continue
	      const idx = (content.value.attachments || []).findIndex((x) => String(x.id) === String(attachmentId))
	      if (idx >= 0) content.value.attachments.splice(idx, 1)
	    }
	  } catch (e) {
	    console.warn('applyLocalEdits failed:', e)
	  }
	}

function onFieldChange({ categoryId, itemId, fieldId, value }) {
  if (!editing.value) return
  for (const c of content.value.check_categories || []) {
    if (String(c.category_id) !== String(categoryId)) continue
    for (const it of c.items || []) {
      if (String(it.item_id) !== String(itemId)) continue
      if (!it.values) it.values = {}
      it.values[fieldId] = value
    }
  }
  const catIndex = (content.value.check_categories || []).findIndex(x => String(x.category_id) === String(categoryId))
  const itemIndex = (content.value.check_categories[catIndex]?.items || []).findIndex(x => String(x.item_id) === String(itemId))
  if (catIndex >= 0 && itemIndex >= 0) {
    const path = `/check_categories/${catIndex}/items/${itemIndex}/values/${jsonPointerEscape(fieldId)}`
    edits.set(path, value)
  }
}

async function saveChanges() {
  try {
    saving.value = true
    const patchOps = []
    for (const [path, value] of edits.entries()) {
      patchOps.push({ op: 'replace', path, value })
    }
    const addGroups = new Map()
    for (const rec of photoAdds.value) {
      const loc = resolvePhotosContainer(origin.value, rec.categoryId, rec.itemId, rec.level, rec.sectorId, rec.cellId)
      if (!loc) continue
      const base = loc.photosPathBase
      const photoVal = { ...rec.photo }
      delete photoVal.pending
      if (!addGroups.has(base)) {
        addGroups.set(base, { hasArray: Array.isArray(loc.container?.photos), photos: [] })
      }
      addGroups.get(base).photos.push(photoVal)
    }
    for (const [base, info] of addGroups.entries()) {
      if (info.hasArray) {
        info.photos.forEach((p) => patchOps.push({ op: 'add', path: `${base}/-`, value: p }))
      } else if (info.photos.length) {
        patchOps.push({ op: 'add', path: base, value: info.photos })
      }
    }

    const removeGroups = new Map()
    for (const rec of photoDeletes.value) {
      const loc = resolvePhotosContainer(origin.value, rec.categoryId, rec.itemId, rec.level, rec.sectorId, rec.cellId)
      if (!loc) continue
      const photos = Array.isArray(loc.container?.photos) ? loc.container.photos : []
      const idx = photos.findIndex((p) => String(p.id) === String(rec.photoId))
      if (idx < 0) continue
      const base = loc.photosPathBase
      if (!removeGroups.has(base)) removeGroups.set(base, [])
      removeGroups.get(base).push(idx)
    }
	    for (const [base, indexes] of removeGroups.entries()) {
	      indexes
	        .filter((x) => Number.isInteger(x))
	        .sort((a, b) => b - a)
	        .forEach((idx) => patchOps.push({ op: 'remove', path: `${base}/${idx}` }))
	    }

	    const originAttachments = Array.isArray(origin.value?.attachments) ? origin.value.attachments : null
	    if (attachmentAdds.value.length) {
	      const addList = attachmentAdds.value
	        .map((x) => x?.attachment)
	        .filter(Boolean)
	        .map((a) => {
	          const v = { ...a }
	          delete v.pending
	          delete v._temp
	          return v
	        })
	      if (addList.length) {
	        if (originAttachments) {
	          addList.forEach((a) => patchOps.push({ op: 'add', path: '/attachments/-', value: a }))
	        } else {
	          patchOps.push({ op: 'add', path: '/attachments', value: addList })
	        }
	      }
	    }
	    if (attachmentDeletes.value.length && originAttachments) {
	      const idxs = attachmentDeletes.value
	        .map((x) => originAttachments.findIndex((a) => String(a?.id) === String(x?.attachmentId)))
	        .filter((i) => i >= 0)
	        .sort((a, b) => b - a)
	      idxs.forEach((i) => patchOps.push({ op: 'remove', path: `/attachments/${i}` }))
	    }

	    if (!patchOps.length) {
	      ElMessage.info('没有变更需要保存')
	      editing.value = false
	      return
	    }

    await ssvArchivesApi.patch(id, patchOps, { base_version: archive.value?.current_version, change_summary: '用户编辑' })
	    ElMessage.success('已保存')
	    edits.clear()
	    photoAdds.value = []
	    photoDeletes.value = []
	    attachmentAdds.value = []
	    attachmentDeletes.value = []
	    await load(false)
  } catch (e) {
    console.error(e)
    const msg = e?.response?.data?.detail || '保存失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
    editing.value = false
  }
}

function startEdit() {
  editing.value = true
}

function cancelEdit() {
  if (edits.size || photoAdds.value.length || photoDeletes.value.length || attachmentAdds.value.length || attachmentDeletes.value.length) {
    ElMessageBox.confirm('放弃当前修改？', '提示', { type: 'warning' })
      .then(() => {
        edits.clear()
        photoAdds.value = []
        photoDeletes.value = []
        attachmentAdds.value = []
        attachmentDeletes.value = []
        load(false)
      })
      .catch(() => {})
  } else {
    editing.value = false
    load(false)
  }
}

function goBack() {
  router.back()
}

function fileUrl(p) { return resolveImageUrl(p) }

function formatBytes(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return '-'
  const kb = 1024
  const mb = kb * 1024
  const gb = mb * 1024
  if (n >= gb) return `${(n / gb).toFixed(2)} GB`
  if (n >= mb) return `${(n / mb).toFixed(2)} MB`
  if (n >= kb) return `${(n / kb).toFixed(2)} KB`
  return `${n} B`
}

function formatDate(v) {
  return v ? new Date(v).toLocaleString() : '-'
}

function formatOperator(row) {
  const direct = String(row?.operator_name || '').trim()
  if (direct) return direct
  if (row?.changed_by != null && row?.changed_by !== '') return `用户#${row.changed_by}`
  return '-'
}

async function loadHistory() {
  try {
    historyLoading.value = true
    const res = await ssvArchivesApi.history(id)
    const rows = Array.isArray(res) ? res : []
    history.value = rows.map((row) => {
      const rawDetails = row?.details
      let details = []
      if (Array.isArray(rawDetails)) {
        details = rawDetails
          .map((line) => (line == null ? '' : String(line).trim()))
          .filter(Boolean)
      } else if (typeof rawDetails === 'string' && rawDetails.trim()) {
        details = [rawDetails.trim()]
      }
      return {
        ...row,
        details,
      }
    })
  } catch (e) {
    console.error(e)
    ElMessage.error('加载历史失败')
  } finally {
    historyLoading.value = false
  }
}

function openHistory() {
  historyVisible.value = true
  if (!history.value || history.value.length === 0) {
    loadHistory()
  }
}

async function onUploadPhoto(payload) {
  if (!editing.value) return
  try {
    const { categoryId, itemId, file, fieldId: rawFieldId, level: rawLevel, sectorId: rawSectorId, cellId: rawCellId } = payload || {}
    const fieldId = normalizeId(rawFieldId)
    const level = normalizeLevel(rawLevel)
    const sectorId = normalizeId(rawSectorId)
    const cellId = normalizeId(rawCellId)

    const res = await ssvArchivesApi.uploadTempPhoto(id, {
      category_id: categoryId,
      item_id: itemId,
      file,
      field_id: fieldId || undefined,
      level,
      sector_id: sectorId || undefined,
      cell_id: cellId || undefined,
    })
    const photo = { ...res, field_id: fieldId || res.field_id || null, pending: true }
    const rec = { categoryId, itemId, level, photo }
    if (level === 'sector' && sectorId) rec.sectorId = sectorId
    if (level === 'cell' && cellId) rec.cellId = cellId
    photoAdds.value.push(rec)
    applyLocalEdits()
    ElMessage.success('已上传，保存后生效')
    const warning = res?.duplicate_warning
    if (warning && typeof warning === 'object') {
      const warningMsg = typeof warning.message === 'string' ? warning.message : '检测到重复图片，当前未阻断上传'
      ElMessage.warning(warningMsg)
    }
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    if (typeof detail === 'string') {
      ElMessage.error(detail)
    } else if (detail && typeof detail === 'object') {
      ElMessage.error(detail.message || '上传失败')
    } else {
      ElMessage.error('上传失败')
    }
  }
}

async function onUploadAttachment(opt) {
  try {
    if (!editing.value) return
    const file = opt?.file
    if (!file) return
    const res = await ssvArchivesApi.uploadTempAttachment(id, { file })
    const att = {
      ...res,
      original_name: res?.original_name || file.name,
      file_size: res?.file_size ?? file.size,
      mime_type: res?.mime_type || file.type,
      pending: true,
    }
    if (!Array.isArray(content.value.attachments)) content.value.attachments = []
    if (!content.value.attachments.find((x) => String(x.id) === String(att.id))) {
      content.value.attachments.push(att)
    }
    attachmentAdds.value.push({ attachment: att })
    ElMessage.success('附件已上传（未保存）')
  } catch (e) {
    console.error(e)
    ElMessage.error('上传附件失败')
  }
}

async function onDeleteAttachment(row) {
  try {
    if (!editing.value) return
    const attachmentId = row?.id
    if (!attachmentId) return
    if (row?.pending) {
      const idx = attachmentAdds.value.findIndex((x) => String(x?.attachment?.id) === String(attachmentId))
      if (idx >= 0) attachmentAdds.value.splice(idx, 1)
    } else {
      if (!attachmentDeletes.value.find((x) => String(x?.attachmentId) === String(attachmentId))) {
        attachmentDeletes.value.push({ attachmentId })
      }
    }
    const list = Array.isArray(content.value.attachments) ? content.value.attachments : []
    const i = list.findIndex((x) => String(x.id) === String(attachmentId))
    if (i >= 0) list.splice(i, 1)
    ElMessage.success('已移除附件（保存后生效）')
  } catch (e) {
    console.error(e)
    ElMessage.error('删除失败')
  }
}

async function onDeletePhoto(payload) {
  if (!editing.value) return
  const { categoryId, itemId, level, sectorId, cellId, photoId, photo } = payload || {}
  try {
    await ElMessageBox.confirm('确认删除该照片？', '提示', { type: 'warning' })
  } catch (e) {
    return
  }

  const pendingIdx = photoAdds.value.findIndex((x) => String(x.photo?.id) === String(photoId))
  const loc = resolvePhotosContainer(content.value, categoryId, itemId, level, sectorId, cellId)
  if (loc) {
    const photos = Array.isArray(loc.container.photos) ? loc.container.photos : []
    const idx = photos.findIndex((p) => String(p.id) === String(photoId))
    if (idx >= 0) photos.splice(idx, 1)
  }
  if (pendingIdx >= 0 || photo?.pending) {
    if (pendingIdx >= 0) photoAdds.value.splice(pendingIdx, 1)
    applyLocalEdits()
    ElMessage.success('已移除未保存的照片')
    return
  }

  const del = { categoryId, itemId, level: normalizeLevel(level), photoId }
  const sid = normalizeId(sectorId)
  const cid = normalizeId(cellId)
  if (del.level === 'sector' && sid) del.sectorId = sid
  if (del.level === 'cell' && cid) del.cellId = cid
  if (!photoDeletes.value.find((x) => String(x.photoId) === String(photoId))) {
    photoDeletes.value.push(del)
  }
  applyLocalEdits()
}

onMounted(load)
</script>

<style scoped>
.page { padding: 16px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.header-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 6px 12px; margin-bottom: 12px; color: #666; }
.hist-lines { padding-left: 16px; margin: 0; }
.hist-lines li { list-style: disc; line-height: 1.5; }
.muted { color: #999; }
.attachments { margin-top: 8px; }
.attachments-header { display:flex; align-items:center; justify-content:space-between; margin-bottom: 8px; }
.attachments-title { font-weight: 600; }
.att-name { display:flex; align-items:center; gap: 8px; flex-wrap: wrap; }
.att-pending { margin-left: 4px; }
.att-desc { color: #777; font-size: 12px; margin-top: 4px; }
</style>
