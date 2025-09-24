// 环境配置文件 - 统一管理API地址
// 部署时只需要修改这个文件即可

// 自动检测运行环境
const getBaseURL = () => {
  // 如果在构建时定义了环境变量，优先使用
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }
  
  // 如果是生产构建且在浏览器中运行
  if (import.meta.env.PROD && typeof window !== 'undefined') {
    // 使用相对路径，自动适配当前域名
    return window.location.origin
  }
  
  // 开发环境默认配置
  return 'http://localhost:8000'
}

const config = {
  // API基础地址
  API_BASE_URL: getBaseURL(),
  
  // 请求超时时间
  TIMEOUT: 10000,
  
  // 是否启用请求日志
  ENABLE_REQUEST_LOG: import.meta.env.DEV,
  
  // 文件上传大小限制 (MB)
  MAX_FILE_SIZE: 10
}

// 开发模式下打印配置信息
if (import.meta.env.DEV) {
  console.log('🔧 Environment Config:', config)
}

export default config