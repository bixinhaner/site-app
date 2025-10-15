<template>
	<view class="profile-container" :key="languageStore.currentLocale">
		<!-- 用户信息头部 -->
		<view class="profile-header">
			<view class="avatar-section">
				<view class="avatar">
					<image 
						v-if="userInfo?.avatar" 
						:src="userInfo.avatar" 
						class="avatar-image"
						mode="aspectFill"
					></image>
					<text v-else class="avatar-text">{{ getAvatarText() }}</text>
				</view>
				<button class="edit-avatar-btn" @click="changeAvatar">
					<text class="btn-icon">📷</text>
				</button>
			</view>
			
			<view class="user-details">
				<text class="user-name">{{ userInfo?.full_name || userInfo?.username }}</text>
				<text class="user-role">{{ getRoleText(userInfo?.role) }}</text>
				<text class="user-department" v-if="userInfo?.department">{{ userInfo.department }}</text>
			</view>
		</view>
		
		<!-- 统计信息 -->
		<view class="stats-section">
			<view class="stat-item">
				<text class="stat-number">{{ userStats.totalSites }}</text>
				<text class="stat-label">{{ $t('home.totalSites') }}</text>
			</view>
			
			<view class="stat-divider"></view>
			
			<view class="stat-item">
				<text class="stat-number">{{ userStats.completedInspections }}</text>
				<text class="stat-label">{{ $t('home.completedToday') }}</text>
			</view>
			
			<view class="stat-divider"></view>
			
			<view class="stat-item">
				<text class="stat-number">{{ userStats.pendingTasks }}</text>
				<text class="stat-label">{{ $t('home.pendingItems') }}</text>
			</view>
		</view>
		
		<!-- 功能菜单 -->
		<view class="menu-section">
			<view class="menu-group">
				<view class="menu-item" @click="editProfile">
					<view class="menu-left">
						<text class="menu-icon">👤</text>
						<text class="menu-text">{{ $t('profile.userInfo') }}</text>
					</view>
					<text class="menu-arrow">›</text>
				</view>
				
				<view class="menu-item" @click="changePassword">
					<view class="menu-left">
						<text class="menu-icon">🔒</text>
						<text class="menu-text">{{ $t('profile.changePassword') }}</text>
					</view>
					<text class="menu-arrow">›</text>
				</view>
				
				<view class="menu-item" @click="viewMyInspections">
					<view class="menu-left">
						<text class="menu-icon">📋</text>
						<text class="menu-text">{{ $t('inspection.list') }}</text>
					</view>
					<text class="menu-arrow">›</text>
				</view>
				
				<view class="menu-item" @click="viewMySites" v-if="canViewSites">
					<view class="menu-left">
						<text class="menu-icon">📍</text>
						<text class="menu-text">{{ userInfo?.role === 'inspector' ? $t('site.title') : $t('site.list') }}</text>
					</view>
					<text class="menu-arrow">›</text>
				</view>
			</view>
			
			<view class="menu-group">
				<!-- 语言设置菜单项 -->
				<view class="menu-item" @click="showLanguageSettings">
					<view class="menu-left">
						<text class="menu-icon">🌐</text>
						<text class="menu-text">{{ $t('profile.languageSettings') }}</text>
					</view>
					<view class="menu-right">
						<text class="menu-value">{{ languageStore.currentLanguageName }}</text>
						<text class="menu-arrow">›</text>
					</view>
				</view>
				
				<view class="menu-item" @click="showSettings">
					<view class="menu-left">
						<text class="menu-icon">⚙️</text>
						<text class="menu-text">{{ $t('profile.settings') }}</text>
					</view>
					<text class="menu-arrow">›</text>
				</view>
				
				<view class="menu-item" @click="showHelp">
					<view class="menu-left">
						<text class="menu-icon">❓</text>
						<text class="menu-text">{{ $t('profile.preferences') }}</text>
					</view>
					<text class="menu-arrow">›</text>
				</view>
				
				<view class="menu-item" @click="showAbout">
					<view class="menu-left">
						<text class="menu-icon">ℹ️</text>
						<text class="menu-text">{{ t('profile.about') }}</text>
					</view>
					<text class="menu-arrow">›</text>
				</view>
				
				<view class="menu-item" @click="goToLoggingTest" v-if="isAdmin">
					<view class="menu-left">
						<text class="menu-icon">🔍</text>
						<text class="menu-text">日志测试</text>
					</view>
					<text class="menu-arrow">›</text>
				</view>
				
				<view class="menu-item" @click="goToLocationPluginTest" v-if="isAdmin">
					<view class="menu-left">
						<text class="menu-icon">📍</text>
						<text class="menu-text">定位插件测试</text>
					</view>
					<text class="menu-arrow">›</text>
				</view>
				
				<view class="menu-item" @click="goToBuiltinLocationTest" v-if="isAdmin">
					<view class="menu-left">
						<text class="menu-icon">🌍</text>
						<text class="menu-text">内置定位测试</text>
					</view>
					<text class="menu-arrow">›</text>
				</view>
			</view>
			
			<view class="menu-group">
				<view class="menu-item logout" @click="handleLogout">
					<view class="menu-left">
						<text class="menu-icon">🚪</text>
						<text class="menu-text">{{ $t('profile.logout') }}</text>
					</view>
					<text class="menu-arrow">›</text>
				</view>
			</view>
		</view>
		
		<!-- 语言设置弹窗 -->
		<view class="language-modal" v-if="showLanguageModal" @click="closeLanguagePopup">
			<view class="language-popup" @click.stop>
				<view class="popup-header">
					<view class="popup-title">{{ $t('profile.languageSettings') }}</view>
					<view class="popup-close" @click="closeLanguagePopup">✕</view>
				</view>
				<view class="language-options">
					<view 
						class="language-option" 
						:class="{ active: languageStore.currentLocale === 'zh' }"
						@click="setLanguage('zh')"
					>
						<text class="language-name">{{ $t('profile.chinese') }}</text>
						<text class="language-check" v-if="languageStore.currentLocale === 'zh'">✓</text>
					</view>
					<view 
						class="language-option" 
						:class="{ active: languageStore.currentLocale === 'en' }"
						@click="setLanguage('en')"
					>
						<text class="language-name">{{ $t('profile.english') }}</text>
						<text class="language-check" v-if="languageStore.currentLocale === 'en'">✓</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 版本信息 -->
		<view class="version-info">
			<text class="version-text">站点管理系统 v1.0.0</text>
			<text class="build-text">Build 20240101</text>
		</view>
	</view>
