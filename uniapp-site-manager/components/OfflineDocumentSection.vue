<template>
  <view class="offline-doc">
    <view v-if="showHeader" class="offline-doc__head">
      <view class="offline-doc__head-left">
        <text class="offline-doc__title">{{ $t('stock.offlineDocTitle') }}</text>
        <text class="offline-doc__optional">{{ $t('common.optional') }}</text>
      </view>
      <text class="offline-doc__hint">{{ $t('stock.offlineDocActiveTip') }}</text>
    </view>

    <view v-if="activeDoc" class="offline-doc__active">
      <view class="offline-doc__row">
        <text class="offline-doc__label">{{ $t('stock.offlineDocUseThisTime') }}</text>
        <switch
          :checked="useThisTime"
          :disabled="disabled"
          @change="onUseChange"
          color="#2563eb"
        />
      </view>

      <view v-if="activeDoc.remark" class="offline-doc__remark">
        <text class="offline-doc__remark-k">{{ $t('common.info') }}:</text>
        <text class="offline-doc__remark-v">{{ activeDoc.remark }}</text>
      </view>

      <view class="offline-doc__grid">
        <view
          v-for="(p, idx) in activeDoc.photos"
          :key="p.id || `${p.file_path}-${idx}`"
          class="offline-doc__item"
        >
          <image class="offline-doc__img" :src="buildImageUrl(p.file_path)" mode="aspectFill" @click="preview(idx)" />
        </view>
      </view>

      <view v-if="!disabled" class="offline-doc__actions">
        <button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="uploading" @click="openReplace">
          {{ $t('stock.offlineDocReplace') }}
        </button>
        <button class="u-btn u-btn-ghost u-btn-sm u-pressable" :disabled="uploading" @click="clearCurrent">
          {{ $t('common.clear') }}
        </button>
      </view>

      <text class="offline-doc__tip">{{ $t('stock.offlineDocTip', { max }) }}</text>

      <view v-if="replaceVisible" class="offline-doc__replace">
        <input
          class="offline-doc__remark-input"
          v-model="draftRemark"
          :placeholder="$t('stock.offlineDocRemarkPlaceholder')"
          :disabled="disabled || uploading"
          maxlength="500"
        />
        <DocumentPhotoPicker v-model="draftPhotos" :max="max" :disabled="disabled || uploading" :showHeader="false" />
        <view class="offline-doc__replace-actions">
          <button
            class="u-btn u-btn-primary u-btn-sm u-pressable"
            :disabled="disabled || uploading || draftPhotos.length === 0"
            @click="createAndUpload"
          >
            {{ uploading ? $t('messages.uploadingPhoto') : $t('stock.offlineDocSetCurrent') }}
          </button>
          <button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="disabled || uploading" @click="closeReplace">
            {{ $t('common.cancel') }}
          </button>
        </view>
      </view>
    </view>

    <view v-else class="offline-doc__empty">
      <text class="offline-doc__empty-text">{{ $t('stock.offlineDocNoActive') }}</text>

      <view class="offline-doc__create">
        <input
          class="offline-doc__remark-input"
          v-model="draftRemark"
          :placeholder="$t('stock.offlineDocRemarkPlaceholder')"
          :disabled="disabled || uploading"
          maxlength="500"
        />
        <DocumentPhotoPicker v-model="draftPhotos" :max="max" :disabled="disabled || uploading" :showHeader="false" />
        <button
          class="u-btn u-btn-primary u-btn-sm u-pressable"
          :disabled="disabled || uploading || draftPhotos.length === 0"
          @click="createAndUpload"
        >
          {{ uploading ? $t('messages.uploadingPhoto') : $t('stock.offlineDocSetCurrent') }}
        </button>
      </view>
    </view>
  </view>
</template>

