<template>
  <div class="release-notes-preview-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <el-button @click="goBack" type="default">
        <el-icon><ArrowLeft /></el-icon>
        返回版本管理
      </el-button>
      <h1>Release Notes 预览</h1>
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
      <div class="header-card">
        <div class="version-badge">🚀</div>
        <h1 class="main-title">{{ localizedTitle }}</h1>
        <p class="sub-title">{{ localizedSubtitle }}</p>
        <div class="version-info">
          <span class="version-tag">v{{ versionInfo?.version_name }}</span>
          <span class="date-tag" v-if="releaseNote.created_at">
            发布于 {{ formatDate(releaseNote.created_at) }}
          </span>
        </div>
      </div>

      <!-- 更新项目列表 -->
      <div class="items-container">
        <div 
          v-for="(item, index) in releaseNote.items" 
          :key="item.id"
          class="update-item"
          :class="{ 'image-item': item.item_type === 'image' }"
        >
          <!-- 文字项目 -->
          <template v-if="item.item_type === 'text'">
            <div class="item-number">{{ index + 1 }}</div>
            <div class="item-content">
              <p class="item-text" v-html="formatContent(getLocalizedContent(item))"></p>
            </div>
          </template>

          <!-- 图片项目 -->
          <template v-else-if="item.item_type === 'image'">
            <div class="image-wrapper">
              <img 
                :src="getFullImageUrl(item.image_url)" 
                :alt="getLocalizedCaption(item)"
                @error="handleImageError"
              />
              <p class="image-caption" v-if="getLocalizedCaption(item)">
                {{ getLocalizedCaption(item) }}
              </p>
            </div>
          </template>
        </div>
      </div>

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
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding: 0 20px;
}

.page-header h1 {
  margin: 0;
  color: #fff;
  font-size: 20px;
  font-weight: 500;
}

.loading-container,
.empty-container {
  background: #fff;
  border-radius: 20px;
  padding: 60px 40px;
  max-width: 800px;
  margin: 0 auto;
}

.release-notes-container {
  max-width: 800px;
  margin: 0 auto;
}

/* 头部卡片 */
.header-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 24px;
  padding: 50px 40px;
  text-align: center;
  margin-bottom: 30px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.version-badge {
  font-size: 64px;
  margin-bottom: 20px;
}

.main-title {
  font-size: 32px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 12px 0;
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.sub-title {
  font-size: 18px;
  color: #666;
  margin: 0 0 24px 0;
}

.version-info {
  display: flex;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
}

.version-tag {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  padding: 8px 20px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
}

.date-tag {
  color: #999;
  font-size: 14px;
  padding: 8px 20px;
}

/* 更新项目列表 */
.items-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.update-item {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  padding: 24px 30px;
  display: flex;
  align-items: flex-start;
  gap: 20px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.update-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
}

.update-item.image-item {
  padding: 0;
  overflow: hidden;
}

.item-number {
  width: 40px;
  height: 40px;
  min-width: 40px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
}

.item-content {
  flex: 1;
}

.item-text {
  margin: 0;
  font-size: 16px;
  line-height: 1.8;
  color: #333;
}

/* 图片项目 */
.image-wrapper {
  width: 100%;
}

.image-wrapper img {
  width: 100%;
  display: block;
  border-radius: 16px 16px 0 0;
}

.image-caption {
  padding: 16px 24px;
  margin: 0;
  font-size: 14px;
  color: #666;
  text-align: center;
  background: #f8f9fa;
  border-radius: 0 0 16px 16px;
}

/* 底部信息 */
.footer-info {
  text-align: center;
  padding: 40px 20px;
  color: rgba(255, 255, 255, 0.8);
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

  .header-card {
    padding: 30px 20px;
  }

  .main-title {
    font-size: 24px;
  }

  .sub-title {
    font-size: 15px;
  }

  .update-item {
    padding: 16px 20px;
  }

  .item-number {
    width: 32px;
    height: 32px;
    min-width: 32px;
    font-size: 14px;
  }

  .item-text {
    font-size: 14px;
  }
}
</style>