</template>

<script setup>
	import { ref, reactive, computed, onMounted, watch, getCurrentInstance } from 'vue'
import { useUserStore } from '@/stores/user'
	import { useSiteStore } from '@/stores/site'
	import { useInspectionStore } from '@/stores/inspection'
	import { useLanguageStore } from '@/stores/language'
	
	const userStore = useUserStore()
	const siteStore = useSiteStore()
	const inspectionStore = useInspectionStore()
	const languageStore = useLanguageStore()
	
	const instance = getCurrentInstance()
	const $t = instance.appContext.config.globalProperties.$t
	
	// 使用computed创建响应式的t函数
	const t = (key) => {
		// 添加对currentLocale的依赖，使其成为响应式
		const _ = languageStore.currentLocale
		return $t(key)
	}
	
	const showLanguageModal = ref(false)
	
	const userStats = reactive({
		totalSites: 0,
		completedInspections: 0,
		pendingTasks: 0
	})
	
const userInfo = computed(() => userStore.userInfo)
const isAdmin = computed(() => userStore.isAdmin)
	
	// 权限控制
	const canViewSites = computed(() => {
		const role = userInfo.value?.role
		return role === 'admin' || role === 'manager' || role === 'inspector'
	})
	
	// 获取头像文字
	const getAvatarText = () => {
		const name = userInfo.value?.full_name || userInfo.value?.username || ''
		return name.charAt(0).toUpperCase()
	}
	
	// 获取角色文本
	const getRoleText = (role) => {
		const roleMap = {
			'admin': '系统管理员',
			'manager': '项目经理',
			'inspector': '安装施工人员',
			'user': '现场工程师'
		}
		return roleMap[role] || role
	}
	
	// 更换头像
	const changeAvatar = () => {
		uni.showActionSheet({
			itemList: ['从相册选择', '拍照'],
			success: (res) => {
				if (res.tapIndex === 0) {
					chooseImageFromAlbum()
				} else if (res.tapIndex === 1) {
					takePhoto()
				}
			}
		})
	}
	
	// 从相册选择
	const chooseImageFromAlbum = () => {
		uni.chooseImage({
			count: 1,
			sourceType: ['album'],
			success: (res) => {
				uploadAvatar(res.tempFilePaths[0])
			}
		})
	}
	
	// 拍照
	const takePhoto = () => {
		uni.chooseImage({
			count: 1,
			sourceType: ['camera'],
			success: (res) => {
				uploadAvatar(res.tempFilePaths[0])
			}
		})
	}
	
	// 上传头像
	const uploadAvatar = (filePath) => {
		uni.showLoading({
			title: '上传中...'
		})
		
		// 这里应该调用后端API上传头像
		// 暂时模拟上传成功
		setTimeout(() => {
			uni.hideLoading()
			uni.showToast({
				title: '上传成功',
				icon: 'success'
			})
			// 更新用户信息中的头像URL
			// userStore.updateAvatar(uploadedUrl)
		}, 2000)
	}
	
	// 编辑个人信息
	const editProfile = () => {
		uni.showModal({
			title: '编辑资料',
			content: '个人信息编辑功能正在开发中',
			showCancel: false
		})
	}
	
	// 修改密码
	const changePassword = () => {
		uni.showModal({
			title: '修改密码',
			content: '密码修改功能正在开发中',
			showCancel: false
		})
	}
	
	// 查看我的检查记录
	const viewMyInspections = () => {
		uni.switchTab({
			url: '/pages/inspection/list'
		})
	}
	
	// 查看我的站点
	const viewMySites = () => {
		uni.switchTab({
			url: '/pages/site/list'
		})
	}
	
	// 应用设置
	const showSettings = () => {
		uni.showActionSheet({
			itemList: ['消息通知', '数据同步', '清理缓存'],
			success: (res) => {
				const actions = ['通知设置', '同步设置', '缓存清理']
				uni.showModal({
					title: actions[res.tapIndex],
					content: '该功能正在开发中',
					showCancel: false
				})
			}
		})
	}
	
	// 帮助中心
	const showHelp = () => {
		uni.showModal({
			title: '帮助中心',
			content: '如需帮助，请联系系统管理员\n\n电话：400-1234-567\n邮箱：support@sitemanager.com',
			showCancel: false
		})
	}
	
	// 关于应用
	const showAbout = () => {
		uni.showModal({
			title: t('profile.aboutTitle'),
			content: t('profile.aboutContent'),
			showCancel: false
		})
	}
	
	// 跳转到日志测试页面
	const goToLoggingTest = () => {
		uni.navigateTo({
			url: '/pages/test/logging-test'
		})
	}
	
	// 跳转到定位插件测试页面
	const goToLocationPluginTest = () => {
		uni.navigateTo({
			url: '/pages/test-location-plugin/test-location-plugin'
		})
	}
	
	// 跳转到内置定位测试页面
	const goToBuiltinLocationTest = () => {
		uni.navigateTo({
			url: '/pages/test-location-builtin/test-location-builtin'
		})
	}
	
	// 显示语言设置弹窗
	const showLanguageSettings = () => {
		showLanguageModal.value = true
	}
	
	// 关闭语言设置弹窗
	const closeLanguagePopup = () => {
		showLanguageModal.value = false
	}
	
	// 设置语言
	const setLanguage = (locale) => {
		languageStore.setLocale(locale)
		closeLanguagePopup()
	}
	
	// 退出登录
	const handleLogout = () => {
		uni.showModal({
			title: $t('messages.confirmLogout'),
			content: $t('messages.confirmLogout'),
			success: (res) => {
				if (res.confirm) {
					userStore.logout()
				}
			}
		})
	}
	
	// 加载用户统计数据
	const loadUserStats = async () => {
		try {
			// 加载站点数据
			const sitesResult = await siteStore.getSites()
			if (sitesResult.success) {
				// 计算用户负责的站点数
				const userSites = sitesResult.data.filter(site => 
					site.assigned_to === userInfo.value?.id || 
					site.created_by === userInfo.value?.id
				)
				userStats.totalSites = userSites.length
			}
			
			// 加载检查数据
			const inspectionsResult = await inspectionStore.getInspections()
			if (inspectionsResult.success) {
				const userInspections = inspectionsResult.data.filter(inspection => 
					inspection.inspector_id === userInfo.value?.id
				)
				userStats.completedInspections = userInspections.filter(i => i.status === 'completed').length
				userStats.pendingTasks = userInspections.filter(i => 
					i.status === 'pending' || i.status === 'in_progress'
				).length
			}
		} catch (error) {
			console.error('Load user stats error:', error)
		}
	}
	
	// 监听语言变化，更新页面标题
	watch(() => languageStore.currentLocale, () => {
		uni.setNavigationBarTitle({
			title: $t('profile.title')
		})
	})
	
	onMounted(() => {
		// 动态设置页面标题
		uni.setNavigationBarTitle({
			title: $t('profile.title')
		})
		if (userInfo.value) {
			loadUserStats()
		}
	})
