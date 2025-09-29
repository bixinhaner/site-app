import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import i18n from './utils/i18n.js'
import { setI18nInstance } from './stores/language.js'

export function createApp() {
	const app = createSSRApp(App)
	const pinia = createPinia()
	
	app.use(pinia)
	app.use(i18n)
	
	// 设置i18n实例给语言store使用
	setI18nInstance(i18n)
	
	return {
		app
	}
}