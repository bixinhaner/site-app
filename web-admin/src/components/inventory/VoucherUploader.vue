<template>
  <div class="voucher-uploader">
    <div class="tiles">
      <div v-for="(f, idx) in files" :key="f.key" class="tile" :class="{ error: f.status === 'error' }">
        <template v-if="f.isPdf">
          <a v-if="f.url" class="pdf" :href="f.url" target="_blank" rel="noopener" :title="f.name">
            <el-icon :size="26"><Document /></el-icon>
            <span class="pdf-name">{{ f.name }}</span>
          </a>
          <div v-else class="pdf">
            <el-icon :size="26"><Document /></el-icon>
            <span class="pdf-name">{{ f.name }}</span>
          </div>
        </template>
        <el-image
          v-else
          class="thumb"
          :src="f.url"
          fit="cover"
          :preview-src-list="imageUrls"
          :initial-index="imageIndex(idx)"
          preview-teleported
        />
        <div v-if="f.status === 'uploading'" class="mask">
          <el-icon class="is-loading"><Loading /></el-icon>
        </div>
        <div v-else-if="f.status === 'error'" class="mask err" :title="f.error">
          {{ t('quickOut.voucherUploadFailed') }}
        </div>
        <button v-if="!disabled && f.status !== 'uploading'" type="button" class="remove" @click="removeFile(f)">
          <el-icon><Close /></el-icon>
        </button>
      </div>

      <el-upload
        v-if="!disabled && files.length < max"
        class="tile add"
        drag
        multiple
        :show-file-list="false"
        :accept="ACCEPT"
        :http-request="onHttpRequest"
      >
        <el-icon :size="22"><Plus /></el-icon>
        <div class="add-text">{{ t('quickOut.voucherAdd') }}</div>
      </el-upload>
    </div>

    <el-input
      v-model="remark"
      class="remark"
      :disabled="disabled"
      :placeholder="t('quickOut.voucherNoPlaceholder')"
      maxlength="100"
      clearable
      @change="saveRemark"
    />
    <div class="tip">{{ t('quickOut.voucherTip', { max }) }}</div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { stockApi } from '../../api/stock'
import { resolveImageUrl } from '../../utils/imageLoader'

