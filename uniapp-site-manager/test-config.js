// 测试配置加载
import { env } from './config/env.js'
import { API_CONFIG, buildApiUrl, API_ENDPOINTS } from './config/api.js'

console.log('=== 配置测试 ===')
console.log('环境配置:', env)
console.log('API配置:', API_CONFIG)
console.log('登录URL:', buildApiUrl(API_ENDPOINTS.AUTH.LOGIN))
console.log('================')