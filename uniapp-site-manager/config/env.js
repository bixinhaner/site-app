/**
 * 环境配置管理
 * 根据构建时的环境变量加载对应配置
 */

// 构建时注入的环境配置
// 这些值会在构建脚本中被实际的配置替换
const ENV_CONFIG = {
  API_BASE_URL: '__API_BASE_URL__',
  APP_NAME: '__APP_NAME__',
  APP_VERSION: '__APP_VERSION__',
  DEBUG: '__DEBUG__'
}

// 运行时环境检测
const getEnvironment = () => {
  // #ifdef H5
  return 'h5'
  // #endif

  // #ifdef APP-PLUS
  return 'app'
  // #endif

  // #ifdef MP-WEIXIN
  return 'weixin'
  // #endif

  // #ifdef MP-ALIPAY
  return 'alipay'
  // #endif

  return 'unknown'
}

// 配置验证
const validateConfig = (config) => {
  if (!config.API_BASE_URL || config.API_BASE_URL === '__API_BASE_URL__') {
    console.info('[ENV] 开发模式：使用默认API配置')
    return false
  }
  return true
}

// 获取App版本号（优先从manifest.json读取）
const getAppVersion = () => {
  // #ifdef APP-PLUS
  // App端：从plus.runtime获取manifest.json中的版本号
  try {
    if (typeof plus !== 'undefined' && plus.runtime) {
      return plus.runtime.version || '1.0.0'
    }
  } catch (e) {
    console.warn('[ENV] 获取App版本失败:', e)
  }
  // #endif

  // 其他端或获取失败时的默认值
  return '1.0.0'
}

// 获取配置
const getConfig = () => {
  const config = { ...ENV_CONFIG }

  // 如果配置未被替换，使用开发环境默认值
  if (!validateConfig(config)) {
    // 开发环境使用网络地址，同时支持本地和移动设备访问
    //config.API_BASE_URL = 'http://113.45.25.135/api'
    config.API_BASE_URL = 'http://192.168.2.103:8000'
    config.APP_NAME = '站点管理系统'
    config.APP_VERSION = getAppVersion()
    config.DEBUG = 'true'
  } else {
    // 生产环境也使用动态获取的版本号
    config.APP_VERSION = getAppVersion()
  }

  // 生产环境配置 - 通过80端口访问（简化方案）
  const productionConfig = {
    //API_BASE_URL: 'http://113.45.25.135/api',  // 服务器IP + /api路径
    API_BASE_URL: 'http://192.168.2.103:8000',
    APP_NAME: '站点管理系统',
    APP_VERSION: getAppVersion(),
    DEBUG: 'false'
  }

  // 转换字符串值为对应类型
  config.DEBUG = config.DEBUG === 'true'

  return config
}

export const env = getConfig()
export const environment = getEnvironment()

// 动态获取版本号（供运行时使用，确保获取最新值）
export const getVersion = () => {
  // #ifdef APP-PLUS
  try {
    // 方式1: 使用uni.getAppBaseInfo (推荐，兼容性好)
    const appInfo = uni.getAppBaseInfo()
    if (appInfo && appInfo.appVersion) {
      return appInfo.appVersion
    }

    // 方式2: 使用plus.runtime (备选)
    if (typeof plus !== 'undefined' && plus.runtime && plus.runtime.version) {
      return plus.runtime.version
    }
  } catch (e) {
    console.warn('[ENV] 获取版本号失败:', e)
  }
  // #endif

  // H5/小程序端或获取失败时返回默认值
  return env.APP_VERSION || '1.0.0'
}

// 日志函数
export const log = (...args) => {
  if (env.DEBUG) {
    console.log('[ENV]', ...args)
  }
}