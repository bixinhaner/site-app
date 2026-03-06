import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import CustomNavbar from './components/CustomNavbar.vue'
import CustomTabbar from './components/custom-tabbar/custom-tabbar.vue'
import OfflineDocumentSection from './components/OfflineDocumentSection.vue'
import DocumentPhotoPicker from './components/DocumentPhotoPicker.vue'
import UniIcons from './uni_modules/uni-icons/components/uni-icons/uni-icons.vue'
import UniLoadMore from './uni_modules/uni-load-more/components/uni-load-more/uni-load-more.vue'
import i18n from './utils/i18n.js'
import { setI18nInstance } from './stores/language.js'
import { trackPageView } from './utils/operationTrack.js'
import { useUserStore } from './stores/user.js'
import { guardRouteAccess, isPublicRoute, normalizeRoutePath } from './utils/feature-access.js'
import { formatPercentInt, toPercentInt } from './utils/number.js'

// 统一拦截 showToast
// 解决 UniApp 原生 toast 带图标时文字长度限制问题（通常最多7个汉字）
// 自动转换为纯文本模式 + Emoji，确保长文本完整显示
const originalShowToast = uni.showToast
uni.showToast = function (options = {}) {
	const title = options.title || ''
	const icon = options.icon || 'success'
	const image = options.image

	// 如果已经指定了 none 或者使用了自定义图片，则不处理
	if (icon === 'none' || image) {
		return originalShowToast.call(uni, options)
	}

	// 检查文本长度（简单按字符数判断，汉字占1，英文占1，保守阈值设为7）
	// 实测带图标时超过7-8个字就会被截断
	if (title.length > 7) {
		// 映射图标到 Emoji
		let prefix = ''
		if (icon === 'success') prefix = '✅ '
		else if (icon === 'error' || icon === 'fail') prefix = '❌ '
		else if (icon === 'exception') prefix = '❗ '
		else if (icon === 'loading') prefix = '⏳ '

		// 强制转换为纯文本模式
		options.icon = 'none'
		options.title = prefix + title
	}

	return originalShowToast.call(uni, options)
}

// 统一拦截 showModal
// 修复不同语言下默认按钮文案仍为中文（如“确定/取消”）的问题
const originalShowModal = uni.showModal
uni.showModal = function (options = {}) {
	try {
		const t = i18n?.global?.t?.bind(i18n.global)
		if (!t) return originalShowModal.call(uni, options)

		const nextOptions = { ...options }
		const showCancel = nextOptions.showCancel !== false

		if (showCancel) {
			if (nextOptions.confirmText === undefined || nextOptions.confirmText === null || nextOptions.confirmText === '') {
				nextOptions.confirmText = t('common.confirm')
			}
			if (nextOptions.cancelText === undefined || nextOptions.cancelText === null || nextOptions.cancelText === '') {
				nextOptions.cancelText = t('common.cancel')
			}
		} else {
			if (nextOptions.confirmText === undefined || nextOptions.confirmText === null || nextOptions.confirmText === '') {
				nextOptions.confirmText = t('common.ok')
			}
		}

		return originalShowModal.call(uni, nextOptions)
	} catch (e) {
		return originalShowModal.call(uni, options)
	}
}

export function createApp() {
	const app = createSSRApp(App)
	const pinia = createPinia()

	app.use(pinia)
	app.use(i18n)

	// 全局组件：确保 Options API / script setup 均可直接使用
	app.component('CustomNavbar', CustomNavbar)
	// 生产包兜底：显式注册常用组件，避免 easycom/自动解析异常导致不渲染
	app.component('custom-tabbar', CustomTabbar)
	app.component('uni-icons', UniIcons)
	app.component('uni-load-more', UniLoadMore)
	app.component('OfflineDocumentSection', OfflineDocumentSection)
	app.component('DocumentPhotoPicker', DocumentPhotoPicker)
	app.config.globalProperties.$formatPercentInt = formatPercentInt
	app.config.globalProperties.$toPercentInt = toPercentInt

	// 设置i18n实例给语言store使用
	setI18nInstance(i18n)

	const ensureCurrentPageAccess = (silent = true) => {
		try {
			const pages = getCurrentPages()
			const route = normalizeRoutePath(pages?.[pages.length - 1]?.route || '')
			if (!route || isPublicRoute(route)) {
				return true
			}
			const userStore = useUserStore()
			return guardRouteAccess({
				userStore,
				route,
				t: i18n?.global?.t?.bind(i18n.global),
				silent,
				delay: 0,
			})
		} catch (e) {
			return true
		}
	}

	// 方案A：不记录普通GET，页面访问/查询等通过前端轨迹上报
	app.mixin({
		onLoad() {
			ensureCurrentPageAccess(true)
		},
		onShow() {
			// 统一登录态与页面权限兜底，避免“入口隐藏了但 URL 还能进”。
			if (!ensureCurrentPageAccess(true)) {
				return
			}
			trackPageView()
		}
	})

	return {
		app
	}
}