// 出库凭证（三签单）：选中/拖入/粘贴即上传到同一张线下票据；v-model 为票据 id（至少 1 个文件上传成功才有值）
const props = defineProps({
  modelValue: { type: String, default: null },
  disabled: { type: Boolean, default: false },
  max: { type: Number, default: 10 },
  // 页面可见时监听 Ctrl+V 粘贴截图
  listenPaste: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue', 'change'])
const { t } = useI18n()

const ACCEPT = '.jpg,.jpeg,.png,.pdf'
const MAX_BYTES = 10 * 1024 * 1024

const docId = ref(null)
const remark = ref('')
const files = ref([])
let creating = null
let seq = 0

const imageFiles = computed(() => files.value.filter((f) => !f.isPdf && f.url))
const imageUrls = computed(() => imageFiles.value.map((f) => f.url))
const imageIndex = (idx) => Math.max(0, imageFiles.value.indexOf(files.value[idx]))
const doneCount = computed(() => files.value.filter((f) => f.status === 'done').length)
const uploading = computed(() => files.value.some((f) => f.status === 'uploading'))

const sync = () => {
  const id = doneCount.value > 0 ? docId.value : null
  if (id !== props.modelValue) emit('update:modelValue', id)
  emit('change', { id, count: doneCount.value, uploading: uploading.value })
}

const ensureDoc = async () => {
  if (docId.value) return docId.value
  if (!creating) {
    creating = stockApi
      .createOfflineDocument({ remark: remark.value.trim() })
      .then((res) => {
        docId.value = res.id
        return res.id
      })
      .finally(() => {
        creating = null
      })
  }
  return creating
}

const extractError = (error) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return detail?.message || error?.message || t('quickOut.voucherUploadFailed')
}

const isPdfFile = (file) => /\.pdf$/i.test(file?.name || '') || file?.type === 'application/pdf'

const addFile = async (raw) => {
  if (!raw) return
  if (!/\.(jpe?g|png|pdf)$/i.test(raw.name || '') && !/^image\/(png|jpe?g)$/.test(raw.type || '')) {
    ElMessage.warning(t('quickOut.voucherTypeInvalid'))
    return
  }
  if (raw.size > MAX_BYTES) {
    ElMessage.warning(t('quickOut.voucherTooLarge'))
    return
  }
  if (files.value.length >= props.max) {
    ElMessage.warning(t('quickOut.voucherLimit', { max: props.max }))
    return
  }
  // 粘贴的截图没有扩展名，补一个，后端按扩展名校验
  const file = /\.[a-z]+$/i.test(raw.name || '') ? raw : new File([raw], `paste-${Date.now()}.png`, { type: raw.type })
  const pdf = isPdfFile(file)
  const entry = {
    key: `f${++seq}`,
    name: file.name,
    isPdf: pdf,
    url: pdf ? '' : URL.createObjectURL(file),
    status: 'uploading',
    id: null,
    error: '',
  }
  files.value.push(entry)
  sync()
  const row = files.value.find((x) => x.key === entry.key) // 取响应式代理，多文件并发上传时互不干扰
  try {
    const id = await ensureDoc()
    const res = await stockApi.uploadOfflineDocumentPhoto(id, file)
    if (row.url) URL.revokeObjectURL(row.url)
    row.id = res.id
    row.url = resolveImageUrl(res.file_path)
    row.status = 'done'
  } catch (error) {
    row.status = 'error'
    row.error = extractError(error)
    ElMessage.error(row.error)
  } finally {
    sync()
  }
}

const onHttpRequest = ({ file }) => addFile(file)

const removeFile = async (f) => {
  if (f.id && docId.value) {
    try {
      await stockApi.deleteOfflineDocumentPhoto(docId.value, f.id)
    } catch (error) {
      ElMessage.error(extractError(error))
      return
    }
  }
  if (f.url?.startsWith('blob:')) URL.revokeObjectURL(f.url)
  files.value = files.value.filter((x) => x !== f)
  sync()
}

const saveRemark = async () => {
  if (!docId.value) return // 尚未上传文件：创建票据时一并带上
  try {
    await stockApi.updateOfflineDocument(docId.value, { remark: remark.value.trim() })
  } catch (error) {
    ElMessage.error(extractError(error))
  }
}

const onPaste = (e) => {
  if (props.disabled || !props.listenPaste) return
  const pasted = Array.from(e.clipboardData?.files || [])
  if (!pasted.length) return // 纯文本（如粘贴 SN）交给输入框处理
  e.preventDefault()
  pasted.forEach(addFile)
}

const reset = () => {
  files.value.forEach((f) => f.url?.startsWith('blob:') && URL.revokeObjectURL(f.url))
  files.value = []
  docId.value = null
  remark.value = ''
  sync()
}

onMounted(() => document.addEventListener('paste', onPaste))
onBeforeUnmount(() => {
  document.removeEventListener('paste', onPaste)
  files.value.forEach((f) => f.url?.startsWith('blob:') && URL.revokeObjectURL(f.url))
})

defineExpose({ reset, uploading, doneCount })
</script>

<style scoped>
.tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.tile {
  position: relative;
  width: 104px;
  height: 104px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-lighter);
}
.tile.error {
  border-color: var(--el-color-danger);
}
.thumb {
  width: 100%;
  height: 100%;
}
.pdf {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 8px;
  color: var(--el-color-danger);
  text-decoration: none;
}
.pdf-name {
  width: 100%;
  font-size: 11px;
  color: var(--el-text-color-regular);
  text-align: center;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.7);
  font-size: 12px;
}
.mask.err {
  color: var(--el-color-danger);
  background: rgba(254, 240, 240, 0.85);
}
.remove {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: rgba(0, 0, 0, 0.45);
  cursor: pointer;
}
.tile.add {
  border: none;
  background: transparent;
}
.tile.add :deep(.el-upload),
.tile.add :deep(.el-upload-dragger) {
  width: 104px;
  height: 104px;
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border-radius: 10px;
  color: var(--el-text-color-secondary);
}
.add-text {
  font-size: 11px;
  line-height: 1.3;
  white-space: nowrap;
  text-align: center;
  padding: 0 6px;
}
.remark {
  margin-top: 10px;
  max-width: 360px;
}
.tip {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
