<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <h1>档案详情</h1>
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
import { surveyArchivesApi } from '@/api/surveyArchives'
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
    const res = await surveyArchivesApi.get(id)
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

const jsonPointerEscape = (s) => String(s).replaceAll('~', '~0').replaceAll('/', '~1')
const jsonPointerUnescape = (s) => String(s).replaceAll('~1', '/').replaceAll('~0', '~')

function applyLocalEdits() {
  // 将本地未保存 edits 应用到最新 content 上
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
    // 应用本地待新增的照片
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
  // 更新本地 content
  for (const c of content.value.check_categories || []) {
    if (String(c.category_id) !== String(categoryId)) continue
    for (const it of c.items || []) {
      if (String(it.item_id) !== String(itemId)) continue
      if (!it.values) it.values = {}
      it.values[fieldId] = value
    }
  }
  // 记录差异（JSON Patch replace）
  // 通过索引定位，为简化前端生成，后端会做整体Patch应用
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
    // 字段变更（replace）
    for (const [path, value] of edits.entries()) {
      patchOps.push({ op: 'replace', path, value })
    }
    // 照片新增（add 到数组末尾）
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
    // 照片删除（按原始内容中的索引 remove）
    for (const rec of photoDeletes.value) {
      const { categoryId, itemId, photoId } = rec
      const catIndex = (origin.value?.check_categories || []).findIndex(x => String(x.category_id) === String(categoryId))
      const itemIndex = (origin.value?.check_categories?.[catIndex]?.items || []).findIndex(x => String(x.item_id) === String(itemId))
      if (catIndex >= 0 && itemIndex >= 0) {
        const photos = origin.value.check_categories[catIndex].items[itemIndex].photos || []
        const idx = photos.findIndex(p => String(p.id) === String(photoId))
        if (idx >= 0) {
          const path = `/check_categories/${catIndex}/items/${itemIndex}/photos/${idx}`
          patchOps.push({ op: 'remove', path })
        }
      }
    }
    if (patchOps.length === 0) {
      ElMessage.info('没有更改')
      return
    }
    
    await surveyArchivesApi.patch(id, patchOps, archive.value.current_version, '前端编辑')
    ElMessage.success('已保存')
    edits.clear()
    photoAdds.value = []
    photoDeletes.value = []
    await load()
    editing.value = false
  } catch (e) {
    console.error(e)
    if (String(e?.response?.status) === '409') {
      ElMessageBox.confirm('版本已更新，是否刷新后重试？', '提示').then(load).catch(() => {})
    } else {
      ElMessage.error('保存失败')
    }
  } finally {
    saving.value = false
  }
}

async function loadHistory() {
  try {
    historyLoading.value = true
    const res = await surveyArchivesApi.history(id)
    history.value = Array.isArray(res) ? res : []
  } catch (e) {
    console.error(e)
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

function formatDate(v) { return v ? new Date(v).toLocaleString() : '-' }

async function onUploadPhoto({ categoryId, itemId, file }) {
  try {
    if (!editing.value) return
    const res = await surveyArchivesApi.uploadTempPhoto(id, { category_id: categoryId, item_id: itemId, file })
    const photo = {
      id: res.id || res.temp_id,
      file_path: res.file_path,
      file_size: res.file_size,
      mime_type: res.mime_type,
      hash_value: res.hash_value,
      uploaded_by: res.uploaded_by,
      taken_at: res.taken_at || null,
      pending: true,
    }
    // 前端插入预览
    const catIdx = (content.value?.check_categories || []).findIndex(x => String(x.category_id) === String(categoryId))
    const itemIdx = (content.value?.check_categories?.[catIdx]?.items || []).findIndex(x => String(x.item_id) === String(itemId))
    if (catIdx >= 0 && itemIdx >= 0) {
      const photos = content.value.check_categories[catIdx].items[itemIdx].photos || (content.value.check_categories[catIdx].items[itemIdx].photos = [])
      photos.push(photo)
    }
    // 记录待提交的新增
    photoAdds.value.push({ categoryId, itemId, photo })
    ElMessage.success('已上传，待保存后生效')
  } catch (e) {
    console.error(e)
    ElMessage.error('上传失败')
  }
}

async function onDeletePhoto({ photoId, photo }) {
  try {
    if (!editing.value) return
    // 如果是本次会话内新增的 pending 照片，直接从本地移除并移出待新增列表
    const isPending = photo && (photo.pending || String(photo.id || '').startsWith('temp-'))
    if (isPending) {
      // 从本地 content 移除
      for (const c of content.value?.check_categories || []) {
        for (const it of c.items || []) {
          if (!Array.isArray(it.photos)) continue
          const idx = it.photos.findIndex(p => String(p.id) === String(photoId))
          if (idx >= 0) it.photos.splice(idx, 1)
        }
      }
      // 从待新增队列移除
      const i = photoAdds.value.findIndex(x => String(x.photo?.id) === String(photoId))
      if (i >= 0) photoAdds.value.splice(i, 1)
      ElMessage.success('已移除未保存的照片')
      return
    }
    // 否则标记为待删除（真正保存时再生成 patch）并从本地视图移除
    for (const c of content.value?.check_categories || []) {
      for (const it of c.items || []) {
        if (!Array.isArray(it.photos)) continue
        const idx = it.photos.findIndex(p => String(p.id) === String(photoId))
        if (idx >= 0) {
          photoDeletes.value.push({ categoryId: c.category_id, itemId: it.item_id, photoId })
          it.photos.splice(idx, 1)
          break
        }
      }
    }
    ElMessage.success('已标记删除，保存后生效')
  } catch (e) {
    console.error(e)
    ElMessage.error('删除失败')
  }
}

onMounted(load)
onMounted(loadHistory)

function startEdit() {
  // 仅在按钮可见时可触发，此处不再重复权限判断
  editing.value = true
  try { console.debug('[ArchiveDetail] Enter edit mode') } catch (_) {}
}

async function cancelEdit() {
  if (edits.size > 0) {
    try {
      await ElMessageBox.confirm('放弃未保存的修改？', '提示', { type: 'warning' })
    } catch (e) {
      return
    }
  }
  // 还原并退出编辑
  content.value = safeClone(origin.value)
  edits.clear()
  photoAdds.value = []
  photoDeletes.value = []
  editing.value = false
  try { console.debug('[ArchiveDetail] Cancel edit and restore content') } catch (_) {}
}

function goBack() {
  router.back()
}
</script>

<style scoped>
.page { padding: 16px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.meta { display: grid; grid-template-columns: repeat(2, minmax(240px, 1fr)); gap: 8px; margin-bottom: 12px; }
.hist-lines { margin: 0; padding-left: 18px; }
.hist-lines li { list-style: disc; line-height: 1.6; }
.muted { color: #999; }
</style>
