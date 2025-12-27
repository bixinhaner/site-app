import { defineStore } from 'pinia'

let i18nInstance = null

export const setI18nInstance = (instance) => {
  i18nInstance = instance
}

export const useLanguageStore = defineStore('language', {
  state: () => ({
    currentLocale: uni.getStorageSync('locale') || 'zh',
    supportedLocales: [
      { code: 'zh', name: '中文' },
      { code: 'en', name: 'English' },
      { code: 'id', name: 'Bahasa Indonesia' }
    ]
  }),

  getters: {
    currentLanguageName() {
      const lang = this.supportedLocales.find(l => l.code === this.currentLocale)
      return lang ? lang.name : '中文'
    },

    currentLocaleTag() {
      if (this.currentLocale === 'zh') return 'zh-CN'
      if (this.currentLocale === 'id') return 'id-ID'
      return 'en-US'
    },
    
    isZh() {
      return this.currentLocale === 'zh'
    },
    
    isEn() {
      return this.currentLocale === 'en'
    },

    isId() {
      return this.currentLocale === 'id'
    }
  },

  actions: {
    updateTabBarText() {
      if (!i18nInstance) return
      
      const t = i18nInstance.global.t.bind(i18nInstance.global)
      
      // 更新底部导航栏文本
      const tabBarItems = [
        { index: 0, text: t('navigation.home') },
        { index: 1, text: t('navigation.sites') }, 
        { index: 2, text: t('navigation.workorders') },
        { index: 3, text: t('navigation.profile') }
      ]
      
      tabBarItems.forEach(item => {
        uni.setTabBarItem({
          index: item.index,
          text: item.text
        })
      })
    },
    
    updatePageTitle(route) {
      if (!i18nInstance) return
      
      const t = i18nInstance.global.t.bind(i18nInstance.global)
      
      // 根据当前页面路径设置对应的标题
      const titleMap = {
        'pages/site/list': t('site.list'),
        'pages/profile/profile': t('profile.title'),
        'pages/workorder/list': t('workorder.title'),
        'pages/home/home': t('home.title'),
        'pages/site/detail': t('site.detail'),
        'pages/inspection/checklist': t('inspection.checklist'),
        'pages/inspection/detail': t('inspection.detail'),
        'pages/inspection/review': t('inspection.review'),
        'pages/inspection/camera': t('inspection.camera'),
        'pages/stock/scan-pickup': t('stock.scanPickup'),
        // 测试页面
        'pages/test/logging-test': t('test.logging.title'),
        'pages/test-location-plugin/test-location-plugin': t('test.locationPlugin.title'),
        'pages/test-location-builtin/test-location-builtin': t('test.locationBuiltin.title'),
        'pages/test/watermark-test': t('test.watermark.title')
      }
      
      const title = titleMap[route]
      if (title) {
        uni.setNavigationBarTitle({
          title: title
        })
      }
    },
    
    async setLocale(locale) {
      if (this.supportedLocales.some(l => l.code === locale)) {
        this.currentLocale = locale
        if (i18nInstance) {
          i18nInstance.global.locale = locale
        }
        
        try {
          uni.setStorageSync('locale', locale)
        } catch (e) {
          console.error('Failed to save locale to storage:', e)
        }
        
        // 更新底部导航栏文本
        this.updateTabBarText()
        
        // 更新当前页面标题
        const pages = getCurrentPages()
        if (pages.length > 0) {
          const currentPage = pages[pages.length - 1]
          this.updatePageTitle(currentPage.route)
        }
        
        const toastTitle = i18nInstance
          ? i18nInstance.global.t(
            locale === 'zh' ? 'messages.languageSwitchedToZh' :
            locale === 'en' ? 'messages.languageSwitchedToEn' :
            'messages.languageSwitchedToId'
          )
          : (
            locale === 'zh' ? '语言已切换为中文' :
            locale === 'en' ? 'Language switched to English' :
            'Bahasa telah diganti ke Bahasa Indonesia'
          )
        uni.showToast({
          title: toastTitle,
          icon: 'none',
          duration: 2000
        })
      }
    },

    toggleLocale() {
      const locales = ['zh', 'en', 'id']
      const currentIndex = locales.indexOf(this.currentLocale)
      const newLocale = locales[(currentIndex + 1) % locales.length]
      this.setLocale(newLocale)
    },

    initLocale() {
      const savedLocale = uni.getStorageSync('locale')
      if (savedLocale && this.supportedLocales.some(l => l.code === savedLocale)) {
        this.currentLocale = savedLocale
        if (i18nInstance) {
          i18nInstance.global.locale = savedLocale
        }
        // 初始化时也要更新底部导航栏文本
        this.updateTabBarText()
        // 初始化时也更新当前页面标题（避免启动后仍显示 pages.json 默认中文标题）
        const pages = getCurrentPages()
        if (pages.length > 0) {
          const currentPage = pages[pages.length - 1]
          this.updatePageTitle(currentPage.route)
        }
      } else {
        const systemLocale = uni.getSystemInfoSync().language || 'zh'
        let locale = 'zh'  // 默认中文
        if (systemLocale.startsWith('en')) {
          locale = 'en'
        } else if (systemLocale.startsWith('id')) {
          locale = 'id'
        }
        this.setLocale(locale)
      }
    }
  }
})