<script setup>
  import { computed, getCurrentInstance, onMounted, ref, watch } from 'vue'
  import { buildApiUrl, buildImageUrl, createRequestConfig, getAuthHeaders } from '@/config/api.js'
  import { useUserStore } from '@/stores/user'
  import { useOfflineDocumentStore } from '@/stores/offlineDocument'

  const props = defineProps({
    modelValue: {
      type: String,
      default: null,
    },
    max: {
      type: Number,
      default: 10,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    showHeader: {
      type: Boolean,
      default: true,
    },
  })

  const emit = defineEmits(['update:modelValue'])

  const userStore = useUserStore()
  const offlineDocStore = useOfflineDocumentStore()
  const { appContext } = getCurrentInstance()
  const { $t } = appContext.config.globalProperties

  const activeDoc = computed(() => offlineDocStore.activeDoc)
  const useThisTime = ref(true)

  const replaceVisible = ref(false)
  const uploading = ref(false)
  const draftRemark = ref('')
  const draftPhotos = ref([])

  const syncModelValue = () => {
    const doc = activeDoc.value
    const next = useThisTime.value && doc ? doc.id : null
    emit('update:modelValue', next)
  }

  const onUseChange = (e) => {
    useThisTime.value = !!e?.detail?.value
    syncModelValue()
  }

  const clearCurrent = () => {
    offlineDocStore.clear()
    useThisTime.value = false
    replaceVisible.value = false
    draftRemark.value = ''
    draftPhotos.value = []
    syncModelValue()
  }

  const preview = (idx) => {
    const doc = activeDoc.value
    if (!doc?.photos?.length) return
    const urls = doc.photos.map(p => buildImageUrl(p.file_path)).filter(Boolean)
    if (!urls.length) return
    const i = Math.max(0, Math.min(Number(idx) || 0, urls.length - 1))
    uni.previewImage({ urls, current: urls[i] })
  }

  const safeParseJson = (raw) => {
    try {
      if (raw == null) return null
      if (typeof raw === 'object') return raw
      const s = String(raw || '').trim()
      if (!s) return null
      return JSON.parse(s)
    } catch (e) {
      return null
    }
  }

  const createAndUpload = async () => {
    if (!userStore.token) return
    if (uploading.value) return
    if (!draftPhotos.value.length) return

    uploading.value = true
    try {
      // 1) create document
      const createRes = await uni.request({
        url: buildApiUrl('/api/stock/offline-documents'),
        ...createRequestConfig({
          method: 'POST',
          headers: getAuthHeaders(userStore.token),
          data: {
            remark: String(draftRemark.value || '').trim(),
          }
        })
      })

      if (createRes.statusCode === 401) {
        userStore.logout()
        return
      }
      if (createRes.statusCode !== 200) {
        const msg = createRes.data?.detail || createRes.data?.message || $t('messages.operationFailed')
        uni.showToast({ title: String(msg), icon: 'none' })
        return
      }

      const docId = String(createRes.data?.id || '').trim()
      if (!docId) {
        uni.showToast({ title: $t('messages.operationFailed'), icon: 'none' })
        return
      }

      // 2) upload photos
      const photos = []
      let failed = 0
      uni.showLoading({ title: $t('messages.uploadingPhoto') })
      try {
        for (const fp of (draftPhotos.value || [])) {
          const filePath = String(fp || '').trim()
          if (!filePath) continue
          const up = await uni.uploadFile({
            url: buildApiUrl(`/api/stock/offline-documents/${encodeURIComponent(docId)}/photos`),
            filePath,
            name: 'file',
            header: getAuthHeaders(userStore.token),
          })
          if (up.statusCode === 200) {
            const data = safeParseJson(up.data)
            if (data?.file_path) photos.push(data)
            continue
          }
          failed += 1
        }
      } finally {
        uni.hideLoading()
      }

      if (!photos.length) {
        uni.showToast({ title: $t('messages.photoUploadFailed'), icon: 'none' })
        return
      }

      offlineDocStore.setCurrent({
        id: docId,
        remark: String(createRes.data?.remark || '').trim(),
        photos,
      })

      useThisTime.value = true
      replaceVisible.value = false
      draftRemark.value = ''
      draftPhotos.value = []
      syncModelValue()

      if (failed > 0) uni.showToast({ title: $t('messages.photoUploadFailed'), icon: 'none' })
      else uni.showToast({ title: $t('messages.uploadSuccess'), icon: 'success' })
    } catch (e) {
      console.error('创建/上传线下票据失败:', e)
      uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
    } finally {
      uploading.value = false
    }
  }

  const openReplace = () => {
    if (disabled || uploading.value) return
    replaceVisible.value = true
    draftRemark.value = String(activeDoc.value?.remark || '').trim()
    draftPhotos.value = []
  }

  const closeReplace = () => {
    replaceVisible.value = false
    draftRemark.value = ''
    draftPhotos.value = []
  }

  watch(activeDoc, (doc) => {
    useThisTime.value = !!doc
    syncModelValue()
  }, { immediate: true })

  onMounted(() => {
    offlineDocStore.hydrate()
  })
</script>

<style scoped lang="scss">
  .offline-doc { display: flex; flex-direction: column; gap: 10px; }

  .offline-doc__head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
  .offline-doc__head-left { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
  .offline-doc__title { font-size: 13px; font-weight: 900; color: var(--text-primary); }
  .offline-doc__optional { font-size: 11px; color: var(--text-secondary); }
  .offline-doc__hint { font-size: 11px; color: var(--text-secondary); text-align: right; }

  .offline-doc__row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 0; }
  .offline-doc__label { font-size: 12px; font-weight: 800; color: var(--text-primary); }

  .offline-doc__remark { font-size: 12px; color: var(--text-secondary); display: flex; gap: 6px; }
  .offline-doc__remark-k { color: var(--text-secondary); }
  .offline-doc__remark-v { color: var(--text-primary); }

  .offline-doc__grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
  .offline-doc__item { border-radius: 12px; overflow: hidden; border: 1px solid rgba(229, 231, 235, 0.9); height: 74px; background: rgba(255, 255, 255, 0.9); }
  .offline-doc__img { width: 100%; height: 100%; }

  .offline-doc__actions { display: flex; gap: 10px; margin-top: 6px; }
  .offline-doc__tip { font-size: 11px; color: var(--text-secondary); }

  .offline-doc__replace { margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
  .offline-doc__replace-actions { display: flex; gap: 10px; }

  .offline-doc__empty-text { font-size: 12px; color: var(--text-secondary); }
  .offline-doc__create { display: flex; flex-direction: column; gap: 10px; }
  .offline-doc__remark-input {
    height: 36px;
    border-radius: 12px;
    border: 1px solid var(--border-color);
    padding: 0 12px;
    font-size: 13px;
    background: rgba(255, 255, 255, 0.92);
    color: var(--text-primary);
  }
</style>
