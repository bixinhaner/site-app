import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import CustomNavbar from './components/CustomNavbar.vue'
import i18n from './utils/i18n.js'
import { setI18nInstance } from './stores/language.js'
import { trackPageView } from './utils/operationTrack.js'
import { useUserStore } from './stores/user.js'

export function createApp() {
	const app = createSSRApp(App)
	const pinia = createPinia()
	
	app.use(pinia)
	app.use(i18n)

	// 全局组件：确保 Options API / script setup 均可直接使用
	app.component('CustomNavbar', CustomNavbar)
	
	// 设置i18n实例给语言store使用
	setI18nInstance(i18n)

	// 方案A：不记录普通GET，页面访问/查询等通过前端轨迹上报
	app.mixin({
		onShow() {
			// 统一登录态兜底：避免未登录进入业务页后只看到“加载失败/未登录”的弱提示
			try {
				const pages = getCurrentPages()
				const route = pages?.[pages.length - 1]?.route || ''
				if (route && route !== 'pages/login/login') {
					const userStore = useUserStore()
					if (!userStore.isLoggedIn) {
						uni.reLaunch({ url: '/pages/login/login' })
						return
					}
				}
			} catch (e) {
				// ignore
			}
			trackPageView()
		}
	})
	
	return {
		app
	}
}
