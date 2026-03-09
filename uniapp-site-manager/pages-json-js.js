import { createBlock, createVNode, defineAsyncComponent, openBlock, withCtx } from 'vue'
import pagesConfig from './pages.json'
import {
  PageComponent,
  UniServiceJSBridge,
  UniViewJSBridge,
  getApp,
  getCurrentPages,
  setupPage,
  uni,
  upx2px,
} from '@dcloudio/uni-h5'
import '@dcloudio/uni-h5/style/framework/base.css'
import '@dcloudio/uni-h5/style/framework/async.css'
import '@dcloudio/uni-h5/style/framework/pageHead.css'
import '@dcloudio/uni-h5/style/framework/pageRefresh.css'

const globalTarget = typeof window !== 'undefined' ? window : globalThis
const pageModules = import.meta.glob('./pages/**/*.vue')

const APP_ASYNC_CONFIG = {
  delay: 0,
  timeout: 30000,
  suspensible: false,
}

const normalizeNavigationBar = (style = {}) => {
  const globalStyle = pagesConfig?.globalStyle || {}
  const textStyle = String(style.navigationBarTextStyle || globalStyle.navigationBarTextStyle || 'black').toLowerCase()
  return {
    type: 'default',
    style: String(style.navigationStyle || 'default').toLowerCase(),
    titleText: String(style.navigationBarTitleText || '').trim(),
    titleColor: textStyle === 'white' ? '#FFFFFF' : '#000000',
    backgroundColor: String(style.navigationBarBackgroundColor || globalStyle.navigationBarBackgroundColor || '#F8F8F8'),
    searchInput: null,
  }
}

const buildPageMeta = (page, index) => {
  const style = page?.style || {}
  const enablePullDownRefresh = style.enablePullDownRefresh === true
  return {
    isEntry: index === 0,
    isQuit: index === 0,
    isTabBar: false,
    route: String(page?.path || '').trim(),
    navigationBar: normalizeNavigationBar(style),
    enablePullDownRefresh,
    pullToRefresh: enablePullDownRefresh
      ? {
          offset: 0,
          color: '#2B63F1',
          type: 'default',
        }
      : undefined,
    leftWindow: false,
    rightWindow: false,
    topWindow: false,
  }
}

const renderPage = (component, props) => {
  return openBlock(), createBlock(PageComponent, null, {
    page: withCtx(() => [
      createVNode(component, { ...(props || {}), ref: 'page' }, null, 512),
    ]),
    _: 1,
  })
}

const resolvePageImporter = (pagePath) => {
  const filePath = `./${pagePath}.vue`
  const importer = pageModules[filePath]
  if (!importer) {
    throw new Error(`未找到页面组件: ${filePath}`)
  }
  return importer
}

const createPageLoader = (pagePath) => {
  const importer = resolvePageImporter(pagePath)
  return () => importer().then((mod) => setupPage(mod.default || mod))
}

const createPageComponent = (pagePath) => {
  return defineAsyncComponent({
    loader: createPageLoader(pagePath),
    delay: APP_ASYNC_CONFIG.delay,
    timeout: APP_ASYNC_CONFIG.timeout,
    suspensible: APP_ASYNC_CONFIG.suspensible,
  })
}

const buildRouteRecord = (page, index) => {
  const pagePath = String(page?.path || '').trim()
  const pageComponent = createPageComponent(pagePath)
  const loader = createPageLoader(pagePath)
  const routePath = index === 0 ? '/' : `/${pagePath}`
  const alias = index === 0 ? `/${pagePath}` : undefined
  const meta = buildPageMeta(page, index)

  return {
    path: routePath,
    ...(alias ? { alias } : {}),
    component: {
      setup() {
        const app = getApp()
        const query = (app && app.$route && app.$route.query) || {}
        return () => renderPage(pageComponent, query)
      },
    },
    loader,
    meta,
  }
}

const routes = (Array.isArray(pagesConfig?.pages) ? pagesConfig.pages : []).map(buildRouteRecord)

globalTarget.getApp = getApp
globalTarget.getCurrentPages = getCurrentPages
globalTarget.wx = uni
globalTarget.uni = uni
globalTarget.UniViewJSBridge = UniViewJSBridge
globalTarget.UniServiceJSBridge = UniServiceJSBridge
globalTarget.rpx2px = upx2px
globalTarget.__setupPage = (component) => setupPage(component)
globalTarget.__uniConfig = {
  ...(pagesConfig || {}),
  appId: 'baicells-site-manager-h5',
  appName: 'Baicells Sites Manager',
  appVersion: '1.0.0',
  appVersionCode: '10000',
  debug: true,
  networkTimeout: {
    request: 60000,
    uploadFile: 60000,
    downloadFile: 60000,
    connectSocket: 60000,
  },
  router: {
    mode: 'hash',
    base: '/',
    routerBase: '/',
    assets: '/',
    strict: false,
  },
  async: APP_ASYNC_CONFIG,
  locale: 'zh',
  fallbackLocale: 'zh',
  darkmode: false,
  themeConfig: {},
  tabBar: pagesConfig?.tabBar,
  nvue: {
    'flex-direction': 'column',
  },
}
globalTarget.__uniRoutes = routes.map((route) => {
  route.meta.route = String(route.alias || route.path).replace(/^\//, '')
  return route
})

export {}
