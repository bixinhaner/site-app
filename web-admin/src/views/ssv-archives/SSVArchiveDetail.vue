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
    </el-card>

    <el-drawer v-model="historyVisible" title="变更历史" size="60%">
      <el-table :data="history" height="70vh" v-loading="historyLoading">
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ formatDate(row.changed_at) }}</template>
        </el-table-column>
        <el-table-column prop="operator_name" label="操作人" width="140" />
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

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const id = route.params.id

const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const isAdmin = userStore.isAdmin
const archive = ref(null)
const origin = ref(null)
const content = ref(null)
const edits = reactive(new Map()) // key: json pointer, value: new value
// 照片变更在前端暂存，保存时一次性通过 JSON Patch 提交
const photoAdds = ref([]) // { categoryId, itemId, photo }
const photoDeletes = ref([]) // { categoryId, itemId, photoId }

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
    const blob = await ssvArchivesApi.exportZip(id)
    const url = window.URL.createObjectURL(new Blob([blob]))
    const a = document.createElement('a')
    a.href = url
    a.download = buildExportName('zip')
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败')
  }
}

async function exportPdf() {
  try {
    const blob = await ssvArchivesApi.exportPdf(id)
    const url = window.URL.createObjectURL(new Blob([blob]))
    const a = document.createElement('a')
    a.href = url
    a.download = buildExportName('pdf')
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败')
  }
}

function buildExportName(ext) {
  const code = content.value?.meta?.site_code || 'NA'
  const name = content.value?.meta?.site_name || 'NA'
  const ver = archive.value?.current_version || 1
  const ts = archive.value?.updated_at ? new Date(archive.value.updated_at) : new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const tsStr = `${ts.getFullYear()}${pad(ts.getMonth()+1)}${pad(ts.getDate())}_${pad(ts.getHours())}${pad(ts.getMinutes())}`
  const raw = `SSV档案_${code}_${name}_v${ver}_${tsStr}.${ext}`
  return raw.replace(/[\\/:*?"<>|]/g, '-').replace(/\s+/g, '_')
}

const jsonPointerEscape = (s) => String(s).replaceAll('~', '~0').replaceAll('/', '~1')
const jsonPointerUnescape = (s) => String(s).replaceAll('~1', '/').replaceAll('~0', '~')

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
      const { categoryId, itemId, photo } = rec
      const catIdx = (content.value?.check_categories || []).findIndex(x => String(x.category_id) === String(categoryId))
      const itemIdx = (content.value?.check_categories?.[catIdx]?.items || []).findIndex(x => String(x.item_id) === String(itemId))
      if (catIdx >= 0 && itemIdx >= 0) {
        const photos = content.value.check_categories[catIdx].items[itemIdx].photos || (content.value.check_categories[catIdx].items[itemIdx].photos = [])
        if (!photos.find(p => String(p.id) === String(photo.id))) {
          photos.push(photo)
        }
      }
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
    for (const rec of photoAdds.value) {
      const catIndex = (origin.value?.check_categories || []).findIndex(x => String(x.category_id) === String(rec.categoryId))
      const itemIndex = (origin.value?.check_categories?.[catIndex]?.items || []).findIndex(x => String(x.item_id) === String(rec.itemId))
      if (catIndex >= 0 && itemIndex >= 0) {
        const originItem = origin.value?.check_categories?.[catIndex]?.items?.[itemIndex] || {}
        const photoVal = { ...rec.photo }
        delete photoVal.pending
        if (Array.isArray(originItem.photos)) {
          const path = `/check_categories/${catIndex}/items/${itemIndex}/photos/-`
          patchOps.push({ op: 'add', path, value: photoVal })
        } else {
          const path = `/check_categories/${catIndex}/items/${itemIndex}/photos`
          patchOps.push({ op: 'add', path, value: [photoVal] })
        }
      }
    }
    for (const rec of photoDeletes.value) {
      const catIndex = (origin.value?.check_categories || []).findIndex(x => String(x.category_id) === String(rec.categoryId))
      const itemIndex = (origin.value?.check_categories?.[catIndex]?.items || []).findIndex(x => String(x.item_id) === String(rec.itemId))
      if (catIndex >= 0 && itemIndex >= 0) {
        const path = `/check_categories/${catIndex}/items/${itemIndex}/photos/${rec.photoIndex}`
        patchOps.push({ op: 'remove', path })
      }
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
  if (edits.size || photoAdds.value.length || photoDeletes.value.length) {
    ElMessageBox.confirm('放弃当前修改？', '提示', { type: 'warning' })
      .then(() => {
        edits.clear()
        photoAdds.value = []
        photoDeletes.value = []
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

function formatDate(v) {
  return v ? new Date(v).toLocaleString() : '-'
}

async function openHistory() {
  try {
    historyVisible.value = true
    historyLoading.value = true
    const res = await ssvArchivesApi.history(id)
    history.value = Array.isArray(res) ? res : []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载历史失败')
  } finally {
    historyLoading.value = false
  }
}

async function onUploadPhoto({ categoryId, itemId, file }) {
  if (!editing.value) return
  try {
    const res = await ssvArchivesApi.uploadTempPhoto(id, { categoryId, itemId, file })
    photoAdds.value.push({ categoryId, itemId, photo: { ...res, pending: true } })
    applyLocalEdits()
    ElMessage.success('已上传，保存后生效')
  } catch (e) {
    console.error(e)
    ElMessage.error('上传失败')
  }
}

function onDeletePhoto({ categoryId, itemId, photoId }) {
  if (!editing.value) return
  const catIdx = (origin.value?.check_categories || []).findIndex(x => String(x.category_id) === String(categoryId))
  const itemIdx = (origin.value?.check_categories?.[catIdx]?.items || []).findIndex(x => String(x.item_id) === String(itemId))
  const photos = origin.value?.check_categories?.[catIdx]?.items?.[itemIdx]?.photos || []
  const idx = photos.findIndex(p => String(p.id) === String(photoId))
  if (idx >= 0) {
    photoDeletes.value.push({ categoryId, itemId, photoId, photoIndex: idx })
    applyLocalEdits()
  } else {
    // 如果是刚刚新增未保存的，直接从待新增列表移除
    const pendingIdx = photoAdds.value.findIndex(p => String(p.photo.id) === String(photoId))
    if (pendingIdx >= 0) {
      photoAdds.value.splice(pendingIdx, 1)
      applyLocalEdits()
    }
  }
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
</style>
