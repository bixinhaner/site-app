<template>
  <view v-if="visible" class="update-dialog-mask" @click.self="handleMaskClick">
    <view class="update-dialog" :class="{ 'force-update': isForceUpdate }">
      <!-- 头部 -->
      <view class="dialog-header">
        <view class="icon-container">
          <text class="update-icon">🚀</text>
        </view>
        <text class="title">{{ i18n.newVersionFound.value }}</text>
        <text class="version">v{{ versionInfo?.version_name }}</text>
      </view>
      
      <!-- 内容 -->
      <view class="dialog-content">
        <!-- 文件大小 -->
        <view class="info-row">
          <text class="info-label">📦 {{ i18n.updateSize.value }}:</text>
          <text class="info-value">{{ formattedFileSize }}</text>
        </view>
        
        <!-- 更新日志 -->
        <view class="release-notes" v-if="releaseNotes">
          <text class="notes-title">📝 {{ i18n.releaseNotes.value }}:</text>
          <scroll-view scroll-y class="notes-content">
            <text class="notes-text">{{ releaseNotes }}</text>
          </scroll-view>
        </view>
        
        <!-- 查看详情按钮 -->
        <view class="view-details-section" v-if="showReleaseNotesLink && !isDownloading && !isDownloadComplete">
          <button class="btn-view-details" @click="handleViewDetails">
            📖 {{ i18n.viewDetails.value }}
          </button>
        </view>
        
        <!-- 下载进度 -->
        <view class="progress-section" v-if="isDownloading || isDownloadComplete">
          <view class="progress-bar-container">
            <view class="progress-bar" :style="{ width: downloadProgress + '%' }"></view>
          </view>
          <view class="progress-info">
            <text class="progress-text">{{ progressText }}</text>
            <text class="progress-percent">{{ downloadProgress }}%</text>
          </view>
        </view>
        
        <!-- 错误信息 -->
        <view class="error-section" v-if="errorMessage">
          <text class="error-text">❌ {{ errorMessage }}</text>
        </view>
      </view>
      
      <!-- 底部按钮 -->
      <view class="dialog-footer">
        <!-- 稍后提醒按钮（强制更新时隐藏） -->
        <button 
          v-if="!isForceUpdate && !isDownloading && !isDownloadComplete"
          class="btn btn-secondary"
          @click="handleLater"
        >
          {{ i18n.later.value }}
        </button>
        
        <!-- 主操作按钮 -->
        <button 
          class="btn btn-primary"
          :class="{ 'btn-full': isForceUpdate || isDownloading || isDownloadComplete }"
          :disabled="isDownloading"
          @click="handlePrimaryAction"
        >
          {{ primaryButtonText }}
        </button>
      </view>
      
      <!-- 强制更新提示 -->
      <view class="force-tip" v-if="isForceUpdate">
        <text class="tip-text">⚠️ {{ i18n.forceUpdateTip.value }}</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useUpgradeStore } from '@/stores/upgrade'
import { useLanguageStore } from '@/stores/language'
import i18nInstance from '@/utils/i18n.js'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:visible', 'close', 'installed'])

const upgradeStore = useUpgradeStore()
const languageStore = useLanguageStore()

// ============ 国际化翻译 ============
// 响应式翻译函数 - 使用 computed 确保语言切换时自动更新
const t = (key, params) => {
  return computed(() => {
    // 显式依赖 locale，确保切换语言时重新计算
    const _locale = languageStore.currentLocale
    return i18nInstance.global.t(`upgrade.${key}`, params)
  })
}

// ============ 计算属性 ============
const versionInfo = computed(() => upgradeStore.versionInfo)
const isForceUpdate = computed(() => upgradeStore.isForceUpdate)
const isDownloading = computed(() => upgradeStore.isDownloading)
const isDownloadComplete = computed(() => upgradeStore.isDownloadComplete)
const downloadProgress = computed(() => upgradeStore.downloadProgress)
const formattedFileSize = computed(() => upgradeStore.formattedFileSize)
const errorMessage = computed(() => upgradeStore.errorMessage)

