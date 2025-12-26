<template>
	<view class="release-notes-page">
		<!-- 导航栏 -->
		<view class="navbar">
			<view class="navbar-left" @click="goBack">
				<text class="back-icon">←</text>
			</view>
			<text class="navbar-title">{{ t('title') }}</text>
			<view class="navbar-right"></view>
		</view>
		
		<!-- 加载中 -->
		<view v-if="loading" class="loading-container">
			<view class="loading-spinner"></view>
			<text class="loading-text">{{ t('loading') }}</text>
		</view>
		
		<!-- 错误状态 -->
		<view v-else-if="error" class="error-container">
			<text class="error-icon">😔</text>
			<text class="error-text">{{ error }}</text>
			<button class="retry-btn" @click="loadData">{{ t('retry') }}</button>
		</view>
		
		<!-- 内容区域 -->
		<scroll-view v-else scroll-y class="content-scroll">
			<!-- 头部卡片 -->
			<view class="header-card">
				<view class="version-badge">🚀</view>
				<text class="main-title">{{ localizedTitle }}</text>
				<text class="sub-title" v-if="localizedSubtitle">{{ localizedSubtitle }}</text>
				<view class="version-info">
					<view class="version-tag">v{{ versionName }}</view>
					<text class="date-tag" v-if="releaseNote?.created_at">
						{{ formatDate(releaseNote.created_at) }}
					</text>
				</view>
			</view>
			
			<!-- 更新项目列表 -->
			<view class="items-container">
				<text class="section-title">{{ t('updateContent') }}</text>
				<view 
					v-for="(item, index) in releaseNote?.items || []" 
					:key="item.id"
					class="update-item"
				>
					<view class="item-number">{{ index + 1 }}</view>
					<view class="item-content">
						<!-- 文字内容 -->
						<text class="item-text" v-if="getLocalizedContent(item)">
							{{ getLocalizedContent(item) }}
						</text>
						
						<!-- 图片内容 -->
						<view
							v-for="(img, imgIndex) in getItemImages(item)"
							:key="img.image_url + '_' + imgIndex"
							class="item-image"
						>
							<image
								:src="getFullImageUrl(img.image_url)"
								mode="widthFix"
								@click="previewItemImages(item, imgIndex)"
								@error="handleImageError"
							/>
							<text class="image-caption" v-if="getLocalizedImageCaption(img)">
								{{ getLocalizedImageCaption(img) }}
							</text>
						</view>
					</view>
				</view>
			</view>
			
			<!-- 底部信息 -->
			<view class="footer-info">
				<text>{{ t('thankYou') }}</text>
			</view>
		</scroll-view>
	</view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { useLanguageStore } from '@/stores/language'
import { API_ENDPOINTS, buildApiUrl, buildImageUrl, createRequestConfig } from '@/config/api.js'
import { env } from '@/config/env.js'

const languageStore = useLanguageStore()

// 状态
const loading = ref(true)
const error = ref('')
const releaseNote = ref(null)
const versionId = ref(null)
const versionName = ref('')

// 国际化
const translations = {
	zh: {
		title: '版本更新详情',
		loading: '加载中...',
		retry: '重试',
		updateContent: '更新内容',
		thankYou: '感谢您使用我们的应用！如有问题请联系技术支持。',
		loadFailed: '加载失败，请稍后重试',
		noData: '暂无更新说明'
	},
	en: {
		title: 'Release Notes',
		loading: 'Loading...',
		retry: 'Retry',
		updateContent: 'What\'s New',
		thankYou: 'Thank you for using our app! Contact support if you need help.',
		loadFailed: 'Failed to load, please try again',
		noData: 'No release notes available'
	}
}

const t = (key) => {
	const locale = languageStore.currentLocale || 'zh'
	return translations[locale]?.[key] || key
}

// 计算属性
const localizedTitle = computed(() => {
	if (!releaseNote.value) return ''
	const locale = languageStore.currentLocale
	return locale === 'en'
		? (releaseNote.value.title_en || releaseNote.value.title || '')
		: (releaseNote.value.title || releaseNote.value.title_en || '')
})

