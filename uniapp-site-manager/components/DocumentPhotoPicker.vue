<template>
  <view class="doc-picker">
    <view v-if="showHeader" class="doc-picker__head">
      <view class="doc-picker__head-left">
        <text class="doc-picker__title">{{ titleText }}</text>
        <text v-if="optional" class="doc-picker__optional">{{ $t('common.optional') }}</text>
      </view>
      <text class="doc-picker__count mono">{{ currentCount }}/{{ max }}</text>
    </view>

    <view class="doc-picker__grid">
      <view
        v-for="(p, idx) in safeList"
        :key="`${p}-${idx}`"
        class="doc-picker__item"
      >
        <image
          class="doc-picker__img"
          :src="buildImageUrl(p)"
          mode="aspectFill"
          @click="preview(idx)"
        />
        <view v-if="!disabled" class="doc-picker__remove u-pressable" @click.stop="remove(idx)">×</view>
      </view>

      <view
        v-if="!disabled && currentCount < max"
        class="doc-picker__add u-pressable-subtle"
        @click="choose"
      >
        <uni-icons type="camera" size="22" color="#2563eb" />
        <text class="doc-picker__add-text">{{ $t('stock.offlineDocAdd') }}</text>
      </view>
    </view>

    <text class="doc-picker__tip">{{ $t('stock.offlineDocTip', { max }) }}</text>
  </view>
</template>

<script setup>
  import { computed, getCurrentInstance } from 'vue'
  import { buildImageUrl } from '@/config/api.js'

  const props = defineProps({
    modelValue: {
      type: Array,
      default: () => [],
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
    optional: {
      type: Boolean,
      default: true,
    },
    title: {
      type: String,
      default: '',
    },
    sourceType: {
      type: Array,
      default: () => ['camera', 'album'],
    },
  })

  const emit = defineEmits(['update:modelValue'])

  const { appContext } = getCurrentInstance()
  const { $t } = appContext.config.globalProperties

  const safeList = computed(() => (Array.isArray(props.modelValue) ? props.modelValue.filter(Boolean) : []))
  const currentCount = computed(() => safeList.value.length)
  const titleText = computed(() => String(props.title || $t('stock.offlineDocTitle')))

  const choose = async () => {
    if (props.disabled) return
    const remaining = Math.max(0, Number(props.max || 0) - currentCount.value)
    if (remaining <= 0) {
      uni.showToast({ title: $t('stock.offlineDocLimit', { max: props.max }), icon: 'none' })
      return
    }

    try {
      const res = await uni.chooseImage({
        count: remaining,
        sizeType: ['compressed'],
        sourceType: props.sourceType,
      })
      const paths = Array.isArray(res?.tempFilePaths) ? res.tempFilePaths.map(p => String(p || '').trim()).filter(Boolean) : []
      if (!paths.length) return
      emit('update:modelValue', safeList.value.concat(paths).slice(0, props.max))
    } catch (e) {
      // 用户取消选择无需提示
    }
  }

  const remove = (idx) => {
    if (props.disabled) return
    const list = safeList.value.slice()
    list.splice(Number(idx) || 0, 1)
    emit('update:modelValue', list)
  }

  const preview = (idx) => {
    const urls = safeList.value.map(p => buildImageUrl(p)).filter(Boolean)
    if (!urls.length) return
    const i = Math.max(0, Math.min(Number(idx) || 0, urls.length - 1))
    uni.previewImage({ urls, current: urls[i] })
  }
</script>

<style scoped lang="scss">
  .doc-picker {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .doc-picker__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .doc-picker__head-left {
    display: flex;
    align-items: baseline;
    gap: 8px;
    min-width: 0;
  }

  .doc-picker__title {
    font-size: 13px;
    font-weight: 900;
    color: var(--text-primary);
  }

  .doc-picker__optional {
    font-size: 11px;
    color: var(--text-secondary);
  }

  .doc-picker__count {
    font-size: 12px;
    font-weight: 900;
    color: var(--text-secondary);
  }

  .doc-picker__grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
  }

  .doc-picker__item {
    position: relative;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(229, 231, 235, 0.9);
    background: rgba(255, 255, 255, 0.9);
    height: 74px;
  }

  .doc-picker__img {
    width: 100%;
    height: 100%;
  }

  .doc-picker__remove {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 20px;
    height: 20px;
    border-radius: 10px;
    background: rgba(17, 24, 39, 0.65);
    color: #fff;
    font-size: 16px;
    font-weight: 900;
    display: flex;
    align-items: center;
    justify-content: center;
    line-height: 1;
  }

  .doc-picker__add {
    border-radius: 12px;
    border: 1px dashed rgba(37, 99, 235, 0.45);
    background: rgba(37, 99, 235, 0.06);
    height: 74px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }

  .doc-picker__add-text {
    font-size: 11px;
    color: #2563eb;
    font-weight: 800;
  }

  .doc-picker__tip {
    font-size: 11px;
    color: var(--text-secondary);
  }

  .mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  }
</style>

