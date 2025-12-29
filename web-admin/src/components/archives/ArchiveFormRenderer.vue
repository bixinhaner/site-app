<template>
  <div class="renderer" :class="{ 'renderer--template': variant === 'template' }">
    <div v-for="cat in content.check_categories || []" :key="cat.category_id" class="cat">
      <h3 class="cat-title">
        <span class="cat-name">{{ cat.category_name || cat.category_id }}</span>
        <el-tag
          v-if="variant === 'template'"
          size="small"
          effect="light"
          :type="levelTagType(cat)"
        >
          {{ levelLabel(cat) }}
        </el-tag>
      </h3>
      <div v-if="variant === 'template' && cat.description" class="cat-desc">
        {{ cat.description }}
      </div>
      <el-card v-for="it in cat.items || []" :key="`${cat.category_id}-${it.item_id}`" class="item">
        <div class="item-header">
          <div class="item-title">
            <strong>{{ displayItemName(it) }}</strong>
            <el-tag v-if="it.required_type" size="small" effect="plain">{{ requiredTypeLabel(it.required_type) }}</el-tag>
            <el-tag
              v-if="variant === 'template'"
              size="small"
              effect="plain"
              :type="levelTagType(cat)"
            >
              {{ levelLabel(cat) }}
            </el-tag>
          </div>
          <template v-if="it.description">
            <div v-if="variant === 'template'" class="desc-block" role="note" aria-label="检查说明">
              <div class="desc-block__title">
                <el-icon><InfoFilled /></el-icon>
                <span>检查说明</span>
              </div>
              <div class="desc-block__content">{{ it.description }}</div>
            </div>
            <div v-else class="item-desc">{{ it.description }}</div>
          </template>
        </div>

        <!-- 站点级字段 -->
        <div v-if="(it.fields || []).length" class="fields">
          <div v-for="fd in (it.fields || [])" :key="fd.field_id" class="field">
            <label class="field-label">
              <span class="field-label__text">{{ fd.label || fd.field_id }}</span>
              <el-popover
                v-if="String(fd?.help_text || '').trim()"
                placement="top-start"
                trigger="click"
                width="360"
                :title="`${fd.label || fd.field_id} 描述/注意事项`"
              >
                <template #reference>
                  <el-icon class="field-help-icon" :title="`${fd.label || fd.field_id} 描述/注意事项`">
                    <QuestionFilled />
                  </el-icon>
                </template>
                <div class="field-help-text">{{ fd.help_text }}</div>
              </el-popover>
            </label>
            <!-- number -->
            <el-input-number
              v-if="(fd.type || 'text').toLowerCase() === 'number'"
              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :min="fd?.constraints?.min"
              :max="fd?.constraints?.max"
              :disabled="disabled"
            />
            <!-- boolean -->
            <el-switch
              v-else-if="(fd.type || 'text').toLowerCase() === 'boolean'"
              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :disabled="disabled"
            />
            <!-- select (single) -->
            <el-select
              v-else-if="(fd.type || 'text').toLowerCase() === 'select_single'"
              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :disabled="disabled"
            >
              <el-option v-for="o in (fd?.options || [])" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <!-- select (multi) -->
            <el-select
              v-else-if="(fd.type || 'text').toLowerCase() === 'select_multi'"
              multiple
              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :disabled="disabled"
            >
              <el-option v-for="o in (fd?.options || [])" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <!-- date/time/datetime -->
            <el-date-picker
              v-else-if="['date','time','datetime'].includes((fd.type || '').toLowerCase())"
              :type="(fd.type || 'date').toLowerCase()"
              :value-format="dateValueFormat(fd.type)"
              :format="dateDisplayFormat(fd.type)"
              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :disabled="disabled"
            />
            <!-- text/default -->
            <el-input
              v-else
              :placeholder="fd?.placeholder"
              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :disabled="disabled"
              :maxlength="fd?.constraints?.max_length || null"
              :minlength="fd?.constraints?.min_length || null"
              show-word-limit
            />
          </div>
        </div>
        <!-- 扇区级数据 -->
        <div v-if="(it.sectors || []).length" class="sub-block">
          <div class="sub-title">扇区级</div>
          <div class="card-grid">
            <el-card v-for="sec in it.sectors" :key="sec.sector_id" shadow="never" class="mini-card">
              <div class="mini-header">
                <el-tag size="small" type="info">扇区 {{ sec.sector_id }}</el-tag>
              </div>
              <div class="kv-list">
                <div v-for="(v, k) in sec.values || {}" :key="k" class="kv-item">
                  <span class="kv-key">{{ fieldLabel(it, k) }}</span>
                  <span class="kv-val">{{ renderVal(v) }}</span>
                </div>
              </div>
            </el-card>
          </div>
        </div>

        <!-- 小区级数据 -->
        <div v-if="(it.cells || []).length" class="sub-block">
          <div class="sub-title">小区级</div>
          <div class="card-grid">
            <el-card v-for="cell in it.cells" :key="cell.cell_id" shadow="never" class="mini-card">
              <div class="mini-header">
                <el-tag size="small" type="success">小区 {{ cell.cell_id }}</el-tag>
                <el-tag size="small" effect="plain" style="margin-left:6px">扇区 {{ cell.sector_id }}</el-tag>
                <el-tag v-if="cell.band" size="small" effect="plain" style="margin-left:6px">Band {{ cell.band }}</el-tag>
              </div>
              <div class="kv-list">
                <div v-for="(v, k) in cell.values || {}" :key="k" class="kv-item">
                  <span class="kv-key">{{ fieldLabel(it, k) }}</span>
                  <span class="kv-val">{{ renderVal(v) }}</span>
                </div>
              </div>
            </el-card>
          </div>
        </div>

        <div class="photos" v-if="(it.photos && it.photos.length) || (!disabled && needsPhoto(it))">
          <div class="photos-header" v-if="it.photos && it.photos.length">照片</div>
          <div class="grid" v-if="it.photos && it.photos.length">
            <div v-for="p in it.photos" :key="p.id" class="item photo-card">
              <el-image :src="fileUrl(p.file_path)" :preview-src-list="[fileUrl(p.file_path)]" fit="cover" />
              <el-tag v-if="p.pending" size="small" type="warning" class="badge-pending">未保存</el-tag>
              <div class="meta compact">
                <div class="meta-actions">
                  <el-button v-if="!disabled" link type="danger" size="small"
                    @click="$emit('delete-photo', { photoId: p.id, photo: p })" title="删除" aria-label="删除">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>
            </div>
          </div>
          <div class="upload-bar" v-if="!disabled && needsPhoto(it)">
            <el-upload :show-file-list="false" :http-request="(opt) => onUpload(cat, it, opt)" accept="image/*">
              <el-button size="small" type="primary"><el-icon><Upload /></el-icon>选择图片</el-button>
            </el-upload>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'