const localizedSubtitle = computed(() => {
	if (!releaseNote.value) return ''
	const locale = languageStore.currentLocale
	return locale === 'en'
		? (releaseNote.value.subtitle_en || releaseNote.value.subtitle || '')
		: (releaseNote.value.subtitle || releaseNote.value.subtitle_en || '')
})

// 方法
const getLocalizedContent = (item) => {
	const locale = languageStore.currentLocale
	return locale === 'en'
		? (item.content_en || item.content || '')
		: (item.content || item.content_en || '')
}

const getLocalizedCaption = (item) => {
	const locale = languageStore.currentLocale
	return locale === 'en'
		? (item.image_caption_en || item.image_caption || '')
		: (item.image_caption || item.image_caption_en || '')
}

const getLocalizedImageCaption = (img) => {
	const locale = languageStore.currentLocale
	return locale === 'en'
		? (img.image_caption_en || img.image_caption || '')
		: (img.image_caption || img.image_caption_en || '')
}

const getItemImages = (item) => {
	const images = Array.isArray(item.images) ? item.images : []
	if (images.length) {
		return images
			.filter(img => img && img.image_url)
			.slice()
			.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
	}

	if (item.image_url) {
		return [{
			sort_order: 0,
			image_url: item.image_url,
			image_caption: item.image_caption,
			image_caption_en: item.image_caption_en
		}]
	}

	return []
}

const formatDate = (dateString) => {
	if (!dateString) return ''
	const date = new Date(dateString)
	const locale = languageStore.currentLocale
	return date.toLocaleDateString(locale === 'en' ? 'en-US' : 'zh-CN', {
		year: 'numeric',
		month: 'long',
		day: 'numeric'
	})
}

const getFullImageUrl = (url) => {
	if (!url) return ''
	if (url.startsWith('http')) return url
	return buildImageUrl(url)
}

const handleImageError = (e) => {
	console.warn('图片加载失败:', e)
}

const previewItemImages = (item, imgIndex) => {
	const urls = getItemImages(item)
		.map(img => getFullImageUrl(img.image_url))
		.filter(Boolean)
	if (!urls.length) return
	const current = urls[imgIndex] || urls[0]
	uni.previewImage({
		urls,
		current
	})
}

const goBack = () => {
	uni.navigateBack()
}

// 加载数据
const loadData = async () => {
	console.log('📋 Release Notes: loadData called, versionId =', versionId.value)
	
	if (!versionId.value) {
		console.warn('📋 Release Notes: No versionId, showing noData error')
		error.value = t('noData')
		loading.value = false
		return
	}
	
	loading.value = true
	error.value = ''
	
	try {
		const url = buildApiUrl(`${API_ENDPOINTS.APP_VERSION.BASE}/release-notes/${versionId.value}`)
		console.log('📋 Release Notes: Requesting URL =', url)
		
		const response = await uni.request({
			...createRequestConfig(),
			url,
			method: 'GET'
		})
		
		console.log('📋 Release Notes: Response =', response)
		
		if (response.statusCode === 200 && response.data) {
			releaseNote.value = response.data
			console.log('📋 Release Notes: Data loaded successfully')
		} else if (response.statusCode === 404) {
			console.warn('📋 Release Notes: 404 - Not found')
			error.value = t('noData')
		} else {
			throw new Error('请求失败: ' + response.statusCode)
		}
	} catch (e) {
		console.error('📋 Release Notes: Load failed:', e)
		error.value = t('loadFailed')
	} finally {
		loading.value = false
	}
}

// 页面加载 - 使用onLoad获取页面参数
onLoad((options) => {
	console.log('📋 Release Notes: onLoad called with options =', options)
	
	versionId.value = options?.versionId
	versionName.value = options?.versionName || ''
	
	console.log('📋 Release Notes: Parsed versionId =', versionId.value, ', versionName =', versionName.value)
	
	if (versionId.value) {
		loadData()
	} else {
		console.warn('📋 Release Notes: No versionId in options, showing noData')
		error.value = t('noData')
		loading.value = false
	}
})
</script>

