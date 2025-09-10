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

// 获取配置
const getConfig = () => {
  const config = { ...ENV_CONFIG }
  
  // 如果配置未被替换，使用开发环境默认值
  if (!validateConfig(config)) {
    // 开发环境使用实际IP地址
    config.API_BASE_URL = 'http://192.168.2.100:8000'
    config.APP_NAME = '站点管理系统'
    config.APP_VERSION = '1.0.0'
    config.DEBUG = 'true'
  }
  
  // 转换字符串值为对应类型
  config.DEBUG = config.DEBUG === 'true'
  
  return config
}

export const env = getConfig()
export const environment = getEnvironment()

// 日志函数
export const log = (...args) => {
  if (env.DEBUG) {
    console.log('[ENV]', ...args)
  }
}