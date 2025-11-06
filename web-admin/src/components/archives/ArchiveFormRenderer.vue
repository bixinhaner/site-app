<template>
  <div class="renderer">
    <div v-for="cat in content.check_categories || []" :key="cat.category_id" class="cat">
      <h3>{{ cat.category_name || cat.category_id }}</h3>
      <el-card v-for="it in cat.items || []" :key="`${cat.category_id}-${it.item_id}`" class="item">
        <div class="item-header">
          <strong>{{ it.item_name || it.item_id }}</strong>
          <small class="muted">{{ it.required_type }}</small>
        </div>
        <div class="fields">
          <div v-for="fd in (it.fields || [])" :key="fd.field_id" class="field">
            <label>{{ fd.label || fd.field_id }}</label>
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
            />
          </div>
        </div>
        <div class="photos">
          <div class="photos-header">照片</div>
          <div class="grid">
            <div v-for="p in (it.photos || [])" :key="p.id" class="item">
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
          <div class="upload-bar" v-if="!disabled">
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

const props = defineProps({
  content: { type: Object, required: true },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['change', 'upload-photo', 'delete-photo'])

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

function fileUrl(filePath) {
  if (!filePath) return ''
  const s = String(filePath)
  if (/^https?:\/\//i.test(s) || s.startsWith('data:')) return s
  if (s.startsWith('uploads/')) return `${config.API_BASE_URL}/${s}`
  if (s.startsWith('/uploads/')) return `${config.API_BASE_URL}${s}`
  return `${config.API_BASE_URL}/${s.replace(/^\//, '')}`
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
.item { margin-bottom: 12px; }
.item-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.fields { display: grid; grid-template-columns: repeat(2, minmax(260px, 1fr)); gap: 8px 16px; }
.field label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
.photos { margin-top: 8px; }
.upload-bar { margin-top: 8px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.item { border: 1px solid #eee; border-radius: 10px; overflow: hidden; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.item .el-image { width: 100%; height: auto; aspect-ratio: 4 / 3; }
.item { position: relative; }
.badge-pending { position: absolute; top: 8px; right: 8px; pointer-events: none; }
.meta { display:flex; justify-content: flex-end; align-items:center; padding:6px 8px; font-size:12px; background:#fafafa; }
.meta.compact { gap: 8px; }
.muted { color: #999; font-weight: normal; }
</style>