// 是否显示"查看详情"按钮（根据后端配置）
const showReleaseNotesLink = computed(() => {
  return versionInfo.value?.show_release_notes === true
})

// 国际化文本（响应式）
const i18n = {
  newVersionFound: t('newVersionFound'),
  updateSize: t('updateSize'),
  releaseNotes: t('releaseNotes'),
  downloading: t('downloading'),
  downloadComplete: t('downloadComplete'),
  retry: t('retry'),
  installNow: t('installNow'),
  updateNow: t('updateNow'),
  later: t('later'),
  viewDetails: t('viewDetails'),
  forceUpdateTip: t('forceUpdateTip'),
  pleaseUpdate: t('pleaseUpdate')
}

// 更新日志（根据当前语言自动选择）
const releaseNotes = computed(() => {
  if (!versionInfo.value) return ''
  
  // 根据当前语言选择对应的更新说明
  if (languageStore.currentLocale === 'en' || languageStore.currentLocale === 'id') {
    // 英文/印尼语：优先显示英文说明，如果没有则显示中文
    return versionInfo.value.release_notes_en || versionInfo.value.release_notes || ''
  } else {
    // 中文环境：优先显示中文说明，如果没有则显示英文
    return versionInfo.value.release_notes || versionInfo.value.release_notes_en || ''
  }
})

// 进度文本（响应式）
const progressText = computed(() => {
  if (isDownloadComplete.value) return i18n.downloadComplete.value
  if (isDownloading.value) return i18n.downloading.value
  return ''
})

// 主按钮文本（响应式）
const primaryButtonText = computed(() => {
  if (errorMessage.value) return i18n.retry.value
  if (isDownloadComplete.value) return i18n.installNow.value
  if (isDownloading.value) return i18n.downloading.value
  return i18n.updateNow.value
})

// ============ 方法 ============

// 处理遮罩点击
const handleMaskClick = () => {
  if (!isForceUpdate.value && !isDownloading.value) {
    handleClose()
  }
}

// 关闭弹窗
const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

// 稍后提醒
const handleLater = () => {
  upgradeStore.skipCurrentVersion()
  handleClose()
}

// 查看详情（跳转到App内Release Notes页面）
const handleViewDetails = () => {
  if (!versionInfo.value?.id) return
  
  // 跳转到App内原生Release Notes页面
  uni.navigateTo({
    url: `/pages/release-notes/release-notes?versionId=${versionInfo.value.id}&versionName=${versionInfo.value.version_name || ''}`
  })
}

// 主操作
const handlePrimaryAction = async () => {
  if (errorMessage.value) {
    // 重试下载
    upgradeStore.retryDownload()
    return
  }
  
  if (isDownloadComplete.value) {
    // 安装
    const success = await upgradeStore.installUpdate()
    if (success) {
      emit('installed')
    }
    return
  }
  
  if (!isDownloading.value) {
    // 开始下载
    const success = await upgradeStore.startDownload()
    if (success) {
      // 下载完成后自动安装
      const installSuccess = await upgradeStore.installUpdate()
      if (installSuccess) {
        emit('installed')
      }
    }
  }
}

// 监听强制更新，阻止返回
watch(() => props.visible, (val) => {
  if (val && isForceUpdate.value) {
    // #ifdef APP-PLUS
    // 强制更新时禁用返回键
    plus.key.addEventListener('backbutton', preventBack, false)
    // #endif
  } else {
    // #ifdef APP-PLUS
    plus.key.removeEventListener('backbutton', preventBack)
    // #endif
  }
})

const preventBack = () => {
  // 强制更新时阻止返回
  if (isForceUpdate.value) {
    uni.showToast({
      title: i18n.pleaseUpdate.value,
      icon: 'none'
    })
  }
}
</script>

<style lang="scss" scoped>
.update-dialog-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 40rpx;
}