<style lang="scss" scoped>
.release-notes-page {
	min-height: 100vh;
	background: linear-gradient(180deg, #f0f4f8 0%, #fff 100%);
}

// 导航栏
.navbar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	height: 88rpx;
	padding: 0 32rpx;
	padding-top: var(--status-bar-height);
	background: var(--color-primary, #f97316);
	
	.navbar-left {
		width: 80rpx;
		
		.back-icon {
			font-size: 40rpx;
			color: #fff;
		}
	}
	
	.navbar-title {
		flex: 1;
		text-align: center;
		font-size: 34rpx;
		font-weight: 600;
		color: #fff;
	}
	
	.navbar-right {
		width: 80rpx;
	}
}

// 加载状态
.loading-container {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 100rpx 0;
	
	.loading-spinner {
		width: 64rpx;
		height: 64rpx;
		border: 6rpx solid #e5e7eb;
		border-top-color: var(--color-primary, #f97316);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	
	.loading-text {
		margin-top: 24rpx;
		font-size: 28rpx;
		color: #6b7280;
	}
}

@keyframes spin {
	to { transform: rotate(360deg); }
}

// 错误状态
.error-container {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 100rpx 40rpx;
	
	.error-icon {
		font-size: 80rpx;
		margin-bottom: 24rpx;
	}
	
	.error-text {
		font-size: 28rpx;
		color: #6b7280;
		text-align: center;
		margin-bottom: 32rpx;
	}
	
	.retry-btn {
		background: var(--color-primary, #f97316);
		color: #fff;
		font-size: 28rpx;
		padding: 16rpx 48rpx;
		border-radius: 40rpx;
		border: none;
	}
}

// 内容滚动区
.content-scroll {
	height: calc(100vh - 88rpx - var(--status-bar-height));
}

// 头部卡片
.header-card {
	margin: 32rpx;
	padding: 48rpx 32rpx;
	background: #fff;
	border-radius: 24rpx;
	text-align: center;
	box-shadow: 0 8rpx 32rpx rgba(0, 0, 0, 0.08);
	
	.version-badge {
		font-size: 80rpx;
		margin-bottom: 16rpx;
	}
	
	.main-title {
		display: block;
		font-size: 40rpx;
		font-weight: 700;
		color: #1f2937;
		margin-bottom: 12rpx;
	}
	
	.sub-title {
		display: block;
		font-size: 28rpx;
		color: #6b7280;
		margin-bottom: 24rpx;
	}
	
	.version-info {
		display: flex;
		justify-content: center;
		align-items: center;
		gap: 16rpx;
		flex-wrap: wrap;
	}
	
	.version-tag {
		background: var(--color-primary, #f97316);
		color: #fff;
		padding: 8rpx 24rpx;
		border-radius: 24rpx;
		font-size: 26rpx;
		font-weight: 600;
	}
	
	.date-tag {
		font-size: 24rpx;
		color: #9ca3af;
	}
}

// 更新项目列表
.items-container {
	margin: 0 32rpx 32rpx;
	padding: 32rpx;
	background: #fff;
	border-radius: 24rpx;
	box-shadow: 0 8rpx 32rpx rgba(0, 0, 0, 0.08);
	
	.section-title {
		display: block;
		font-size: 30rpx;
		font-weight: 600;
		color: #374151;
		margin-bottom: 24rpx;
		padding-bottom: 16rpx;
		border-bottom: 2rpx solid #e5e7eb;
	}
}

.update-item {
	display: flex;
	align-items: flex-start;
	gap: 20rpx;
	padding: 24rpx;
	background: #f9fafb;
	border-radius: 16rpx;
	margin-bottom: 20rpx;
	
	&:last-child {
		margin-bottom: 0;
	}
	
	.item-number {
		width: 48rpx;
		height: 48rpx;
		min-width: 48rpx;
		background: var(--color-primary, #f97316);
		color: #fff;
		border-radius: 12rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 26rpx;
		font-weight: 700;
	}
	
	.item-content {
		flex: 1;
		
		.item-text {
			display: block;
			font-size: 28rpx;
			line-height: 1.7;
			color: #374151;
		}
		
		.item-image {
			margin-top: 16rpx;
			
			image {
				width: 100%;
				border-radius: 12rpx;
			}
			
			.image-caption {
				display: block;
				margin-top: 8rpx;
				font-size: 24rpx;
				color: #6b7280;
				text-align: center;
			}
		}
	}
}

// 底部信息
.footer-info {
	text-align: center;
	padding: 32rpx;
	font-size: 24rpx;
	color: #9ca3af;
}
</style>
