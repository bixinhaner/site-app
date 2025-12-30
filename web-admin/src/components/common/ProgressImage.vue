<template>
  <div class="progress-image" :class="statusClass">
    <img
      v-if="status === 'loaded'"
      class="progress-image__img"
      :src="displaySrc"
      :alt="alt"
      :style="{ objectFit: fit }"
      draggable="false"
    />

    <div v-else class="progress-image__placeholder">
      <div v-if="status === 'loading'" class="progress-image__loading">
        <div class="progress-image__percent">{{ progress }}%</div>
        <div class="progress-image__bar">
          <div class="progress-image__bar-fill" :style="{ width: progress + '%' }"></div>
        </div>
      </div>

      <div v-else-if="status === 'error'" class="progress-image__error" @click.stop="retry">
        <div class="progress-image__error-text">{{ errorText }}</div>
        <div class="progress-image__error-sub">{{ retryText }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { createObjectUrl, loadImageBlob, revokeObjectUrl, resolveImageUrl } from '@/utils/imageLoader'

const props = defineProps({
  src: { type: String, default: '' },
  alt: { type: String, default: '' },
  fit: { type: String, default: 'cover' },
  errorText: { type: String, default: '加载失败' },
  retryText: { type: String, default: '点击重试' },
})

const status = ref('idle') // idle | loading | loaded | error
const progress = ref(0)
const objectUrl = ref('')
const loadToken = ref(0)

const resolvedUrl = computed(() => resolveImageUrl(props.src))

const statusClass = computed(() => {
  if (status.value === 'loading') return 'progress-image--loading'
  if (status.value === 'error') return 'progress-image--error'
  if (status.value === 'loaded') return 'progress-image--loaded'
  return 'progress-image--idle'
})

const displaySrc = computed(() => objectUrl.value || resolvedUrl.value)

const cleanupObjectUrl = () => {
  if (objectUrl.value) revokeObjectUrl(objectUrl.value)
  objectUrl.value = ''
}

const load = async () => {
  const url = resolvedUrl.value
  cleanupObjectUrl()
  progress.value = 0
  if (!url) {
    status.value = 'idle'
    return
  }

  status.value = 'loading'
  const token = ++loadToken.value

  const res = await loadImageBlob({
    url,
    onProgress: (p) => {
      if (token !== loadToken.value) return
      progress.value = p
    },
  })

  if (token !== loadToken.value) return

  if (res?.ok && res.blob) {
    progress.value = 100
    objectUrl.value = createObjectUrl(res.blob) || ''
    status.value = 'loaded'
    return
  }

  status.value = 'error'
}

const retry = async () => {
  await load()
}

watch(resolvedUrl, () => {
  load()
}, { immediate: true })

onBeforeUnmount(() => {
  cleanupObjectUrl()
})
</script>

<style scoped>
.progress-image {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  overflow: hidden;
  background: #f5f7fa;
}

.progress-image__img {
  width: 100%;
  height: 100%;
  display: block;
  user-select: none;
}

.progress-image__placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  background: rgba(245, 247, 250, 0.96);
}

.progress-image__loading {
  width: 82%;
  text-align: center;
}

.progress-image__percent {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
}

.progress-image__bar {
  margin-top: 6px;
  height: 6px;
  border-radius: 999px;
  background: #e4e7ed;
  overflow: hidden;
}

.progress-image__bar-fill {
  height: 100%;
  background: #409eff;
  width: 0;
}

.progress-image__error {
  cursor: pointer;
  text-align: center;
  padding: 0 8px;
}

.progress-image__error-text {
  font-size: 12px;
  color: #f56c6c;
  font-weight: 600;
}

.progress-image__error-sub {
  margin-top: 2px;
  font-size: 11px;
  color: #909399;
}
</style>