</script>

<style lang="scss" scoped>
	.profile-container {
		min-height: 100vh;
		background-color: #f5f5f5;
		padding-bottom: 20px;
	}
	
	// 用户信息头部
	.profile-header {
		background: linear-gradient(135deg, #f97316, #fb923c);
		padding: 60px 20px 30px;
		color: white;
		display: flex;
		align-items: center;
		gap: 20px;
	}
	
	.avatar-section {
		position: relative;
	}
	
	.avatar {
		width: 80px;
		height: 80px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(255, 255, 255, 0.2);
		overflow: hidden;
	}
	
	.avatar-image {
		width: 100%;
		height: 100%;
	}
	
	.avatar-text {
		font-size: 32px;
		font-weight: 600;
		color: white;
	}
	
	.edit-avatar-btn {
		position: absolute;
		bottom: -4px;
		right: -4px;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		background: white;
		border: 2px solid #f97316;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 14px;
	}
	
	.user-details {
		flex: 1;
		display: flex;
		flex-direction: column;
	}
	
	.user-name {
		font-size: 22px;
		font-weight: 600;
		margin-bottom: 4px;
	}
	
	.user-role {
		font-size: 14px;
		opacity: 0.9;
		margin-bottom: 2px;
	}
	
	.user-department {
		font-size: 12px;
		opacity: 0.8;
	}
	
	// 统计信息
	.stats-section {
		background: white;
		margin: -10px 20px 20px;
		border-radius: 12px;
		padding: 20px;
		display: flex;
		align-items: center;
		box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
	}
	
	.stat-item {
		flex: 1;
		text-align: center;
		display: flex;
		flex-direction: column;
		align-items: center;
	}
	
	.stat-number {
		font-size: 24px;
		font-weight: 600;
		color: #f97316;
		margin-bottom: 4px;
	}
	
	.stat-label {
		font-size: 12px;
		color: #6b7280;
	}
	
	.stat-divider {
		width: 1px;
		height: 40px;
		background: #f3f4f6;
		margin: 0 20px;
	}
	
	// 功能菜单
	.menu-section {
		padding: 0 20px;
	}
	
	.menu-group {
		background: white;
		border-radius: 12px;
		margin-bottom: 16px;
		overflow: hidden;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
	}
	
	.menu-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px;
		border-bottom: 1px solid #f8f9fa;
		
		&:last-child {
			border-bottom: none;
		}
		
		&.logout {
			.menu-text {
				color: #dc2626;
			}
		}
	}
	
	.menu-left {
		display: flex;
		align-items: center;
		gap: 12px;
	}
	
	.menu-icon {
		font-size: 18px;
		width: 24px;
		text-align: center;
	}
	
	.menu-text {
		font-size: 15px;
		color: #111827;
	}
	
	.menu-arrow {
		font-size: 18px;
		color: #d1d5db;
	}
	
	.menu-right {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	
	.menu-value {
		font-size: 14px;
		color: #6b7280;
	}
	
	// 语言设置弹窗
	.language-modal {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 9999;
		display: flex;
		align-items: flex-end;
		justify-content: center;
	}
	
	.language-popup {
		background: white;
		border-radius: 16px 16px 0 0;
		padding: 0;
		min-height: 200px;
		width: 100%;
		max-width: 500px;
	}
	
	.popup-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 20px;
		border-bottom: 1px solid #f3f4f6;
	}
	
	.popup-title {
		font-size: 18px;
		font-weight: 600;
		color: #1f2937;
	}
	
	.popup-close {
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: #f9fafb;
		border-radius: 50%;
		color: #6b7280;
		font-size: 16px;
		cursor: pointer;
		
		&:active {
			background: #f3f4f6;
		}
	}
	
	.language-options {
		padding: 10px 0;
	}
	
	.language-option {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px;
		cursor: pointer;
		transition: background-color 0.2s;
		
		&:active {
			background: #f9fafb;
		}
		
		&.active {
			background: #fef3e2;
			
			.language-name {
				color: #ea580c;
				font-weight: 500;
			}
		}
	}
	
	.language-name {
		font-size: 16px;
		color: #374151;
	}
	
	.language-check {
		color: #ea580c;
		font-size: 18px;
		font-weight: bold;
	}
	
	// 版本信息
	.version-info {
		text-align: center;
		padding: 20px;
		color: #9ca3af;
	}
	
	.version-text {
		font-size: 14px;
		display: block;
		margin-bottom: 4px;
	}
	
	.build-text {
		font-size: 12px;
		opacity: 0.8;
	}
</style>