import config from '@/config/env.js'
import { QuestionFilled } from '@element-plus/icons-vue'

const props = defineProps({
  content: { type: Object, required: true },
  disabled: { type: Boolean, default: false },
  variant: { type: String, default: 'archive' },
})
const emit = defineEmits(['change', 'upload-photo', 'delete-photo'])

const normalizeLevelType = (category) => {
  const lt = category?.level_type
  if (lt === 'cell') return 'device'
  if (!lt) {
    if (category?.cell_specific) return 'device'
    if (category?.sector_specific) return 'sector'
    return 'site'
  }
  return lt
}

const levelLabel = (category) => {
  const lt = normalizeLevelType(category)
  switch (lt) {
    case 'site':
      return '站点级'
    case 'sector':
      return '扇区级'
    case 'device':
      return '设备级'
    case 'cell_earfcn':
      return '小区级'
    default:
      return '站点级'
  }
}

const levelTagType = (category) => {
  const lt = normalizeLevelType(category)
  switch (lt) {
    case 'site':
      return 'success'
    case 'sector':
      return 'warning'
    case 'device':
      return 'info'
    case 'cell_earfcn':
      return 'danger'
    default:
      return 'success'
  }
}

const needsPhoto = (it) => {
  const t = (it?.required_type || '').toLowerCase()
  // 需要拍照：包含 photo 或 both 关键字（兼容 photo, photo_and_data, photo+data, both 等写法）
  return t.includes('photo') || t.includes('both')
}

const requiredTypeLabel = (value) => {
  const t = String(value || '').trim().toLowerCase()
  if (!t) return ''
  if (t === 'both' || t.includes('photo') && t.includes('data')) return '照片+数据'
  if (t === 'photo' || t.includes('photo')) return '照片'
  if (t === 'data' || t.includes('data')) return '数据'
  return String(value)
}

const state = reactive({ values: {} })

const buildKey = (cat, it, fd) => `${cat.category_id}.${it.item_id}.${fd.field_id}`
const ptr = (cat, it, fd) => buildKey(cat, it, fd)

function coerceBool(v) {
  if (v === true || v === false) return v
  const s = String(v ?? '').trim().toLowerCase()
  if (['1','true','yes','y','是','有'].includes(s)) return true
  if (['0','false','no','n','否','无'].includes(s)) return false
  return null
}

