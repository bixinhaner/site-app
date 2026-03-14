/**
 * 照片水印工具类
 * 支持GPS坐标、时间戳、检查员信息等水印添加
 * 集成地理编码服务，自动获取详细地址信息
 */

// 移除复杂的geocoding依赖，使用统一定位策略

import { getLocationWithAddressStrategy } from './locationStrategy.js'
import i18n from './i18n.js'

const t = (key, params = {}) => {
  try {
    const fn = i18n?.global?.t
    if (typeof fn === 'function') return fn.call(i18n.global, key, params)
  } catch (e) {
    // ignore
  }
  return key
}

const pad2 = (value) => String(value).padStart(2, '0')

export const formatWatermarkTimestamp = (input = new Date()) => {
  const date = input instanceof Date ? input : new Date(input)
  if (!Number.isFinite(date.getTime())) return String(input || '')
  return (
    `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}` +
    ` ${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`
  )
}

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
      areaRatio: 0.08, // 水印区域占图片面积比例
      position: 'bottomLeft', // 水印位置: bottomLeft, bottomRight, topLeft, topRight, center
      content: {
        showIcon: true,
        showLocalUploadNote: true,
        showGPS: true,
        showAccuracy: true,
        showAddress: true,
        showTimestamp: true,
        showInspector: true,
        showCheckItem: true,
        showSiteName: true,
        coordinatePrecision: 6,
        customPrefix: '',
        customSuffix: '',
      },
    }
  }

  _hexToRgba(hex, opacity = 1) {
    const text = String(hex || '').trim()
    const matched = /^#([0-9a-fA-F]{6})$/.exec(text)
    const alpha = Number.isFinite(Number(opacity)) ? Math.max(0, Math.min(1, Number(opacity))) : 1
    if (!matched) return `rgba(0, 0, 0, ${alpha})`
    const color = matched[1]
    const r = parseInt(color.slice(0, 2), 16)
    const g = parseInt(color.slice(2, 4), 16)
    const b = parseInt(color.slice(4, 6), 16)
    return `rgba(${r}, ${g}, ${b}, ${alpha})`
  }

  _resolveRenderConfig(options = {}) {
    const base = this.config
    const incoming = options?.templateConfig
    if (!incoming || typeof incoming !== 'object') {
      return base
    }

    const scene = String(options?.scene || '').trim()
    const scenePolicy = incoming.scene_policy || {}
    if (scene === 'camera' && scenePolicy.apply_for_camera === false) {
      return base
    }
    if (scene === 'album' && scenePolicy.apply_for_album === false) {
      return base
    }

    const template = incoming.template || {}
    const style = template.style || {}
    const content = template.content || {}

    const position = ['topLeft', 'topRight', 'bottomLeft', 'bottomRight', 'center'].includes(style.position)
      ? style.position
      : base.position

    const textColor = /^#([0-9a-fA-F]{6})$/.test(String(style.text_color || '').trim())
      ? String(style.text_color).toUpperCase()
      : base.watermarkColor
    const backgroundColor = /^#([0-9a-fA-F]{6})$/.test(String(style.background_color || '').trim())
      ? String(style.background_color).toUpperCase()
      : '#000000'

    const numberOr = (value, fallback) => {
      const num = Number(value)
      return Number.isFinite(num) ? num : fallback
    }

    return {
      watermarkColor: textColor,
      backgroundColor: this._hexToRgba(backgroundColor, numberOr(style.background_opacity, 0.7)),
      fontSize: Math.max(12, Math.min(96, Math.round(numberOr(style.font_size, base.fontSize)))),
      padding: Math.max(0, Math.min(120, Math.round(numberOr(style.padding, base.padding)))),
      margin: Math.max(0, Math.min(120, Math.round(numberOr(style.margin, base.margin)))),
      lineHeight: Math.max(16, Math.min(140, Math.round(numberOr(style.line_height, base.lineHeight)))),
      borderRadius: Math.max(0, Math.min(80, Math.round(numberOr(style.border_radius, base.borderRadius)))),
      maxWidth: Math.max(0.3, Math.min(1, numberOr(style.max_width_ratio, base.maxWidth))),
      areaRatio: Math.max(0.01, Math.min(0.4, numberOr(style.area_ratio, base.areaRatio))),
      position,
      content: {
        showIcon: content.show_icon !== false,
        showLocalUploadNote: content.show_local_upload_note !== false,
        showGPS: content.show_gps !== false,
        showAccuracy: content.show_accuracy !== false,
        showAddress: content.show_address !== false,
        showTimestamp: content.show_timestamp !== false,
        showInspector: content.show_inspector !== false,
        showCheckItem: content.show_check_item !== false,
        showSiteName: content.show_site_name !== false,
        coordinatePrecision: Math.max(2, Math.min(8, Math.round(numberOr(content.coordinate_precision, 6)))),
        customPrefix: String(content.custom_prefix || '').slice(0, 80),
        customSuffix: String(content.custom_suffix || '').slice(0, 80),
      },
    }
  }

  _sleep(ms) {
    const delay = Number(ms || 0)
    if (!Number.isFinite(delay) || delay <= 0) return Promise.resolve()
    return new Promise((resolve) => setTimeout(resolve, delay))
  }

  _calcRenderSize(imageInfo, options = {}) {
    const srcW = Number(imageInfo?.width || 0)
    const srcH = Number(imageInfo?.height || 0)
    if (!Number.isFinite(srcW) || !Number.isFinite(srcH) || srcW <= 0 || srcH <= 0) {
      return { width: srcW, height: srcH, scale: 1 }
    }

    const optW = Number(options.renderWidth || 0)
    const optH = Number(options.renderHeight || 0)
    if (Number.isFinite(optW) && Number.isFinite(optH) && optW > 0 && optH > 0) {
      const scaleW = optW / srcW
      const scaleH = optH / srcH
      const scale = Math.min(scaleW, scaleH)
      return { width: Math.round(optW), height: Math.round(optH), scale }
    }

    const maxEdge = Number(options.maxEdge || 0) || 4096
    const longEdge = Math.max(srcW, srcH)
    if (!Number.isFinite(maxEdge) || maxEdge <= 0 || longEdge <= maxEdge) {
      return { width: srcW, height: srcH, scale: 1 }
    }

    const scale = maxEdge / longEdge
    return {
      width: Math.max(1, Math.round(srcW * scale)),
      height: Math.max(1, Math.round(srcH * scale)),
      scale,
    }
  }

  _buildCanvasImagePathCandidates(rawPath, imageInfo = null) {
    const candidates = []
    const pushUnique = (path) => {
      const text = String(path || '').trim()
      if (!text) return
      if (!candidates.includes(text)) {
        candidates.push(text)
      }
    }

    const appendDerived = (path) => {
      const text = String(path || '').trim()
      if (!text) return

      if (text.startsWith('file://')) {
        pushUnique(text.replace(/^file:\/\//, ''))
      } else if (/^\/(storage|data|sdcard)\//i.test(text)) {
        pushUnique(`file://${text}`)
      }

      if (typeof plus !== 'undefined' && plus && plus.io && typeof plus.io.convertLocalFileSystemURL === 'function') {
        try {
          const converted = plus.io.convertLocalFileSystemURL(text)
          pushUnique(converted)
        } catch (e) {
          // ignore
        }
      }
    }

    const source = String(rawPath || '').trim()
    const normalized = String(imageInfo?.path || '').trim()
    pushUnique(normalized)
    pushUnique(source)
    appendDerived(normalized)
    appendDerived(source)

    return candidates
  }

  _buildFileInfoPathCandidates(filePath) {
    const paths = []
    const pushUnique = (path) => {
      const text = String(path || '').trim()
      if (!text) return
      if (!paths.includes(text)) paths.push(text)
    }

    const raw = String(filePath || '').trim()
    pushUnique(raw)
    if (raw.startsWith('file://')) {
      pushUnique(raw.replace(/^file:\/\//, ''))
    } else if (/^\/(storage|data|sdcard)\//i.test(raw)) {
      pushUnique(`file://${raw}`)
    }
    return paths
  }

  async _getFileInfoSafe(filePath) {
    const candidates = this._buildFileInfoPathCandidates(filePath)
    for (const candidate of candidates) {
      try {
        const info = await new Promise((resolve, reject) => {
          uni.getFileInfo({
            filePath: candidate,
            success: resolve,
            fail: reject,
          })
        })
        return {
          ...info,
          size: Number(info?.size || 0),
          filePath: candidate,
        }
      } catch (e) {
        // try next candidate
      }
    }
    return null
  }

  async _assertExportFileLooksValid(filePath, imageInfo, options = {}) {
    if (options && options.validateExportFile === false) return

    const fileInfo = await this._getFileInfoSafe(filePath)
    if (!fileInfo) return

    const outputSize = Number(fileInfo.size || 0)
    if (!Number.isFinite(outputSize) || outputSize <= 0) {
      throw new Error('Canvas输出疑似纯白图（导出文件大小无效）')
    }

    const width = Number(imageInfo?.width || 0)
    const height = Number(imageInfo?.height || 0)
    const pixelCount = Math.max(1, Math.round(width * height))

    const configuredBpp = Number(options.minBytesPerPixel)
    const defaultBpp = 0.03
    const minBytesPerPixel = Number.isFinite(configuredBpp) && configuredBpp > 0 ? configuredBpp : defaultBpp
    const minOutputBytesConfigured = Number(options.minOutputBytes)
    const minOutputBytes = Number.isFinite(minOutputBytesConfigured) && minOutputBytesConfigured > 0
      ? Math.round(minOutputBytesConfigured)
      : 96 * 1024
    const minByPixels = Math.round(pixelCount * minBytesPerPixel)
    const threshold = Math.max(minOutputBytes, minByPixels)

    if (outputSize < threshold) {
      throw new Error(
        `Canvas输出疑似纯白图（导出文件偏小），size=${outputSize}, threshold=${threshold}, pixels=${pixelCount}`,
      )
    }

    const sourceFileSize = Number(options.sourceFileSize || 0)
    if (Number.isFinite(sourceFileSize) && sourceFileSize > 0) {
      const ratio = outputSize / sourceFileSize
      if (sourceFileSize >= 512 * 1024 && ratio < 0.015) {
        throw new Error(
          `Canvas输出疑似纯白图（导出压缩比异常），out=${outputSize}, source=${sourceFileSize}, ratio=${ratio.toFixed(4)}`,
        )
      }
    }
  }

  async _getCanvasImageData(canvasId, x, y, width, height) {
    if (typeof uni?.canvasGetImageData !== 'function') {
      return null
    }

    return await new Promise((resolve, reject) => {
      uni.canvasGetImageData({
        canvasId,
        x,
        y,
        width,
        height,
        success: resolve,
        fail: reject,
      })
    })
  }

  _calcWhiteRatio(imageData, threshold = 250) {
    const data = imageData?.data
    if (!data || typeof data.length !== 'number' || data.length === 0) return 0

    const t = Number(threshold)
    const th = Number.isFinite(t) ? t : 250

    let white = 0
    const total = Math.floor(data.length / 4)
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i]
      const g = data[i + 1]
      const b = data[i + 2]
      const a = data[i + 3]
      if (a >= 250 && r >= th && g >= th && b >= th) {
        white += 1
      }
    }
    return total > 0 ? white / total : 0
  }

  _calcLumaMeanStd(imageData) {
    const data = imageData?.data
    if (!data || typeof data.length !== 'number' || data.length === 0) {
      return { mean: 0, std: 0 }
    }

    let sum = 0
    let sumSq = 0
    let count = 0
    for (let i = 0; i < data.length; i += 4) {
      const r = Number(data[i] || 0)
      const g = Number(data[i + 1] || 0)
      const b = Number(data[i + 2] || 0)
      const a = Number(data[i + 3] || 0)
      if (a <= 0) continue
      const luma = 0.299 * r + 0.587 * g + 0.114 * b
      sum += luma
      sumSq += luma * luma
      count += 1
    }

    if (count <= 0) return { mean: 0, std: 0 }
    const mean = sum / count
    const variance = Math.max(0, sumSq / count - mean * mean)
    return { mean, std: Math.sqrt(variance) }
  }

  async _assertCanvasRenderOk(canvasId, width, height, options = {}) {
    // 默认开启；如遇兼容问题可传 validateRender=false 关闭
    if (options && options.validateRender === false) return
    if (typeof uni?.canvasGetImageData !== 'function') return

    const w = Math.floor(Number(width || 0))
    const h = Math.floor(Number(height || 0))
    if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) return

    const patch = Math.min(32, w, h)
    if (patch < 8) return

    const xMid = Math.max(0, Math.floor(w / 2 - patch / 2))
    const yMid = Math.max(0, Math.floor(h / 2 - patch / 2))
    const yBottom = Math.max(0, h - patch)
    const xLeft = 0
    const xRight = Math.max(0, w - patch)

    try {
      const mid = await this._getCanvasImageData(canvasId, xMid, yMid, patch, patch)
      const bottomLeft = await this._getCanvasImageData(canvasId, xLeft, yBottom, patch, patch)
      const bottomMid = await this._getCanvasImageData(canvasId, xMid, yBottom, patch, patch)
      const bottomRight = await this._getCanvasImageData(canvasId, xRight, yBottom, patch, patch)

      const midWhite = this._calcWhiteRatio(mid)
      const b1 = this._calcWhiteRatio(bottomLeft)
      const b2 = this._calcWhiteRatio(bottomMid)
      const b3 = this._calcWhiteRatio(bottomRight)

      const bottomAllWhite = b1 >= 0.985 && b2 >= 0.985 && b3 >= 0.985
      const midNotWhite = midWhite <= 0.95

      if (bottomAllWhite && midNotWhite) {
        throw new Error(
          `Canvas渲染疑似不完整（底部区域空白），midWhite=${midWhite.toFixed(3)}, bottomWhite=${[b1, b2, b3]
            .map(v => v.toFixed(3))
            .join('/')}`
        )
      }

      // 纯白图阻断：避免“看起来生成成功但实际是白图”进入检查项列表
      const yTop = 0
      const topLeft = await this._getCanvasImageData(canvasId, xLeft, yTop, patch, patch)
      const topMid = await this._getCanvasImageData(canvasId, xMid, yTop, patch, patch)
      const topRight = await this._getCanvasImageData(canvasId, xRight, yTop, patch, patch)
      const topWhiteRatios = [
        this._calcWhiteRatio(topLeft, 252),
        this._calcWhiteRatio(topMid, 252),
        this._calcWhiteRatio(topRight, 252),
        midWhite,
      ]
      const topStats = [
        this._calcLumaMeanStd(topLeft),
        this._calcLumaMeanStd(topMid),
        this._calcLumaMeanStd(topRight),
        this._calcLumaMeanStd(mid),
      ]
      const allNearWhite = topWhiteRatios.every((v) => v >= 0.997)
      const allLowVariance = topStats.every((s) => s.std <= 2.2 && s.mean >= 248)
      if (allNearWhite && allLowVariance) {
        throw new Error(
          `Canvas输出疑似纯白图，white=${topWhiteRatios.map(v => v.toFixed(3)).join('/')}, std=${topStats.map(s => s.std.toFixed(2)).join('/')}`,
        )
      }
    } catch (e) {
      // 对“底部空白”的命中必须阻断（用于触发降级重试）；其余 canvas API 异常默认不阻断，避免兼容性问题影响业务
      const msg = e && (e.message || String(e))
      if (typeof msg === 'string' && (msg.includes('Canvas渲染疑似不完整') || msg.includes('Canvas输出疑似纯白图'))) {
        throw e
      }
      const strict = options && options.validateRenderStrict === true
      if (strict) throw e
      console.warn('[watermark] canvas渲染校验跳过/失败:', e)
    }
  }

  /**
   * 为照片添加水印
   * @param {string} imagePath - 原始照片路径
   * @param {Object} watermarkData - 水印数据
   * @param {string} canvasId - 可选的canvas ID，如果不提供则创建新的
   * @param {Object} options - 可选配置（如 maxEdge/renderWidth/renderHeight/validateRender）
   * @returns {Promise<string>} - 带水印的照片路径
   */
  async addWatermark(imagePath, watermarkData, canvasId = null, options = {}) {
    try {
      console.log('开始添加水印:', { imagePath, watermarkData })
      
      // 获取图片信息
      const originImageInfo = await this.getImageInfo(imagePath)
      const drawSourceCandidates = this._buildCanvasImagePathCandidates(imagePath, originImageInfo)
      if (drawSourceCandidates.length === 0) {
        throw new Error('图片绘制路径为空')
      }
      if (drawSourceCandidates[0] !== String(imagePath || '').trim()) {
        console.log('水印绘制路径已规范化:', { from: imagePath, to: drawSourceCandidates[0] })
      }
      const render = this._calcRenderSize(originImageInfo, options)
      const imageInfo = {
        ...originImageInfo,
        width: render.width,
        height: render.height,
        originalWidth: originImageInfo.width,
        originalHeight: originImageInfo.height,
        scale: render.scale,
      }
      const renderConfig = this._resolveRenderConfig(options)
      console.log('图片信息:', { ...imageInfo, origin: { width: originImageInfo.width, height: originImageInfo.height } })
      
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

      const sourceFileInfo =
        await this._getFileInfoSafe(drawSourceCandidates[0]) ||
        await this._getFileInfoSafe(imagePath)
      let lastError = null

      for (let i = 0; i < drawSourceCandidates.length; i += 1) {
        const drawSourcePath = drawSourceCandidates[i]
        try {
          if (i > 0) {
            console.log('切换备选绘制路径重试:', drawSourcePath)
          }

          // 绘制原始图片
          await this.drawImage(canvas, drawSourcePath, imageInfo)

          // 绘制水印
          await this.drawWatermark(canvas, watermarkData, imageInfo, renderConfig)

          // 某些 Android 机型大图绘制存在“回调已触发但底部未渲染”的偶发现象，做轻量校验 + 可选延迟
          await this._sleep(options.postDrawDelayMs || 0)
          await this._assertCanvasRenderOk(canvas.canvasId, imageInfo.width, imageInfo.height, options)

          // 保存带水印的图片
          const watermarkedPath = await this.saveCanvasToFile(canvas, imageInfo, options)
          await this._assertExportFileLooksValid(watermarkedPath, imageInfo, {
            ...options,
            sourceFileSize: Number(sourceFileInfo?.size || 0),
          })

          console.log('水印添加完成:', watermarkedPath)
          return watermarkedPath
        } catch (attemptError) {
          lastError = attemptError
          console.warn('当前绘制路径处理失败，尝试下一路径:', {
            drawSourcePath,
            error: attemptError?.message || attemptError,
          })
        }
      }

      throw lastError || new Error('水印添加失败')
      
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
  async drawWatermark(canvas, watermarkData, imageInfo, renderConfig = this.config) {
    const ctx = canvas.context
    const config = renderConfig || this.config
    
    // 准备水印文本
    const watermarkLines = this.prepareWatermarkText(watermarkData, imageInfo, config)

    // 基于图片尺寸计算动态样式（短边约 2.5% 作为字号基准）
    let style = this.getScaledStyle(imageInfo, config)

    // 先根据基础样式估算尺寸，再按“水印区域占比”做动态缩放
    let watermarkSize = this.calculateWatermarkSize(ctx, watermarkLines, style, imageInfo, config)
    style = this.adjustStyleByAreaRatio(style, watermarkSize, imageInfo, config)
    watermarkSize = this.calculateWatermarkSize(ctx, watermarkLines, style, imageInfo, config)
    
    // 计算水印位置
    const position = this.calculateWatermarkPosition(imageInfo, watermarkSize, style, config)
    
    // 绘制水印背景
    this.drawWatermarkBackground(ctx, position, watermarkSize, style, config)
    
    // 绘制水印文本
    this.drawWatermarkText(ctx, watermarkLines, position, style, config)
    
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
  prepareWatermarkText(watermarkData, imageInfo = null, renderConfig = this.config) {
    const contentConfig = renderConfig?.content || {}
    const showIcon = contentConfig.showIcon !== false
    const showLocalUploadNote = contentConfig.showLocalUploadNote !== false
    const showGPS = contentConfig.showGPS !== false
    const showAccuracy = contentConfig.showAccuracy !== false
    const showAddress = contentConfig.showAddress !== false
    const showTimestamp = contentConfig.showTimestamp !== false
    const showInspector = contentConfig.showInspector !== false
    const showCheckItem = contentConfig.showCheckItem !== false
    const showSiteName = contentConfig.showSiteName !== false
    const coordinatePrecision = Math.max(2, Math.min(8, Number(contentConfig.coordinatePrecision || 6)))

    const lines = []
    const buildLine = (icon, text) => {
      const raw = String(text || '').trim()
      if (!raw) return ''
      return showIcon ? `${icon} ${raw}` : raw
    }
    const stripKnownIconPrefix = (text) => {
      const value = String(text || '').trim()
      if (!value) return ''
      const prefixes = ['📍 ', '📊 ', '🏠 ', '🏪 ', '🕐 ', '👤 ', '📋 ', '🏗️ ', '🛣️ ']
      for (const prefix of prefixes) {
        if (value.startsWith(prefix)) {
          return value.slice(prefix.length).trimStart()
        }
      }
      return value
    }

    if (contentConfig.customPrefix) {
      lines.push(String(contentConfig.customPrefix))
    }

    // 本地上传提示（用于“不携带经纬度/地址”的场景）
    if (showLocalUploadNote && watermarkData && watermarkData.localUploadNote) {
      const note = String(watermarkData.localUploadNote || '').trim()
      if (note) {
        lines.push(note)
      }
    }
    
    // GPS坐标和地址信息（尽量使用“图标 + 数据”，减少语言依赖）
    if (showGPS && watermarkData.gps) {
      const gps = watermarkData.gps || {}
      const latitude = Number(gps.latitude)
      const longitude = Number(gps.longitude)
      const hasCoords = isFinite(latitude) && isFinite(longitude) && !(latitude === 0 && longitude === 0)

      if (hasCoords) {
        const plannedLatitude = Number(gps.plannedLatitude)
        const plannedLongitude = Number(gps.plannedLongitude)
        const hasPlannedCoords = (
          isFinite(plannedLatitude) &&
          isFinite(plannedLongitude) &&
          !(plannedLatitude === 0 && plannedLongitude === 0)
        )
        const distanceToPlan = Number(gps.distanceToPlanM)
        const hasDistanceToPlan = isFinite(distanceToPlan) && distanceToPlan >= 0
        const planCoordinateMissing = gps.planCoordinateMissing === true
        const distanceExceeded = gps.distanceExceeded === true

        if (hasPlannedCoords && !distanceExceeded) {
          const actual = `${latitude.toFixed(coordinatePrecision)},${longitude.toFixed(coordinatePrecision)}`
          const planned = `${plannedLatitude.toFixed(coordinatePrecision)},${plannedLongitude.toFixed(coordinatePrecision)}`
          const distanceText = hasDistanceToPlan
            ? t('messages.photoLocationCompareDistanceText', { distance: distanceToPlan.toFixed(1) })
            : ''
          lines.push(
            buildLine(
              '📍',
              t('messages.photoLocationCompareLine', {
                actual,
                planned,
                distanceText,
              }),
            ),
          )
        } else if (hasPlannedCoords && distanceExceeded) {
          // 超阈值场景仅保留实拍坐标，避免修改原有业务结果表达
          lines.push(buildLine('📍', `${latitude.toFixed(coordinatePrecision)}, ${longitude.toFixed(coordinatePrecision)}`))
        } else if (planCoordinateMissing) {
          const actual = `${latitude.toFixed(coordinatePrecision)},${longitude.toFixed(coordinatePrecision)}`
          lines.push(
            buildLine(
              '📍',
              t('messages.photoLocationComparePlanMissingLine', { actual }),
            ),
          )
        } else {
          lines.push(buildLine('📍', `${latitude.toFixed(coordinatePrecision)}, ${longitude.toFixed(coordinatePrecision)}`))
        }

        const accuracy = Number(gps.accuracy || 0)
        if (showAccuracy && isFinite(accuracy) && accuracy > 0) {
          lines.push(buildLine('📊', `${accuracy.toFixed(1)}m`))
        }

        // 地址信息（可选）
        const showAddressDetails = showAddress && watermarkData.options?.showAddressDetails !== false
        if (showAddressDetails) {
          if (Array.isArray(gps.watermarkAddress) && gps.watermarkAddress.length > 0) {
            gps.watermarkAddress
              .map(line => String(line || '').trim())
              .filter(Boolean)
              .forEach((line) => lines.push(showIcon ? line : stripKnownIconPrefix(line)))
          } else {
            const address = String(gps.address || '').trim()
            if (address) lines.push(buildLine('🏠', address))
          }

          // POI 信息（可选）
          if (gps.addressInfo && watermarkData.options?.showPOI) {
            const poi = String(gps.addressInfo.poi_name || '').trim()
            if (poi) lines.push(buildLine('🏪', poi))
          }
        }
      } else {
        // 无有效坐标（例如定位失败）：仅输出可国际化的短提示
        lines.push(buildLine('📍', t('messages.gpsNotObtained')))
      }
    }
    
    // 时间信息（固定格式：YYYY-MM-DD HH:mm:ss）
    if (showTimestamp && watermarkData.timestamp) {
      const raw = watermarkData.timestamp
      let ts = ''
      if (raw instanceof Date) {
        ts = formatWatermarkTimestamp(raw)
      } else {
        const str = String(raw || '').trim()
        if (str) {
          if (/^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$/.test(str)) {
            ts = str
          } else {
            const parsed = new Date(str)
            ts = Number.isFinite(parsed.getTime()) ? formatWatermarkTimestamp(parsed) : str
          }
        }
      }
      if (ts) lines.push(buildLine('🕐', ts))
    }

    // 检查员信息
    if (showInspector && watermarkData.inspector) {
      lines.push(buildLine('👤', watermarkData.inspector))
    }
    
    // 检查项信息
    if (showCheckItem && watermarkData.checkItem) {
      lines.push(buildLine('📋', watermarkData.checkItem))
    }
    
    // 站点信息
    if (showSiteName && watermarkData.siteName) {
      lines.push(buildLine('🏗️', watermarkData.siteName))
    }

    if (contentConfig.customSuffix) {
      lines.push(String(contentConfig.customSuffix))
    }

    if (!lines.length) {
      lines.push(buildLine('🕐', formatWatermarkTimestamp()))
    }
    
    return lines
  }

  adjustStyleByAreaRatio(style, watermarkSize, imageInfo, renderConfig = this.config) {
    const config = renderConfig || this.config
    const areaRatio = Number(config.areaRatio || 0)
    const imageArea = Number(imageInfo?.width || 0) * Number(imageInfo?.height || 0)
    const watermarkArea = Number(watermarkSize?.width || 0) * Number(watermarkSize?.height || 0)
    if (!isFinite(areaRatio) || areaRatio <= 0 || !isFinite(imageArea) || imageArea <= 0 || !isFinite(watermarkArea) || watermarkArea <= 0) {
      return style
    }

    const targetAreaRatio = Math.max(0.01, Math.min(0.4, areaRatio))
    const targetArea = imageArea * targetAreaRatio
    let scale = Math.sqrt(targetArea / watermarkArea)
    if (!isFinite(scale) || scale <= 0) {
      return style
    }
    scale = Math.max(0.35, Math.min(4.0, scale))

    return {
      fontSize: Math.max(12, style.fontSize * scale),
      padding: Math.max(0, style.padding * scale),
      margin: style.margin,
      lineHeight: Math.max(16, style.lineHeight * scale),
      borderRadius: Math.max(0, style.borderRadius * scale),
    }
  }

  /**
   * 根据图片尺寸计算缩放后的样式
   * 使用图片短边约 2.5% 作为目标字号，并对缩放比例做上下限约束
   */
  getScaledStyle(imageInfo, renderConfig = this.config) {
    const base = Math.min(imageInfo.width, imageInfo.height) || 0
    const config = renderConfig || this.config

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
  calculateWatermarkSize(ctx, lines, style, imageInfo, renderConfig = this.config) {
    const config = renderConfig || this.config

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
  calculateWatermarkPosition(imageInfo, watermarkSize, style, renderConfig = this.config) {
    const config = renderConfig || this.config
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
      case 'center':
        x = (imageInfo.width - watermarkSize.width) / 2
        y = (imageInfo.height - watermarkSize.height) / 2
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
  drawWatermarkBackground(ctx, position, size, style, renderConfig = this.config) {
    const config = renderConfig || this.config
    
    // 设置背景样式
    ctx.setFillStyle(config.backgroundColor)
    
    // 绘制圆角矩形背景
    this.drawRoundedRect(ctx, position.x, position.y, size.width, size.height, style.borderRadius)
    ctx.fill()
  }

  /**
   * 绘制水印文本
   */
  drawWatermarkText(ctx, lines, position, style, renderConfig = this.config) {
    const config = renderConfig || this.config
    
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
  async saveCanvasToFile(canvas, imageInfo, options = {}) {
    return new Promise((resolve, reject) => {
      console.log('开始保存Canvas:', {
        canvasId: canvas.canvasId,
        width: imageInfo?.width || canvas.width,
        height: imageInfo?.height || canvas.height
      })

      const quality = typeof options.quality === 'number' ? options.quality : 0.9
      const fileType = options.fileType || 'jpg'
      
      uni.canvasToTempFilePath({
        canvasId: canvas.canvasId,
        destWidth: imageInfo?.width || canvas.width,
        destHeight: imageInfo?.height || canvas.height,
        quality,
        fileType,
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
        if (o.plannedLatitude !== undefined && o.plannedLatitude !== null) {
          data.plannedLatitude = o.plannedLatitude
        }
        if (o.plannedLongitude !== undefined && o.plannedLongitude !== null) {
          data.plannedLongitude = o.plannedLongitude
        }
        if (o.distanceToPlanM !== undefined && o.distanceToPlanM !== null) {
          data.distanceToPlanM = o.distanceToPlanM
        }
        if (o.planCoordinateMissing !== undefined) {
          data.planCoordinateMissing = o.planCoordinateMissing === true
        }
        if (o.distanceThresholdM !== undefined && o.distanceThresholdM !== null) {
          data.distanceThresholdM = o.distanceThresholdM
        }
        if (o.distanceExceeded !== undefined) {
          data.distanceExceeded = o.distanceExceeded === true
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
      let address = ''
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
              // 无地址信息时不额外追加“坐标”文本，坐标行由通用渲染负责
            }
          }
        } else {
          // 如果没有地址信息，仅显示坐标
          address = `${data.latitude.toFixed(6)}, ${data.longitude.toFixed(6)}`
          // 无地址信息时不额外追加“坐标”文本，坐标行由通用渲染负责
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
        addressInfo: locationResult.address,
        provider: locationResult.data.provider || 'native-plugin',
        plannedLatitude: locationResult.data.plannedLatitude,
        plannedLongitude: locationResult.data.plannedLongitude,
        distanceToPlanM: locationResult.data.distanceToPlanM,
        planCoordinateMissing: locationResult.data.planCoordinateMissing === true,
        distanceThresholdM: locationResult.data.distanceThresholdM,
        distanceExceeded: locationResult.data.distanceExceeded === true,
      }
      
      // 合并GPS信息到水印数据
      const enhancedWatermarkData = {
        ...watermarkData,
        gps: gpsInfo,
        timestamp: watermarkData.timestamp || formatWatermarkTimestamp(),
        options: {
          showPOI: options.showPOI || false,
          showAddressDetails: options.showAddressDetails !== false
        }
      }
      
      console.log('增强的水印数据:', enhancedWatermarkData)
      
      // 添加水印
      const result = await this.addWatermark(imagePath, enhancedWatermarkData, options.canvasId, options)
      console.log('增强水印添加完成:', result)
      
      return result
      
    } catch (error) {
      console.error('原生插件GPS水印添加失败:', error)
      
      // 不再提供降级方案，直接抛出错误
      // 确保只使用原生插件定位，不使用任何备用方案
      const failedGpsInfo = {
        failed: true,
        latitude: 0,
        longitude: 0,
        accuracy: 0,
        addressError: error.message,
        provider: 'native-plugin-failed'
      }
      
      // 即使失败也添加失败信息的水印
      return await this.addWatermark(imagePath, {
        ...watermarkData,
        gps: failedGpsInfo,
        timestamp: watermarkData.timestamp || formatWatermarkTimestamp()
      }, options.canvasId, options)
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
          let address = ''
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
                // 无地址信息时不额外追加“坐标”文本，坐标行由通用渲染负责
              }
            }
          } else {
            address = `${data.latitude.toFixed(6)}, ${data.longitude.toFixed(6)}`
            // 无地址信息时不额外追加“坐标”文本，坐标行由通用渲染负责
          }
          
          gpsInfo = {
            latitude: data.latitude,
            longitude: data.longitude,
            accuracy: data.accuracy || 0,
            address: address,
            watermarkAddress: watermarkAddress,
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
          failed: true,
          latitude: 0,
          longitude: 0,
          accuracy: 0,
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
          timestamp: formatWatermarkTimestamp(),
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
