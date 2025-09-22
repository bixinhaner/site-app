/**
 * 水印配置文件
 * 包含水印样式、安全设置等配置项
 */

export const watermarkConfig = {
  // 基础样式配置
  style: {
    fontSize: 28,           // 字体大小
    fontFamily: 'Arial',    // 字体族
    textColor: '#FF6600',   // 文字颜色（橙色主题）
    backgroundColor: 'rgba(0, 0, 0, 0.7)', // 背景颜色
    padding: 15,            // 内边距
    margin: 20,             // 外边距
    lineHeight: 35,         // 行高
    borderRadius: 8,        // 圆角
    maxWidth: 0.9,          // 最大宽度比例
    shadowColor: 'rgba(0, 0, 0, 0.5)', // 阴影颜色
    shadowBlur: 4           // 阴影模糊度
  },
  
  // 水印位置配置
  position: {
    default: 'bottomLeft',  // 默认位置
    options: ['topLeft', 'topRight', 'bottomLeft', 'bottomRight', 'center']
  },
  
  // 水印内容配置
  content: {
    includeGPS: true,       // 包含GPS坐标
    includeTime: true,      // 包含时间戳
    includeInspector: true, // 包含检查员信息
    includeCheckItem: true, // 包含检查项信息
    includeSite: true,      // 包含站点信息
    includeAccuracy: true,  // 包含GPS精度
    includeAddress: false,  // 包含详细地址（可选）
    customPrefix: '现场检查', // 自定义前缀
    customSuffix: '- 质量追溯' // 自定义后缀
  },
  
  // 质量和性能配置
  quality: {
    outputQuality: 0.9,     // 输出图片质量 (0.1-1.0)
    fileType: 'jpg',        // 输出文件类型
    maxFileSize: 5 * 1024 * 1024, // 最大文件大小 (5MB)
    compression: true       // 是否压缩
  },
  
  // 安全配置
  security: {
    enableHash: true,       // 启用文件哈希
    enableSignature: true,  // 启用数字签名
    hashAlgorithm: 'sha256', // 哈希算法
    enableTamperDetection: true, // 启用防篡改检测
    watermarkVersion: '1.0', // 水印版本
    securityLevel: 'high'   // 安全级别: low, medium, high
  },
  
  // 高级功能配置
  advanced: {
    enableOffline: true,    // 离线模式支持
    enablePreview: true,    // 预览功能
    enableMultiple: false,  // 多水印模式
    enableAnimation: false, // 动画效果
    debugMode: false,       // 调试模式
    logLevel: 'info'        // 日志级别: debug, info, warn, error
  },
  
  // 本地化配置
  localization: {
    language: 'zh-CN',      // 语言
    dateFormat: 'YYYY-MM-DD HH:mm:ss', // 日期格式
    coordinateFormat: 'decimal', // 坐标格式: decimal, dms
    coordinatePrecision: 6  // 坐标精度（小数位数）
  },
  
  // 错误处理配置
  errorHandling: {
    fallbackToOriginal: true, // 失败时使用原图
    retryAttempts: 3,        // 重试次数
    retryDelay: 1000,        // 重试延迟（毫秒）
    showErrorToast: true     // 显示错误提示
  }
}

// 水印文本模板
export const watermarkTemplates = {
  // 标准模板
  standard: {
    gps: '📍 {latitude}, {longitude}',
    accuracy: '📊 精度: {accuracy}m',
    time: '🕐 {timestamp}',
    inspector: '👤 {inspector}',
    checkItem: '📋 {checkItem}',
    site: '🏗️ {siteName}',
    custom: '✓ {customText}'
  },
  
  // 简洁模板
  minimal: {
    gps: '{latitude}, {longitude}',
    time: '{timestamp}',
    inspector: '{inspector}'
  },
  
  // 详细模板
  detailed: {
    header: '== 现场检查记录 ==',
    gps: '坐标: {latitude}, {longitude}',
    accuracy: 'GPS精度: {accuracy}m',
    time: '时间: {timestamp}',
    inspector: '检查员: {inspector}',
    checkItem: '检查项: {checkItem}',
    site: '站点: {siteName}',
    footer: '-- 质量追溯系统 --'
  }
}

// 安全哈希函数
export const securityUtils = {
  /**
   * 生成简单哈希值
   */
  generateSimpleHash(data) {
    let hash = 0
    const str = JSON.stringify(data)
    
    if (str.length === 0) return hash.toString()
    
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash = hash & hash // 转换为32位整数
    }
    
    return Math.abs(hash).toString(16)
  },
  
  /**
   * 生成时间戳签名
   */
  generateTimestamp() {
    return Date.now().toString()
  },
  
  /**
   * 验证数据完整性
   */
  verifyIntegrity(originalHash, currentData) {
    const currentHash = this.generateSimpleHash(currentData)
    return originalHash === currentHash
  },
  
  /**
   * 生成数字签名
   */
  generateSignature(data, secretKey = 'watermark_secret_2024') {
    const combined = JSON.stringify(data) + secretKey + this.generateTimestamp()
    return this.generateSimpleHash(combined)
  }
}

// 导出默认配置
export default watermarkConfig