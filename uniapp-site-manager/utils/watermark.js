/**
 * 照片水印工具类
 * 支持GPS坐标、时间戳、检查员信息等水印添加
 * 集成地理编码服务，自动获取详细地址信息
 */

// 移除复杂的geocoding依赖，使用UniApp内置功能

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
   * @param {string} canvasId - 可选的canvas ID，如果不提供则创建新的
   * @returns {Promise<string>} - 带水印的照片路径
   */
  async addWatermark(imagePath, watermarkData, canvasId = null) {
    try {
      console.log('开始添加水印:', { imagePath, watermarkData })
      
      // 获取图片信息
      const imageInfo = await this.getImageInfo(imagePath)
      console.log('图片信息:', imageInfo)
      
      let canvas
      if (canvasId) {
        // 使用外部提供的canvas
        canvas = {
          canvasId: canvasId,
          width: imageInfo.width,
          height: imageInfo.height,
          context: uni.createCanvasContext(canvasId)
        }
        console.log('使用外部canvas:', canvasId)
      } else {
        // 创建新的canvas
        canvas = await this.createCanvas(imageInfo.width, imageInfo.height)
        console.log('创建新canvas:', canvas.canvasId)
      }
      
      // 绘制原始图片
      await this.drawImage(canvas, imagePath, imageInfo)
      
      // 绘制水印
      await this.drawWatermark(canvas, watermarkData, imageInfo)
      
      // 保存带水印的图片
      const watermarkedPath = await this.saveCanvasToFile(canvas, imageInfo)
      
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
    
    // GPS坐标和地址信息
    if (watermarkData.gps) {
      // 坐标信息（如果有有效坐标）
      if (watermarkData.gps.latitude && watermarkData.gps.longitude) {
        lines.push(`📍 ${watermarkData.gps.latitude.toFixed(6)}, ${watermarkData.gps.longitude.toFixed(6)}`)
        
        // 精度信息
        if (watermarkData.gps.accuracy > 0) {
          lines.push(`📊 精度: ${watermarkData.gps.accuracy.toFixed(1)}m`)
        }
        
        // 详细地址信息（如果有增强的地址数据）
        if (watermarkData.gps.watermarkAddress && watermarkData.gps.watermarkAddress.length > 0) {
          // 使用格式化的地址信息
          watermarkData.gps.watermarkAddress.forEach(addressLine => {
            lines.push(addressLine)
          })
        } else if (watermarkData.gps.address && watermarkData.gps.address !== 'GPS获取失败') {
          // 兜底显示基本地址
          lines.push(`🏠 ${watermarkData.gps.address}`)
        }
        
        // 如果有详细地址信息，显示街道信息
        if (watermarkData.gps.addressInfo) {
          const addrInfo = watermarkData.gps.addressInfo
          
          // 显示街道和门牌号
          if (addrInfo.street && !lines.some(line => line.includes(addrInfo.street))) {
            let streetInfo = addrInfo.street
            if (addrInfo.street_number) {
              streetInfo += addrInfo.street_number
            }
            lines.push(`🛣️ ${streetInfo}`)
          }
          
          // 显示POI信息（如果启用且存在）
          if (addrInfo.poi_name && watermarkData.options?.showPOI) {
            lines.push(`🏪 ${addrInfo.poi_name}`)
          }
        }
      } else {
        // GPS获取失败的情况
        if (watermarkData.gps.address === 'GPS获取失败') {
          lines.push(`📍 GPS获取失败`)
          if (watermarkData.gps.addressError) {
            lines.push(`⚠️ ${watermarkData.gps.addressError}`)
          }
        }
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
  async saveCanvasToFile(canvas, imageInfo) {
    return new Promise((resolve, reject) => {
      console.log('开始保存Canvas:', {
        canvasId: canvas.canvasId,
        width: imageInfo?.width || canvas.width,
        height: imageInfo?.height || canvas.height
      })
      
      uni.canvasToTempFilePath({
        canvasId: canvas.canvasId,
        destWidth: imageInfo?.width || canvas.width,
        destHeight: imageInfo?.height || canvas.height,
        quality: 0.9,
        fileType: 'jpg',
        success: (res) => {
          console.log('Canvas保存成功:', res.tempFilePath)
          if (res.tempFilePath) {
            resolve(res.tempFilePath)
          } else {
            reject(new Error('Canvas保存成功但未返回文件路径'))
          }
        },
        fail: (error) => {
          console.error('Canvas保存失败:', error)
          reject(new Error('保存canvas失败: ' + (error.errMsg || error.message || 'Unknown error')))
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

  /**
   * 自动获取GPS信息并添加水印的便捷方法
   * @param {string} imagePath - 原始照片路径
   * @param {Object} watermarkData - 基础水印数据
   * @param {Object} options - 配置选项
   * @returns {Promise<string>} - 带水印的照片路径
   */
  async addWatermarkWithGPS(imagePath, watermarkData = {}, options = {}) {
    console.log('开始添加GPS水印...')
    
    try {
      console.log('开始获取GPS和地址信息...')
      
      // 使用UniApp内置的geocode功能，最简单的方式
      const locationResult = await new Promise((resolve, reject) => {
        uni.getLocation({
          type: 'gcj02',
          geocode: true, // 启用地址解析
          isHighAccuracy: true,
          success: (res) => {
            console.log('高精度GPS定位成功:', res)
            resolve(res)
          },
          fail: (error) => {
            console.log('高精度定位失败，尝试普通精度:', error)
            // 降级到普通精度
            uni.getLocation({
              type: 'gcj02',
              geocode: true,
              isHighAccuracy: false,
              success: (res) => {
                console.log('普通精度定位成功:', res)
                resolve(res)
              },
              fail: (err) => {
                console.error('定位完全失败:', err)
                reject(err)
              }
            })
          }
        })
      })
      
      // 提取地址信息
      let address = '位置获取中...'
      let watermarkAddress = []
      
      if (locationResult.address && (locationResult.address.city || locationResult.address.province)) {
        // 如果有详细地址信息
        const addr = locationResult.address
        console.log('获取到详细地址信息:', addr)
        
        // 构建完整地址
        const fullAddress = [
          addr.country,
          addr.province, 
          addr.city,
          addr.district,
          addr.street,
          addr.streetNum,
          addr.poiName
        ].filter(item => item && item.trim()).join('')
        
        address = fullAddress || `${locationResult.latitude.toFixed(6)}, ${locationResult.longitude.toFixed(6)}`
        
        // 分行显示地址信息
        if (addr.country && addr.province && addr.city) {
          watermarkAddress.push(`🏠 ${addr.country}${addr.province}${addr.city}`)
        }
        if (addr.district) {
          watermarkAddress.push(`📍 ${addr.district}`)
        }
        if (addr.street) {
          let streetInfo = addr.street
          if (addr.streetNum) streetInfo += addr.streetNum
          watermarkAddress.push(`🛣️ ${streetInfo}`)
        }
        if (addr.poiName && options.showPOI) {
          watermarkAddress.push(`🏪 ${addr.poiName}`)
        }
      } else {
        // 内置geocode没有返回地址，尝试使用OpenStreetMap API
        console.log('内置geocode未返回地址，尝试OpenStreetMap逆地理编码...')
        try {
          const osmResult = await this.getAddressFromOSM(locationResult.latitude, locationResult.longitude)
          if (osmResult && osmResult.display_name) {
            address = osmResult.display_name
            watermarkAddress.push(`🏠 ${address}`)
            console.log('OpenStreetMap地址获取成功:', address)
            
            // 如果有详细地址组件，添加更多信息
            if (osmResult.address) {
              const addr = osmResult.address
              if (addr.road) {
                watermarkAddress.push(`🛣️ ${addr.road}${addr.house_number || ''}`)
              }
              if (addr.suburb || addr.neighbourhood) {
                watermarkAddress.push(`📍 ${addr.suburb || addr.neighbourhood}`)
              }
            }
          } else {
            throw new Error('OpenStreetMap未返回有效地址')
          }
        } catch (osmError) {
          console.log('OpenStreetMap地址获取失败，使用坐标:', osmError.message)
          // 如果API也失败，显示坐标
          address = `${locationResult.latitude.toFixed(6)}, ${locationResult.longitude.toFixed(6)}`
          watermarkAddress.push(`📍 坐标: ${address}`)
        }
      }
      
      console.log('最终地址信息:', address)
      console.log('水印地址数组:', watermarkAddress)
      
      // 构建GPS信息对象
      const gpsInfo = {
        latitude: locationResult.latitude,
        longitude: locationResult.longitude,
        accuracy: locationResult.accuracy || 0,
        address: address,
        watermarkAddress: watermarkAddress,
        timestamp: new Date().toLocaleString('zh-CN'),
        addressInfo: locationResult.address
      }
      
      // 合并GPS信息到水印数据
      const enhancedWatermarkData = {
        ...watermarkData,
        gps: gpsInfo,
        timestamp: watermarkData.timestamp || new Date().toLocaleString('zh-CN'),
        options: {
          showPOI: options.showPOI || false,
          showAddressDetails: options.showAddressDetails !== false
        }
      }
      
      console.log('增强的水印数据:', enhancedWatermarkData)
      
      // 添加水印
      const result = await this.addWatermark(imagePath, enhancedWatermarkData, options.canvasId)
      console.log('增强水印添加完成:', result)
      
      return result
      
    } catch (error) {
      console.error('添加GPS水印失败:', error)
      
      // 如果允许降级到基础水印
      if (options.fallbackToBasic !== false) {
        console.log('降级到基础水印模式...')
        
        const basicGpsInfo = {
          latitude: 0,
          longitude: 0,
          accuracy: 0,
          address: '位置获取失败',
          watermarkAddress: ['📍 位置获取失败'],
          timestamp: new Date().toLocaleString('zh-CN'),
          addressError: error.message
        }
        
        return await this.addWatermark(imagePath, {
          ...watermarkData,
          gps: basicGpsInfo,
          timestamp: new Date().toLocaleString('zh-CN'),
          options: {
            showPOI: false,
            showAddressDetails: false
          }
        }, options.canvasId)
      }
      
      throw error
    }
  }

  /**
   * 批量处理照片水印（支持多张照片同时处理）
   * @param {Array<string>} imagePaths - 照片路径数组
   * @param {Object} watermarkData - 共同的水印数据
   * @param {Object} options - 配置选项
   * @returns {Promise<Array<Object>>} - 处理结果数组
   */
  async addWatermarkBatch(imagePaths, watermarkData = {}, options = {}) {
    const results = []
    
    // 获取一次GPS信息，用于所有照片
    let gpsInfo = null
    if (options.useGPS !== false) {
      try {
        const locationResult = await new Promise((resolve, reject) => {
          uni.getLocation({
            type: 'gcj02',
            geocode: true,
            isHighAccuracy: true,
            success: resolve,
            fail: reject
          })
        })
        
        let address = '位置获取中...'
        let watermarkAddress = []
        
        if (locationResult.address && (locationResult.address.city || locationResult.address.province)) {
          const addr = locationResult.address
          const fullAddress = [addr.country, addr.province, addr.city, addr.district, addr.street, addr.streetNum, addr.poiName]
            .filter(item => item && item.trim()).join('')
          address = fullAddress || `${locationResult.latitude.toFixed(6)}, ${locationResult.longitude.toFixed(6)}`
          
          if (addr.country && addr.province && addr.city) {
            watermarkAddress.push(`🏠 ${addr.country}${addr.province}${addr.city}`)
          }
          if (addr.district) watermarkAddress.push(`📍 ${addr.district}`)
          if (addr.street) {
            let streetInfo = addr.street
            if (addr.streetNum) streetInfo += addr.streetNum
            watermarkAddress.push(`🛣️ ${streetInfo}`)
          }
          if (addr.poiName && options.showPOI) watermarkAddress.push(`🏪 ${addr.poiName}`)
        } else {
          // 尝试使用OpenStreetMap获取地址
          try {
            const osmResult = await this.getAddressFromOSM(locationResult.latitude, locationResult.longitude)
            if (osmResult && osmResult.display_name) {
              address = osmResult.display_name
              watermarkAddress.push(`🏠 ${address}`)
            } else {
              throw new Error('OSM未返回地址')
            }
          } catch (error) {
            address = `${locationResult.latitude.toFixed(6)}, ${locationResult.longitude.toFixed(6)}`
            watermarkAddress.push(`📍 坐标: ${address}`)
          }
        }
        
        gpsInfo = {
          latitude: locationResult.latitude,
          longitude: locationResult.longitude,
          accuracy: locationResult.accuracy || 0,
          address: address,
          watermarkAddress: watermarkAddress,
          timestamp: new Date().toLocaleString('zh-CN'),
          addressInfo: locationResult.address
        }
        
        console.log('批量处理GPS信息获取成功')
      } catch (error) {
        console.warn('批量处理GPS获取失败，将使用基本模式:', error.message)
      }
    }
    
    // 处理每张照片
    for (let i = 0; i < imagePaths.length; i++) {
      const imagePath = imagePaths[i]
      
      try {
        const enhancedWatermarkData = {
          ...watermarkData,
          gps: gpsInfo,
          timestamp: Date.now(),
          photoIndex: i + 1,
          totalPhotos: imagePaths.length,
          options: {
            showPOI: options.showPOI || false,
            showAddressDetails: options.showAddressDetails !== false
          }
        }
        
        const watermarkedPath = await this.addWatermark(imagePath, enhancedWatermarkData)
        
        results.push({
          originalPath: imagePath,
          watermarkedPath: watermarkedPath,
          success: true,
          index: i
        })
        
        console.log(`照片 ${i + 1}/${imagePaths.length} 水印添加完成`)
        
      } catch (error) {
        console.error(`照片 ${i + 1} 水印添加失败:`, error)
        results.push({
          originalPath: imagePath,
          watermarkedPath: null,
          success: false,
          error: error.message,
          index: i
        })
      }
    }
    
    return results
  }

  /**
   * 使用OpenStreetMap Nominatim逆地理编码获取地址（完全免费，无需key）
   */
  async getAddressFromOSM(latitude, longitude) {
    return new Promise((resolve, reject) => {
      // OpenStreetMap Nominatim API - 完全免费，无需API Key
      const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1&accept-language=zh-CN,zh,en`
      
      uni.request({
        url: url,
        method: 'GET',
        timeout: 8000,
        header: {
          'User-Agent': 'UniApp-SiteManager/1.0'  // OSM要求设置User-Agent
        },
        success: (res) => {
          if (res.statusCode === 200 && res.data && res.data.display_name) {
            resolve(res.data)
          } else {
            reject(new Error('OSM API返回错误: 未找到地址信息'))
          }
        },
        fail: (error) => {
          reject(new Error('OSM API请求失败: ' + error.errMsg))
        }
      })
    })
  }

  /**
   * 简化的地址获取配置
   */
  setGeocodingConfig(options = {}) {
    console.log('使用UniApp内置地理编码功能和高德地图API作为备用')
    this.geocodingOptions = {
      timeout: options.timeout || 10000,
      type: options.type || 'gcj02',
      isHighAccuracy: options.isHighAccuracy !== false
    }
  }
}

// 导出单例实例
export const watermarkTool = new WatermarkTool()

// 默认导出类
export default WatermarkTool