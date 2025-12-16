/**
 * 照片水印工具类
 * 支持GPS坐标、时间戳、检查员信息等水印添加
 * 集成地理编码服务，自动获取详细地址信息
 */

// 移除复杂的geocoding依赖，使用统一定位策略

import { getLocationWithAddressStrategy } from './locationStrategy.js'

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

    // 基于图片尺寸计算动态样式（短边约 2.5% 作为字号基准）
    const style = this.getScaledStyle(imageInfo)
    
    // 计算水印尺寸
    const watermarkSize = this.calculateWatermarkSize(ctx, watermarkLines, style, imageInfo)
    
    // 计算水印位置
    const position = this.calculateWatermarkPosition(imageInfo, watermarkSize, style)
    
    // 绘制水印背景
    this.drawWatermarkBackground(ctx, position, watermarkSize, style)
    
    // 绘制水印文本
    this.drawWatermarkText(ctx, watermarkLines, position, style)
    
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
   * 根据图片尺寸计算缩放后的样式
   * 使用图片短边约 2.5% 作为目标字号，并对缩放比例做上下限约束
   */
  getScaledStyle(imageInfo) {
    const base = Math.min(imageInfo.width, imageInfo.height) || 0
    const config = this.config

    // 目标字号：短边的 2.5%
    const targetFontSize = base * 0.025
    // 以配置中的 fontSize 作为参考，计算缩放因子
    let scale = config.fontSize > 0 ? targetFontSize / config.fontSize : 1

    // 限制缩放范围，避免极端大图或小图
    const minScale = 0.8
    const maxScale = 3.0
    if (!isFinite(scale) || scale <= 0) scale = 1
    scale = Math.max(minScale, Math.min(maxScale, scale))

    return {
      fontSize: config.fontSize * scale,
      padding: config.padding * scale,
      margin: config.margin * scale,
      lineHeight: config.lineHeight * scale,
      borderRadius: config.borderRadius * scale,
    }
  }

  /**
   * 计算水印尺寸
   */
  calculateWatermarkSize(ctx, lines, style, imageInfo) {
    const config = this.config

    // 设置字体
    ctx.setFontSize(style.fontSize)
    
    let maxWidth = 0
    lines.forEach(line => {
      const width = ctx.measureText(line).width
      maxWidth = Math.max(maxWidth, width)
    })

    let width = maxWidth + style.padding * 2
    const height = lines.length * style.lineHeight + style.padding * 2

    // 可选：限制水印宽度不超过图片宽度的一定比例
    if (typeof config.maxWidth === 'number' && config.maxWidth > 0 && config.maxWidth <= 1 && imageInfo?.width) {
      const maxAllowedWidth = imageInfo.width * config.maxWidth
      if (width > maxAllowedWidth) {
        width = maxAllowedWidth
      }
    }

    return {
      width,
      height,
    }
  }

  /**
   * 计算水印位置
   */
  calculateWatermarkPosition(imageInfo, watermarkSize, style) {
    const config = this.config
    const margin = style.margin
    
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
  drawWatermarkBackground(ctx, position, size, style) {
    const config = this.config
    
    // 设置背景样式
    ctx.setFillStyle(config.backgroundColor)
    
    // 绘制圆角矩形背景
    this.drawRoundedRect(ctx, position.x, position.y, size.width, size.height, style.borderRadius)
    ctx.fill()
  }

  /**
   * 绘制水印文本
   */
  drawWatermarkText(ctx, lines, position, style) {
    const config = this.config
    
    // 设置文本样式
    ctx.setFillStyle(config.watermarkColor)
    ctx.setFontSize(style.fontSize)
    ctx.setTextAlign('left')
    
    // 绘制每一行文本
    lines.forEach((line, index) => {
      const x = position.x + style.padding
      const y = position.y + style.padding + (index + 1) * style.lineHeight - 8
      
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
   * 自动获取GPS信息并添加水印的便捷方法（使用原生定位插件）
   * @param {string} imagePath - 原始照片路径
   * @param {Object} watermarkData - 基础水印数据
   * @param {Object} options - 配置选项
   * @returns {Promise<string>} - 带水印的照片路径
   */
  async addWatermarkWithGPS(imagePath, watermarkData = {}, options = {}) {
    console.log('开始使用原生插件添加GPS水印...')
    
    try {
      // 若外部已提供GPS结果，则直接使用，避免再次调用原生定位
      let locationResult = null
      if (options && options.gpsOverride) {
        console.log('使用传入的GPS覆盖数据:', options.gpsOverride)
        const o = options.gpsOverride || {}
        const data = o.data || {
          latitude: o.latitude,
          longitude: o.longitude,
          accuracy: o.accuracy || 0,
          provider: o.provider || 'native-plugin'
        }
        const addressObj = o.addressInfo || (typeof o.address === 'string' ? { formattedAddress: o.address } : o.address) || (o.formattedAddress ? { formattedAddress: o.formattedAddress } : null)
        locationResult = {
          code: 0,
          success: true,
          data,
          address: addressObj,
          message: '使用外部提供的定位结果'
        }
      } else {
        console.log('开始通过原生插件获取GPS和地址信息...')
        // 使用原生定位插件获取位置信息
        locationResult = await this.getLocationFromNativePlugin()
      }
      
      // 从原生插件结果中提取地址信息
      let address = '位置获取中...'
      let watermarkAddress = []
      
      if (locationResult.success && locationResult.data) {
        const data = locationResult.data
        
        // 如果原生插件返回了地址信息
        if (locationResult.address && typeof locationResult.address === 'object') {
          const addr = locationResult.address
          console.log('原生插件返回详细地址信息:', addr)
          
          // 优先使用格式化地址，如果不存在则手动构建
          if (addr.formattedAddress && addr.formattedAddress.trim()) {
            // 使用原生插件提供的完整格式化地址
            address = addr.formattedAddress
            
            // 为水印显示提取关键地址信息，分行显示更清晰
            const addressLines = []
            
            // 第一行：国家、省份、城市（如果城市为空则跳过）
            const regionParts = [addr.country, addr.province]
            if (addr.city && addr.city.trim()) {
              regionParts.push(addr.city)
            }
            if (regionParts.length > 0) {
              addressLines.push(`🏠 ${regionParts.join(' ')}`)
            }
            
            // 第二行：区县
            if (addr.district && addr.district.trim()) {
              addressLines.push(`📍 ${addr.district}`)
            }
            
            // 第三行：从formattedAddress中提取详细地址信息
            // 由于各个独立字段可能为空，我们从完整地址中解析
            const detailAddress = this.extractDetailedAddress(addr.formattedAddress, addr)
            if (detailAddress) {
              addressLines.push(`🛣️ ${detailAddress}`)
            }
            
            watermarkAddress = addressLines
            
          } else {
            // 手动构建地址（备用方案）
            const addressParts = [
              addr.country,
              addr.province, 
              addr.city,
              addr.district,
              addr.street,
              addr.streetNumber
            ].filter(item => item && item.trim())
            
            if (addressParts.length > 0) {
              address = addressParts.join(' ')
              
              // 分行显示地址信息
              if (addr.country && addr.province) {
                const region = addr.city ? `${addr.country} ${addr.province} ${addr.city}` : `${addr.country} ${addr.province}`
                watermarkAddress.push(`🏠 ${region}`)
              }
              if (addr.district) {
                watermarkAddress.push(`📍 ${addr.district}`)
              }
              if (addr.street) {
                let streetInfo = addr.street
                if (addr.streetNumber) streetInfo += addr.streetNumber
                watermarkAddress.push(`🛣️ ${streetInfo}`)
              }
            } else {
              address = `${data.latitude.toFixed(6)}, ${data.longitude.toFixed(6)}`
              watermarkAddress.push(`📍 坐标: ${address}`)
            }
          }
        } else {
          // 如果没有地址信息，仅显示坐标
          address = `${data.latitude.toFixed(6)}, ${data.longitude.toFixed(6)}`
          watermarkAddress.push(`📍 坐标: ${address}`)
        }
      } else {
        // 原生插件调用失败
        throw new Error(locationResult.message || '原生定位插件调用失败')
      }
      
      console.log('最终地址信息:', address)
      console.log('水印地址数组:', watermarkAddress)
      
      // 构建GPS信息对象
      const gpsInfo = {
        latitude: locationResult.data.latitude,
        longitude: locationResult.data.longitude,
        accuracy: locationResult.data.accuracy || 0,
        address: address,
        watermarkAddress: watermarkAddress,
        timestamp: new Date().toLocaleString('zh-CN'),
        addressInfo: locationResult.address,
        provider: locationResult.data.provider || 'native-plugin'
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
      console.error('原生插件GPS水印添加失败:', error)
      
      // 不再提供降级方案，直接抛出错误
      // 确保只使用原生插件定位，不使用任何备用方案
      const failedGpsInfo = {
        latitude: 0,
        longitude: 0,
        accuracy: 0,
        address: '原生定位插件获取失败',
        watermarkAddress: ['📍 原生定位插件获取失败'],
        timestamp: new Date().toLocaleString('zh-CN'),
        addressError: error.message,
        provider: 'native-plugin-failed'
      }
      
      // 即使失败也添加失败信息的水印
      return await this.addWatermark(imagePath, {
        ...watermarkData,
        gps: failedGpsInfo,
        timestamp: new Date().toLocaleString('zh-CN')
      }, options.canvasId)
    }
  }

  /**
   * 批量处理照片水印（支持多张照片同时处理，使用原生定位插件）
   * @param {Array<string>} imagePaths - 照片路径数组
   * @param {Object} watermarkData - 共同的水印数据
   * @param {Object} options - 配置选项
   * @returns {Promise<Array<Object>>} - 处理结果数组
   */
  async addWatermarkBatch(imagePaths, watermarkData = {}, options = {}) {
    const results = []
    
    // 获取一次GPS信息，用于所有照片（使用原生插件）
    let gpsInfo = null
    if (options.useGPS !== false) {
      try {
        const locationResult = await this.getLocationFromNativePlugin()
        
        if (locationResult.success && locationResult.data) {
          const data = locationResult.data
          let address = '位置获取中...'
          let watermarkAddress = []
          
          // 如果原生插件返回了地址信息（使用与单张照片相同的处理逻辑）
          if (locationResult.address && typeof locationResult.address === 'object') {
            const addr = locationResult.address
            
            // 优先使用格式化地址
            if (addr.formattedAddress && addr.formattedAddress.trim()) {
              address = addr.formattedAddress
              
              // 为水印显示提取关键地址信息
              const addressLines = []
              
              // 第一行：国家、省份、城市
              const regionParts = [addr.country, addr.province]
              if (addr.city && addr.city.trim()) {
                regionParts.push(addr.city)
              }
              if (regionParts.length > 0) {
                addressLines.push(`🏠 ${regionParts.join(' ')}`)
              }
              
              // 第二行：区县
              if (addr.district && addr.district.trim()) {
                addressLines.push(`📍 ${addr.district}`)
              }
              
              // 第三行：从formattedAddress中提取详细地址信息
              const detailAddress = this.extractDetailedAddress(addr.formattedAddress, addr)
              if (detailAddress) {
                addressLines.push(`🛣️ ${detailAddress}`)
              }
              
              watermarkAddress = addressLines
              
            } else {
              // 手动构建地址（备用方案）
              const addressParts = [
                addr.country, addr.province, addr.city, addr.district, addr.street, addr.streetNumber
              ].filter(item => item && item.trim())
              
              if (addressParts.length > 0) {
                address = addressParts.join(' ')
                
                if (addr.country && addr.province) {
                  const region = addr.city ? `${addr.country} ${addr.province} ${addr.city}` : `${addr.country} ${addr.province}`
                  watermarkAddress.push(`🏠 ${region}`)
                }
                if (addr.district) watermarkAddress.push(`📍 ${addr.district}`)
                if (addr.street) {
                  let streetInfo = addr.street
                  if (addr.streetNumber) streetInfo += addr.streetNumber
                  watermarkAddress.push(`🛣️ ${streetInfo}`)
                }
              } else {
                address = `${data.latitude.toFixed(6)}, ${data.longitude.toFixed(6)}`
                watermarkAddress.push(`📍 坐标: ${address}`)
              }
            }
          } else {
            address = `${data.latitude.toFixed(6)}, ${data.longitude.toFixed(6)}`
            watermarkAddress.push(`📍 坐标: ${address}`)
          }
          
          gpsInfo = {
            latitude: data.latitude,
            longitude: data.longitude,
            accuracy: data.accuracy || 0,
            address: address,
            watermarkAddress: watermarkAddress,
            timestamp: new Date().toLocaleString('zh-CN'),
            addressInfo: locationResult.address,
            provider: 'native-plugin'
          }
          
          console.log('批量处理原生插件GPS信息获取成功')
        } else {
          throw new Error(locationResult.message || '原生定位插件批量调用失败')
        }
      } catch (error) {
        console.warn('批量处理原生插件GPS获取失败:', error.message)
        // 不再提供降级方案
        gpsInfo = {
          latitude: 0,
          longitude: 0,
          accuracy: 0,
          address: '原生定位插件获取失败',
          watermarkAddress: ['📍 原生定位插件获取失败'],
          timestamp: new Date().toLocaleString('zh-CN'),
          addressError: error.message,
          provider: 'native-plugin-failed'
        }
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
   * 使用定位策略获取位置和地址信息
   * @returns {Promise<Object>} 定位结果（结构与原生封装保持一致）
   */
  async getLocationFromNativePlugin() {
    try {
      console.log('开始通过定位策略获取定位信息...')
      const result = await getLocationWithAddressStrategy()
      console.log('定位策略结果:', result)

      if (result && result.success && result.data) {
        return result
      }

      throw new Error(result?.message || '定位失败')
    } catch (error) {
      console.error('调用定位策略封装失败:', error)
      throw new Error('无法获取定位信息: ' + error.message)
    }
  }

  /**
   * 从完整地址中提取详细地址信息
   * @param {string} formattedAddress - 格式化的完整地址
   * @param {Object} addr - 地址对象
   * @returns {string} 详细地址信息
   */
  extractDetailedAddress(formattedAddress, addr) {
    try {
      // formattedAddress 格式: "China, Bei Jing Shi, Hai Dian Qu, Zhongguancun, 理想国际大厦708室 邮政编码: 100086"
      
      // 移除邮政编码部分
      let cleanAddress = formattedAddress.replace(/\s*邮政编码:\s*\d+\s*$/, '').trim()
      
      // 分割地址组件
      const parts = cleanAddress.split(',').map(part => part.trim())
      
      // 已知的组件：country, province, district
      const knownParts = []
      if (addr.country) knownParts.push(addr.country)
      if (addr.province) knownParts.push(addr.province)
      if (addr.district) knownParts.push(addr.district)
      
      // 找到详细地址部分（去除已知的行政区划）
      const detailParts = []
      for (const part of parts) {
        // 跳过已知的行政区划部分
        if (!knownParts.some(known => part.includes(known) || known.includes(part))) {
          detailParts.push(part)
        }
      }
      
      // 返回详细地址（街道、建筑物等）
      return detailParts.length > 0 ? detailParts.join(', ') : ''
      
    } catch (error) {
      console.warn('解析详细地址失败:', error)
      return ''
    }
  }

  /**
   * 原生定位插件配置
   */
  setNativeLocationConfig(options = {}) {
    console.log('配置原生定位插件参数')
    this.nativeLocationOptions = {
      timeout: options.timeout || 30000,
      enableAddress: options.enableAddress !== false,
      highAccuracy: options.highAccuracy !== false
    }
  }
}

// 导出单例实例
export const watermarkTool = new WatermarkTool()

// 默认导出类
export default WatermarkTool
