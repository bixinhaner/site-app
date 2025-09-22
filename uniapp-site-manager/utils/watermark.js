/**
 * 照片水印工具类
 * 支持GPS坐标、时间戳、检查员信息等水印添加
 */

export class WatermarkTool {
  constructor() {
    this.canvasContext = null
    this.config = {
      watermarkColor: '#FF6600', // 橙色主题
      backgroundColor: 'rgba(0, 0, 0, 0.7)', // 半透明黑色背景
      fontSize: 28, // 字体大小
      padding: 15, // 内边距
      margin: 20, // 外边距
      lineHeight: 35, // 行高
      borderRadius: 8, // 圆角
      maxWidth: 0.9, // 水印最大宽度比例
      position: 'bottomLeft' // 水印位置: bottomLeft, bottomRight, topLeft, topRight
    }
  }

  /**
   * 为照片添加水印
   * @param {string} imagePath - 原始照片路径
   * @param {Object} watermarkData - 水印数据
   * @returns {Promise<string>} - 带水印的照片路径
   */
  async addWatermark(imagePath, watermarkData) {
    try {
      console.log('开始添加水印:', { imagePath, watermarkData })
      
      // 获取图片信息
      const imageInfo = await this.getImageInfo(imagePath)
      console.log('图片信息:', imageInfo)
      
      // 创建canvas
      const canvas = await this.createCanvas(imageInfo.width, imageInfo.height)
      
      // 绘制原始图片
      await this.drawImage(canvas, imagePath, imageInfo)
      
      // 绘制水印
      await this.drawWatermark(canvas, watermarkData, imageInfo)
      
      // 保存带水印的图片
      const watermarkedPath = await this.saveCanvasToFile(canvas)
      
      console.log('水印添加完成:', watermarkedPath)
      return watermarkedPath
      
    } catch (error) {
      console.error('添加水印失败:', error)
      throw new Error('水印添加失败: ' + error.message)
    }
  }

  /**
   * 获取图片信息
   */
  async getImageInfo(imagePath) {
    return new Promise((resolve, reject) => {
      uni.getImageInfo({
        src: imagePath,
        success: (res) => {
          resolve({
            width: res.width,
            height: res.height,
            path: res.path,
            type: res.type
          })
        },
        fail: (error) => {
          reject(new Error('获取图片信息失败: ' + error.errMsg))
        }
      })
    })
  }

  /**
   * 创建canvas
   */
  async createCanvas(width, height) {
    const canvasId = 'watermark-canvas-' + Date.now()
    
    // 创建canvas组件实例
    const canvas = {
      canvasId,
      width,
      height,
      context: uni.createCanvasContext(canvasId)
    }
    
    this.canvasContext = canvas.context
    return canvas
  }

  /**
   * 绘制原始图片到canvas
   */
  async drawImage(canvas, imagePath, imageInfo) {
    return new Promise((resolve, reject) => {
      const ctx = canvas.context
      
      // 绘制图片
      ctx.drawImage(imagePath, 0, 0, imageInfo.width, imageInfo.height)
      
      // 等待绘制完成
      ctx.draw(false, () => {
        resolve()
      })
    })
  }

  /**
   * 绘制水印
   */
  async drawWatermark(canvas, watermarkData, imageInfo) {
    const ctx = canvas.context
    const config = this.config
    
    // 准备水印文本
    const watermarkLines = this.prepareWatermarkText(watermarkData)
    
    // 计算水印尺寸
    const watermarkSize = this.calculateWatermarkSize(ctx, watermarkLines)
    
    // 计算水印位置
    const position = this.calculateWatermarkPosition(imageInfo, watermarkSize)
    
    // 绘制水印背景
    this.drawWatermarkBackground(ctx, position, watermarkSize)
    
    // 绘制水印文本
    this.drawWatermarkText(ctx, watermarkLines, position)
    
    // 绘制到canvas
    return new Promise((resolve) => {
      ctx.draw(true, () => {
        resolve()
      })
    })
  }

  /**
   * 准备水印文本内容
   */
  prepareWatermarkText(watermarkData) {
    const lines = []
    
    // GPS坐标信息
    if (watermarkData.gps && watermarkData.gps.latitude) {
      lines.push(`📍 ${watermarkData.gps.latitude.toFixed(6)}, ${watermarkData.gps.longitude.toFixed(6)}`)
      
      if (watermarkData.gps.accuracy) {
        lines.push(`📊 精度: ${watermarkData.gps.accuracy.toFixed(1)}m`)
      }
      
      if (watermarkData.gps.address) {
        lines.push(`🏠 ${watermarkData.gps.address}`)
      }
    }
    
    // 时间信息
    if (watermarkData.timestamp) {
      const date = new Date(watermarkData.timestamp)
      lines.push(`🕐 ${date.toLocaleString('zh-CN')}`)
    }
    
    // 检查员信息
    if (watermarkData.inspector) {
      lines.push(`👤 ${watermarkData.inspector}`)
    }
    
    // 检查项信息
    if (watermarkData.checkItem) {
      lines.push(`📋 ${watermarkData.checkItem}`)
    }
    
    // 站点信息
    if (watermarkData.siteName) {
      lines.push(`🏗️ ${watermarkData.siteName}`)
    }
    
    return lines
  }

