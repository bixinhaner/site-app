/**
 * App升级工具函数
 * 提供版本检测、下载、安装等功能
 */

import { buildApiUrl, API_ENDPOINTS } from '@/config/api.js'

/**
 * 获取当前App版本信息
 * @returns {Object} { versionName, versionCode }
 */
export const getCurrentVersion = () => {
    // #ifdef APP-PLUS
    try {
        return {
            versionName: plus.runtime.version || '1.0.0',
            versionCode: parseInt(plus.runtime.versionCode) || 10000
        }
    } catch (e) {
        console.warn('获取App版本信息失败:', e)
    }
    // #endif

    // H5或其他环境，返回默认版本
    return {
        versionName: '1.0.0',
        versionCode: 10000
    }
}

/**
 * 获取设备唯一标识
 * @returns {string}
 */
export const getDeviceId = () => {
    // #ifdef APP-PLUS
    try {
        // 优先使用 OAID 或 IMEI
        const deviceId = plus.device.uuid
        if (deviceId) return deviceId
    } catch (e) {
        console.warn('获取设备ID失败:', e)
    }
    // #endif

    // 生成或读取持久化的设备ID
    let deviceId = uni.getStorageSync('device_id')
    if (!deviceId) {
        deviceId = 'web_' + Date.now() + '_' + Math.random().toString(36).substring(2, 15)
        uni.setStorageSync('device_id', deviceId)
    }
    return deviceId
}

/**
 * 获取设备信息
 * @returns {Object}
 */
export const getDeviceInfo = () => {
    const systemInfo = uni.getSystemInfoSync()
    return {
        deviceModel: systemInfo.model || 'unknown',
        deviceBrand: systemInfo.brand || 'unknown',
        osVersion: systemInfo.system || 'unknown',
        platform: systemInfo.platform || 'unknown'
    }
}

/**
 * 获取网络类型
 * @returns {Promise<string>}
 */
export const getNetworkType = () => {
    return new Promise((resolve) => {
        uni.getNetworkType({
            success: (res) => {
                resolve(res.networkType || 'unknown')
            },
            fail: () => {
                resolve('unknown')
            }
        })
    })
}

/**
 * 格式化文件大小
 * @param {number} bytes 
 * @returns {string}
 */
export const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * 下载APK文件
 * @param {string} url 下载地址
 * @param {Function} onProgress 进度回调 (progress: 0-100)
 * @returns {Promise<Object>} { success, filePath, error }
 */
export const downloadApk = (url, onProgress) => {
    return new Promise((resolve) => {
        // #ifdef APP-PLUS
        console.log('开始下载APK:', url)

        // 确保URL是完整路径
        const fullUrl = url.startsWith('http') ? url : buildApiUrl(url)

        const downloadTask = plus.downloader.createDownload(
            fullUrl,
            {
                filename: '_doc/update/',  // 保存到私有目录
                retry: 3,
                retryInterval: 10,  // 重试间隔10秒
                timeout: 60         // 连接超时60秒
            },
            (download, status) => {
                console.log('下载完成，状态:', status)
                if (status === 200) {
                    resolve({
                        success: true,
                        filePath: download.filename
                    })
                } else {
                    resolve({
                        success: false,
                        error: `下载失败，状态码: ${status}`
                    })
                }
            }
        )

        // 监听下载进度
        downloadTask.addEventListener('statechanged', (task) => {
            switch (task.state) {
                case 1: // 开始
                    console.log('下载开始')
                    break
                case 2: // 已连接
                    console.log('已连接到服务器')
                    break
                case 3: // 下载中
                    if (task.totalSize > 0) {
                        const progress = Math.round((task.downloadedSize / task.totalSize) * 100)
                        if (onProgress) onProgress(progress)
                    }
                    break
                case 4: // 完成
                    console.log('下载完成')
                    break
                case 5: // 暂停
                    console.log('下载暂停')
                    break
            }
        })

        downloadTask.start()
        // #endif

        // #ifndef APP-PLUS
        // 非App环境，返回不支持
        resolve({
            success: false,
            error: '当前环境不支持下载安装'
        })
        // #endif
    })
}

/**
 * 安装APK
 * @param {string} filePath APK文件路径
 * @returns {Promise<Object>} { success, error }
 */
export const installApk = (filePath) => {
    return new Promise((resolve) => {
        // #ifdef APP-PLUS
        console.log('开始安装APK:', filePath)

        plus.runtime.install(
            filePath,
            { force: true },
            () => {
                console.log('安装成功')
                resolve({ success: true })
            },
            (error) => {
                console.error('安装失败:', error)
                resolve({
                    success: false,
                    error: error.message || '安装失败'
                })
            }
        )
        // #endif

        // #ifndef APP-PLUS
        resolve({
            success: false,
            error: '当前环境不支持安装'
        })
        // #endif
    })
}

/**
 * 检查存储空间是否足够
 * @param {number} requiredSize 需要的空间大小（字节）
 * @returns {Promise<boolean>}
 */
export const checkStorageSpace = async (requiredSize) => {
    // #ifdef APP-PLUS
    try {
        // 预留50MB额外空间
        const safetyMargin = 50 * 1024 * 1024
        const totalRequired = requiredSize + safetyMargin

        // 目前无法直接获取可用空间，默认返回true
        // 实际下载时如果空间不足会失败
        return true
    } catch (e) {
        console.warn('检查存储空间失败:', e)
    }
    // #endif
    return true
}

/**
 * 比较版本号
 * @param {number} v1 版本码1
 * @param {number} v2 版本码2
 * @returns {number} 1: v1 > v2, -1: v1 < v2, 0: v1 == v2
 */
export const compareVersionCode = (v1, v2) => {
    if (v1 > v2) return 1
    if (v1 < v2) return -1
    return 0
}

/**
 * 解析版本号字符串为版本码
 * 例如: "1.2.3" -> 10203
 * @param {string} versionName 
 * @returns {number}
 */
export const parseVersionName = (versionName) => {
    if (!versionName) return 0
    const parts = versionName.split('.').map(p => parseInt(p) || 0)
    while (parts.length < 3) parts.push(0)
    return parts[0] * 10000 + parts[1] * 100 + parts[2]
}

/**
 * 版本码转版本名
 * 例如: 10203 -> "1.2.3"
 * @param {number} versionCode 
 * @returns {string}
 */
export const formatVersionCode = (versionCode) => {
    if (!versionCode) return '0.0.0'
    const major = Math.floor(versionCode / 10000)
    const minor = Math.floor((versionCode % 10000) / 100)
    const patch = versionCode % 100
    return `${major}.${minor}.${patch}`
}
