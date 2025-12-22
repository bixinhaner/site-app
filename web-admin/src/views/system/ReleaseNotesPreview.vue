<template>
  <div class="release-notes-preview-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button @click="goBack" type="default">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <h1>Release Notes 预览</h1>
      </div>
      <div class="header-actions">
        <el-button @click="toggleLanguage" type="info">
          <el-icon><Switch /></el-icon>
          {{ currentLang === 'zh' ? '切换英文' : '切换中文' }}
        </el-button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 无数据 -->
    <div v-else-if="!releaseNote" class="empty-container">
      <el-empty description="暂无 Release Notes 数据" />
    </div>

    <!-- Release Notes 内容 -->
    <div v-else class="release-notes-container">
      <!-- 头部卡片 -->
      <el-card class="header-card">
        <div class="header-content">
          <div class="version-badge">🚀</div>
          <div class="title-section">
            <h1 class="main-title">{{ localizedTitle }}</h1>
            <p class="sub-title" v-if="localizedSubtitle">{{ localizedSubtitle }}</p>
          </div>
        </div>
        <div class="version-info">
          <el-tag type="primary" size="large">v{{ versionInfo?.version_name }}</el-tag>
          <span class="date-tag" v-if="releaseNote.created_at">
            创建于 {{ formatDate(releaseNote.created_at) }}
          </span>
        </div>
      </el-card>

      <!-- 更新项目列表 -->
      <el-card class="items-card">
        <template #header>
          <span>更新内容</span>
        </template>
        <div class="items-list">
          <div 
            v-for="(item, index) in releaseNote.items" 
            :key="item.id"
            class="update-item"
          >
            <div class="item-number">{{ index + 1 }}</div>
            <div class="item-content">
              <!-- 文字内容 -->
              <p class="item-text" v-if="getLocalizedContent(item)" v-html="formatContent(getLocalizedContent(item))"></p>
              
              <!-- 图片内容 -->
              <div class="item-image" v-if="item.image_url">
                <img 
                  :src="getFullImageUrl(item.image_url)" 
                  :alt="getLocalizedCaption(item)"
                  @error="handleImageError"
                />
                <p class="image-caption" v-if="getLocalizedCaption(item)">
                  {{ getLocalizedCaption(item) }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 底部信息 -->
      <div class="footer-info">
        <p>感谢您使用我们的应用！如有问题请联系技术支持。</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Switch } from '@element-plus/icons-vue'
import { appVersionAPI } from '@/api/appVersion'
import config from '@/config/env.js'

const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(true)
const releaseNote = ref(null)
const versionInfo = ref(null)
const currentLang = ref('zh')

// 计算属性
const localizedTitle = computed(() => {
  if (!releaseNote.value) return ''
  return currentLang.value === 'en' 
    ? (releaseNote.value.title_en || releaseNote.value.title || '')
    : (releaseNote.value.title || releaseNote.value.title_en || '')
})

const localizedSubtitle = computed(() => {
  if (!releaseNote.value) return ''
  return currentLang.value === 'en'
    ? (releaseNote.value.subtitle_en || releaseNote.value.subtitle || '')
    : (releaseNote.value.subtitle || releaseNote.value.subtitle_en || '')
})

// 方法
const goBack = () => {
  router.push('/settings/app-version')
}

const toggleLanguage = () => {
  currentLang.value = currentLang.value === 'zh' ? 'en' : 'zh'
}

const getLocalizedContent = (item) => {
  return currentLang.value === 'en'
    ? (item.content_en || item.content || '')
    : (item.content || item.content_en || '')
}

const getLocalizedCaption = (item) => {
  return currentLang.value === 'en'
    ? (item.image_caption_en || item.image_caption || '')
    : (item.image_caption || item.image_caption_en || '')
}

const formatContent = (content) => {
  if (!content) return ''
  // 将换行符转换为 <br>
  return content.replace(/\n/g, '<br>')
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  return new Date(dateString).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

const getFullImageUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return config.API_BASE_URL + url
}

const handleImageError = (e) => {
  e.target.style.display = 'none'
}

// 加载数据
const loadData = async () => {
  const versionId = route.params.versionId
  if (!versionId) {
    ElMessage.error('版本ID无效')
    router.push('/settings/app-version')
    return
  }

  loading.value = true
  try {
    // 获取版本信息
    try {
      versionInfo.value = await appVersionAPI.getVersion(versionId)
    } catch (e) {
      console.warn('获取版本信息失败:', e)
    }

    // 获取 Release Note
    releaseNote.value = await appVersionAPI.getReleaseNote(versionId)
  } catch (error) {
    console.error('加载 Release Note 失败:', error)
    if (error.response?.status === 404) {
      releaseNote.value = null
    } else {
      ElMessage.error('加载失败: ' + (error.response?.data?.detail || error.message))
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.release-notes-preview-page {
  min-height: 100vh;
  background: #f5f7fa;
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-header h1 {
  margin: 0;
  color: #1f2937;
  font-size: 20px;
  font-weight: 600;
}

.loading-container,
.empty-container {
  background: #fff;
  border-radius: 8px;
  padding: 60px 40px;
  max-width: 900px;
  margin: 0 auto;
}

.release-notes-container {
  max-width: 900px;
  margin: 0 auto;
}

/* 头部卡片 */
.header-card {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 16px;
}

.version-badge {
  font-size: 48px;
}

.title-section {
  flex: 1;
}

.main-title {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.sub-title {
  font-size: 16px;
  color: #6b7280;
  margin: 0;
}

.version-info {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.date-tag {
  color: #9ca3af;
  font-size: 14px;
}

/* 更新项目列表 */
.items-card {
  margin-bottom: 20px;
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.update-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px;
  background: #f9fafb;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.item-number {
  width: 32px;
  height: 32px;
  min-width: 32px;
  background: #409eff;
  color: #fff;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
}

.item-content {
  flex: 1;
}

.item-text {
  margin: 0;
  font-size: 15px;
  line-height: 1.7;
  color: #374151;
}

.item-image {
  margin-top: 12px;
}

.item-image img {
  max-width: 100%;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.image-caption {
  margin: 8px 0 0 0;
  font-size: 13px;
  color: #6b7280;
  text-align: center;
}

/* 底部信息 */
.footer-info {
  text-align: center;
  padding: 24px 20px;
  color: #9ca3af;
  font-size: 14px;
}

.footer-info p {
  margin: 0;
}

/* 响应式 */
@media (max-width: 768px) {
  .release-notes-preview-page {
    padding: 15px;
  }

  .header-content {
    flex-direction: column;
    text-align: center;
  }

  .main-title {
    font-size: 20px;
  }

  .sub-title {
    font-size: 14px;
  }

  .update-item {
    padding: 12px;
  }

  .item-number {
    width: 28px;
    height: 28px;
    min-width: 28px;
    font-size: 12px;
  }

  .item-text {
    font-size: 14px;
  }
}
</style>