.update-dialog {
  width: 100%;
  max-width: 600rpx;
  background: #fff;
  border-radius: 24rpx;
  overflow: hidden;
  box-shadow: 0 20rpx 60rpx rgba(0, 0, 0, 0.3);
  
  &.force-update {
    border: 4rpx solid var(--color-primary, #f97316);
  }
}

.dialog-header {
  background: linear-gradient(135deg, var(--color-primary, #f97316), var(--color-primary-light, #fb923c));
  padding: 40rpx 32rpx;
  text-align: center;
  color: #fff;
  
  .icon-container {
    margin-bottom: 16rpx;
    
    .update-icon {
      font-size: 64rpx;
    }
  }
  
  .title {
    display: block;
    font-size: 36rpx;
    font-weight: 600;
    margin-bottom: 8rpx;
  }
  
  .version {
    display: block;
    font-size: 28rpx;
    opacity: 0.9;
  }
}

.dialog-content {
  padding: 32rpx;
  
  .info-row {
    display: flex;
    align-items: center;
    margin-bottom: 24rpx;
    
    .info-label {
      font-size: 28rpx;
      color: #666;
    }
    
    .info-value {
      margin-left: 12rpx;
      font-size: 28rpx;
      color: #333;
      font-weight: 500;
    }
  }
  
  .release-notes {
    margin-bottom: 24rpx;
    
    .notes-title {
      display: block;
      font-size: 28rpx;
      color: #666;
      margin-bottom: 16rpx;
    }
    
    .notes-content {
      max-height: 300rpx;
      background: #f8f9fa;
      border-radius: 12rpx;
      padding: 20rpx;
      
      .notes-text {
        font-size: 26rpx;
        color: #333;
        line-height: 1.6;
        white-space: pre-wrap;
      }
    }
  }
  
  .view-details-section {
    margin-top: 20rpx;
    text-align: center;
    
    .btn-view-details {
      display: inline-block;
      background: transparent;
      border: 2rpx solid var(--color-primary, #f97316);
      color: var(--color-primary, #f97316);
      font-size: 26rpx;
      padding: 12rpx 32rpx;
      border-radius: 32rpx;
      
      &:active {
        background: rgba(249, 115, 22, 0.1);
      }
    }
  }
  
  .progress-section {
    margin-top: 24rpx;
    
    .progress-bar-container {
      height: 16rpx;
      background: #e5e7eb;
      border-radius: 8rpx;
      overflow: hidden;
      
      .progress-bar {
        height: 100%;
        background: linear-gradient(90deg, var(--color-primary, #f97316), var(--color-primary-light, #fb923c));
        border-radius: 8rpx;
        transition: width 0.3s ease;
      }
    }
    
    .progress-info {
      display: flex;
      justify-content: space-between;
      margin-top: 12rpx;
      
      .progress-text {
        font-size: 24rpx;
        color: #666;
      }
      
      .progress-percent {
        font-size: 24rpx;
        color: var(--color-primary, #f97316);
        font-weight: 600;
      }
    }
  }
  
  .error-section {
    margin-top: 24rpx;
    padding: 20rpx;
    background: #fef2f2;
    border-radius: 12rpx;
    
    .error-text {
      font-size: 26rpx;
      color: #dc2626;
    }
  }
}

.dialog-footer {
  display: flex;
  gap: 20rpx;
  padding: 0 32rpx 32rpx;
  
  .btn {
    flex: 1;
    height: 88rpx;
    border-radius: 44rpx;
    font-size: 30rpx;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    
    &.btn-primary {
      background: linear-gradient(135deg, var(--color-primary, #f97316), var(--color-primary-light, #fb923c));
      color: #fff;
      
      &:active {
        opacity: 0.9;
      }
      
      &[disabled] {
        opacity: 0.6;
      }
      
      &.btn-full {
        flex: 1;
      }
    }
    
    &.btn-secondary {
      background: #f3f4f6;
      color: #666;
      
      &:active {
        background: #e5e7eb;
      }
    }
  }
}

.force-tip {
  padding: 16rpx 32rpx 24rpx;
  text-align: center;
  
  .tip-text {
    font-size: 24rpx;
    color: #dc2626;
  }
}
</style>