function coerceNumber(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(String(v).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

function coerceByType(fd, val) {
  const t = String(fd?.type || '').toLowerCase()
  if (t === 'number') return coerceNumber(val)
  if (t === 'boolean') return coerceBool(val)
  if (t === 'select_multi') {
    if (Array.isArray(val)) return val
    if (val === null || val === undefined || val === '') return []
    return [val]
  }
  // date/time/datetime 走字符串 + value-format，由控件处理
  return val
}

watch(() => props.content, (val) => {
  // 初始化局部表单值（保持同一引用，避免丢失响应性）
  for (const k of Object.keys(state.values)) delete state.values[k]
  const cats = (val?.check_categories || [])
  cats.forEach((c) => (c.items || []).forEach((it) => {
    const values = it.values || {}
    ;(it.fields || []).forEach((fd) => {
      const k = buildKey(c, it, fd)
      state.values[k] = coerceByType(fd, values[fd.field_id])
    })
  }))
}, { immediate: true })

function emitChange(cat, it, fd) {
  emit('change', { categoryId: cat.category_id, itemId: it.item_id, fieldId: fd.field_id, value: state.values[buildKey(cat, it, fd)] })
}

function isImage(mime) { return (mime || '').startsWith('image/') }

function onUpload(cat, it, opt) {
  emit('upload-photo', { categoryId: cat.category_id, itemId: it.item_id, file: opt.file })
}

function getValue(cat, it, fd) {
  const k = buildKey(cat, it, fd)
  if (Object.prototype.hasOwnProperty.call(state.values, k)) {
    return state.values[k]
  }
  const raw = (it?.values || {})[fd.field_id]
  return coerceByType(fd, raw)
}

function setValue(cat, it, fd, val) {
  if (props.disabled) return
  const k = buildKey(cat, it, fd)
  state.values[k] = val
  emitChange(cat, it, fd)
}

function fieldLabel(it, key) {
  const f = (it.fields || []).find(x => x.field_id === key)
  return (f && (f.label || f.field_id)) || key
}

function renderVal(v) {
  if (v === null || v === undefined) return '-'
  if (Array.isArray(v)) return v.join(', ')
  if (typeof v === 'object') return JSON.stringify(v)
  return v
}

function fileUrl(filePath) {
  if (!filePath) return ''
  const s = String(filePath)
  if (/^https?:\/\//i.test(s) || s.startsWith('data:')) return s
  if (s.startsWith('uploads/')) return `${config.API_BASE_URL}/${s}`
  if (s.startsWith('/uploads/')) return `${config.API_BASE_URL}${s}`
  return `${config.API_BASE_URL}/${s.replace(/^\//, '')}`
}

function displayItemName(it) {
  const name = it.item_name || it.item_id || ''
  if ((it.cells || []).length > 1 || (it.sectors || []).length > 1) {
    // 去掉尾部含“小区/扇区”描述，避免暗示只对应单个单元
    return name.replace(/[-\s]*小区.*$/u, '').replace(/[-\s]*扇区.*$/u, '')
  }
  return name
}

function dateValueFormat(type) {
  const t = String(type || 'date').toLowerCase()
  if (t === 'date') return 'YYYY-MM-DD'
  if (t === 'time') return 'HH:mm:ss'
  return 'YYYY-MM-DD HH:mm'
}
function dateDisplayFormat(type) {
  const t = String(type || 'date').toLowerCase()
  if (t === 'date') return 'YYYY-MM-DD'
  if (t === 'time') return 'HH:mm:ss'
  return 'YYYY-MM-DD HH:mm'
}
</script>

<style scoped>
.cat { margin-bottom: 16px; }
.item { margin-bottom: 12px; border: 1px solid #eee; border-radius: 10px; overflow: hidden; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.06); padding: 12px; }
.item-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.item-title { display: flex; align-items: center; gap: 8px; }
.fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px 16px; margin-top: 8px; }
.field label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
.field-label { display: flex; align-items: center; gap: 6px; }
.field-label__text { flex: 0 1 auto; }
.field-help-icon { cursor: pointer; color: #909399; font-size: 14px; }
.field-help-text { white-space: pre-line; line-height: 1.6; }
.sub-block { margin-top: 12px; border: 1px dashed #e4e7ed; padding: 8px; border-radius: 6px; background: #fafbfc; }
.sub-title { font-weight: 600; color: #606266; margin-bottom: 6px; }
.kv-list { display: flex; flex-direction: column; gap: 4px; }
.kv-item { display: flex; gap: 6px; font-size: 13px; line-height: 1.5; flex-wrap: wrap; }
.kv-key { color: #606266; font-weight: 600; }
.kv-val { color: #303133; }
.photos { margin-top: 12px; }
.upload-bar { margin-top: 8px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.photo-card { position: relative; border: 1px solid #f0f0f0; border-radius: 8px; overflow: hidden; background: #fff; }
.photo-card .el-image { width: 100%; height: auto; aspect-ratio: 4 / 3; }
.badge-pending { position: absolute; top: 8px; right: 8px; pointer-events: none; }
.meta { display:flex; justify-content: flex-end; align-items:center; padding:6px 8px; font-size:12px; background:#fafafa; }
.meta.compact { gap: 8px; }
.muted { color: #999; font-weight: normal; }

.cat-title {
  margin: 0 0 8px 0;
}

.renderer--template .cat-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.renderer--template .cat-desc {
  margin: -6px 0 10px 0;
  font-size: 12px;
  color: #909399;
}

.renderer--template .item {
  box-shadow: none;
  border: 1px solid #ebeef5;
  border-radius: 12px;
}

.renderer--template .item-header {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.renderer--template .fields {
  grid-template-columns: 1fr;
  gap: 10px;
}

.renderer--template .field label {
  color: #606266;
}

.renderer--template .desc-block {
  width: 100%;
  border-radius: 10px;
  padding: 10px 12px;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
}

.renderer--template .desc-block__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #606266;
  font-weight: 600;
  margin-bottom: 6px;
}

.renderer--template .desc-block__content {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
