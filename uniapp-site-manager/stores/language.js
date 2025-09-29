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
      { code: 'en', name: 'English' }
    ]
  }),

  getters: {
    currentLanguageName() {
      const lang = this.supportedLocales.find(l => l.code === this.currentLocale)
      return lang ? lang.name : '中文'
    },
    
    isZh() {
      return this.currentLocale === 'zh'
    },
    
    isEn() {
      return this.currentLocale === 'en'
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
        'pages/workorder/detail': t('workorder.detail'),
        'pages/site/detail': t('site.detail'),
        'pages/inspection/checklist': t('inspection.checklist'),
        'pages/inspection/detail': t('inspection.detail'),
        'pages/inspection/review': t('inspection.review'),
        'pages/inspection/camera': t('inspection.camera'),
        'pages/stock/scan-pickup': t('stock.scanPickup')
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
        
        uni.showToast({
          title: locale === 'zh' ? '语言已切换为中文' : 'Language switched to English',
          icon: 'none',
          duration: 2000
        })
      }
    },

    toggleLocale() {
      const newLocale = this.currentLocale === 'zh' ? 'en' : 'zh'
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
      } else {
        const systemLocale = uni.getSystemInfoSync().language || 'zh'
        const locale = systemLocale.startsWith('en') ? 'en' : 'zh'
        this.setLocale(locale)
      }
    }
  }
})