  /**
   * 计算水印尺寸
   */
  calculateWatermarkSize(ctx, lines) {
    const config = this.config
    
    // 设置字体
    ctx.setFontSize(config.fontSize)
    
    let maxWidth = 0
    lines.forEach(line => {
      const width = ctx.measureText(line).width
      maxWidth = Math.max(maxWidth, width)
    })
    
    return {
      width: maxWidth + config.padding * 2,
      height: lines.length * config.lineHeight + config.padding * 2
    }
  }

  /**
   * 计算水印位置
   */
  calculateWatermarkPosition(imageInfo, watermarkSize) {
    const config = this.config
    const margin = config.margin
    
    let x, y
    
    switch (config.position) {
      case 'topLeft':
        x = margin
        y = margin
        break
      case 'topRight':
        x = imageInfo.width - watermarkSize.width - margin
        y = margin
        break
      case 'bottomRight':
        x = imageInfo.width - watermarkSize.width - margin
        y = imageInfo.height - watermarkSize.height - margin
        break
      case 'bottomLeft':
      default:
        x = margin
        y = imageInfo.height - watermarkSize.height - margin
        break
    }
    
    return { x, y }
  }

  /**
   * 绘制水印背景
   */
  drawWatermarkBackground(ctx, position, size) {
    const config = this.config
    
    // 设置背景样式
    ctx.setFillStyle(config.backgroundColor)
    
    // 绘制圆角矩形背景
    this.drawRoundedRect(ctx, position.x, position.y, size.width, size.height, config.borderRadius)
    ctx.fill()
  }

  /**
   * 绘制水印文本
   */
  drawWatermarkText(ctx, lines, position) {
    const config = this.config
    
    // 设置文本样式
    ctx.setFillStyle(config.watermarkColor)
    ctx.setFontSize(config.fontSize)
    ctx.setTextAlign('left')
    
    // 绘制每一行文本
    lines.forEach((line, index) => {
      const x = position.x + config.padding
      const y = position.y + config.padding + (index + 1) * config.lineHeight - 8
      
      ctx.fillText(line, x, y)
    })
  }

  /**
   * 绘制圆角矩形
   */
  drawRoundedRect(ctx, x, y, width, height, radius) {
    ctx.beginPath()
    ctx.moveTo(x + radius, y)
    ctx.lineTo(x + width - radius, y)
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius)
    ctx.lineTo(x + width, y + height - radius)
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height)
    ctx.lineTo(x + radius, y + height)
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius)
    ctx.lineTo(x, y + radius)
    ctx.quadraticCurveTo(x, y, x + radius, y)
    ctx.closePath()
  }

  /**
   * 保存canvas为文件
   */
  async saveCanvasToFile(canvas) {
    return new Promise((resolve, reject) => {
      // 生成临时文件路径
      const tempPath = `${wx.env.USER_DATA_PATH}/watermarked_${Date.now()}.jpg`
      
      uni.canvasToTempFilePath({
        canvasId: canvas.canvasId,
        destWidth: canvas.width,
        destHeight: canvas.height,
        quality: 0.9,
        fileType: 'jpg',
        success: (res) => {
          resolve(res.tempFilePath)
        },
        fail: (error) => {
          reject(new Error('保存canvas失败: ' + error.errMsg))
        }
      })
    })
  }

  /**
   * 生成照片哈希值（用于防篡改）
   */
  async generatePhotoHash(imagePath) {
    try {
      const fileInfo = await uni.getFileInfo({
        filePath: imagePath
      })
      
      // 简单的哈希算法（实际项目中应使用更强的算法）
      const hash = this.simpleHash(imagePath + fileInfo.size + Date.now())
      return hash
    } catch (error) {
      console.error('生成哈希失败:', error)
      return null
    }
  }

  /**
   * 简单哈希算法
   */
  simpleHash(str) {
    let hash = 0
    if (str.length === 0) return hash.toString()
    
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash = hash & hash // 转换为32位整数
    }
    
    return Math.abs(hash).toString(16)
  }

  /**
   * 设置水印配置
   */
  setConfig(newConfig) {
    this.config = { ...this.config, ...newConfig }
  }
}

// 导出单例实例
export const watermarkTool = new WatermarkTool()

// 默认导出类
export default WatermarkTool