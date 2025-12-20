/**
 * App升级状态管理
 * 管理版本检测、下载进度、安装状态
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { buildApiUrl, API_ENDPOINTS } from '@/config/api.js'
import {
    getCurrentVersion,
    getDeviceId,
    getDeviceInfo,
    getNetworkType,
    downloadApk,
    installApk,
    formatFileSize
} from '@/utils/upgrade.js'

export const useUpgradeStore = defineStore('upgrade', () => {
    // ============ 状态 ============

    // 版本检测结果
    const checkResult = ref(null)

    // 下载状态: idle / downloading / paused / completed / failed
    const downloadStatus = ref('idle')

    // 下载进度 0-100
    const downloadProgress = ref(0)

    // 已下载文件路径
    const downloadedFile = ref(null)

    // 上次检测时间
    const lastCheckTime = ref(uni.getStorageSync('upgrade_last_check') || null)

    // 用户跳过的版本码
    const skippedVersion = ref(uni.getStorageSync('upgrade_skipped_version') || null)

    // 下载日志ID（用于统计）
    const downloadLogId = ref(null)

    // 错误信息
    const errorMessage = ref(null)

    // ============ 计算属性 ============

    // 是否有可用更新
    const hasUpdate = computed(() => {
        if (!checkResult.value) return false
        if (!checkResult.value.has_update) return false
        // 检查是否被跳过
        if (skippedVersion.value === checkResult.value.version_info?.version_code) {
            return checkResult.value.update_type === 'force' // 强制更新不能跳过
        }
        return true
    })

    // 是否为强制更新
    const isForceUpdate = computed(() => {
        return checkResult.value?.update_type === 'force'
    })

    // 是否为静默更新
    const isSilentUpdate = computed(() => {
        return checkResult.value?.update_type === 'silent'
    })

    // 版本信息
    const versionInfo = computed(() => checkResult.value?.version_info || null)

    // 格式化的文件大小
    const formattedFileSize = computed(() => {
        if (!versionInfo.value?.file_size) return ''
        return formatFileSize(versionInfo.value.file_size)
    })

    // 是否正在下载
    const isDownloading = computed(() => downloadStatus.value === 'downloading')

    // 下载是否完成
    const isDownloadComplete = computed(() => downloadStatus.value === 'completed')

    // ============ 方法 ============

    /**
     * 检测新版本
     * @param {boolean} silent 是否静默检测（不显示loading）
     * @returns {Promise<boolean>} 是否有更新
     */
    const checkUpdate = async (silent = true) => {
        try {
            const currentVersion = getCurrentVersion()
            const deviceId = getDeviceId()
            const deviceInfo = getDeviceInfo()

            console.log('检测版本更新:', { currentVersion, deviceId })

            const response = await uni.request({
                url: buildApiUrl(API_ENDPOINTS.APP_VERSION.CHECK),
                method: 'POST',
                data: {
                    current_version_code: currentVersion.versionCode,
                    device_id: deviceId,
                    device_model: deviceInfo.deviceModel,
                    device_brand: deviceInfo.deviceBrand,
                    os_version: deviceInfo.osVersion
                }
            })

            if (response.statusCode === 200) {
                checkResult.value = response.data
                lastCheckTime.value = Date.now()
                uni.setStorageSync('upgrade_last_check', lastCheckTime.value)

                console.log('版本检测结果:', response.data)

                // 如果有更新且是静默更新，自动开始下载
                if (response.data.has_update && response.data.update_type === 'silent') {
                    startDownload()
                }

                return response.data.has_update
            }

            return false
        } catch (error) {
            console.error('版本检测失败:', error)
            return false
        }
    }

    /**
     * 开始下载
     */
    const startDownload = async () => {
        if (!versionInfo.value?.download_url) {
            errorMessage.value = '下载地址无效'
            return false
        }

        try {
            downloadStatus.value = 'downloading'
            downloadProgress.value = 0
            errorMessage.value = null

            // 记录下载开始
            const currentVersion = getCurrentVersion()
            const deviceInfo = getDeviceInfo()
            const networkType = await getNetworkType()

            try {
                const logResponse = await uni.request({
                    url: buildApiUrl(API_ENDPOINTS.APP_VERSION.DOWNLOAD_START),
                    method: 'POST',
                    data: {
                        version_id: versionInfo.value.id,
                        version_code: versionInfo.value.version_code,
                        from_version_code: currentVersion.versionCode,
                        device_id: getDeviceId(),
                        device_model: deviceInfo.deviceModel,
                        device_brand: deviceInfo.deviceBrand,
                        os_version: deviceInfo.osVersion,
                        network_type: networkType
                    }
                })
                if (logResponse.statusCode === 200) {
                    downloadLogId.value = logResponse.data.log_id
                }
            } catch (e) {
                console.warn('记录下载开始失败:', e)
            }

            // 开始下载
            const result = await downloadApk(
                versionInfo.value.download_url,
                (progress) => {
                    downloadProgress.value = progress
                }
            )

            if (result.success) {
                downloadStatus.value = 'completed'
                downloadedFile.value = result.filePath

                // 记录下载完成
                if (downloadLogId.value) {
                    try {
                        await uni.request({
                            url: buildApiUrl(API_ENDPOINTS.APP_VERSION.DOWNLOAD_COMPLETE),
                            method: 'POST',
                            data: {
                                log_id: downloadLogId.value,
                                status: 'completed'
                            }
                        })
                    } catch (e) {
                        console.warn('记录下载完成失败:', e)
                    }
                }

                return true
            } else {
                downloadStatus.value = 'failed'
                errorMessage.value = result.error

                // 记录下载失败
                if (downloadLogId.value) {
                    try {
                        await uni.request({
                            url: buildApiUrl(API_ENDPOINTS.APP_VERSION.DOWNLOAD_COMPLETE),
                            method: 'POST',
                            data: {
                                log_id: downloadLogId.value,
                                status: 'failed',
                                error_message: result.error
                            }
                        })
                    } catch (e) {
                        console.warn('记录下载失败状态失败:', e)
                    }
                }

                return false
            }
        } catch (error) {
            console.error('下载过程出错:', error)
            downloadStatus.value = 'failed'
            errorMessage.value = error.message || '下载失败'
            return false
        }
    }

    /**
     * 安装更新
     */
    const installUpdate = async () => {
        if (!downloadedFile.value) {
            errorMessage.value = '未找到下载文件'
            return false
        }

        const result = await installApk(downloadedFile.value)

        if (!result.success) {
            errorMessage.value = result.error
        }

        return result.success
    }

    /**
     * 跳过当前版本
     */
    const skipCurrentVersion = () => {
        if (versionInfo.value?.version_code) {
            skippedVersion.value = versionInfo.value.version_code
            uni.setStorageSync('upgrade_skipped_version', skippedVersion.value)
        }
        // 清除检测结果
        checkResult.value = null
    }

    /**
     * 重置下载状态
     */
    const resetDownload = () => {
        downloadStatus.value = 'idle'
        downloadProgress.value = 0
        downloadedFile.value = null
        errorMessage.value = null
        downloadLogId.value = null
    }

    /**
     * 重试下载
     */
    const retryDownload = () => {
        resetDownload()
        return startDownload()
    }

    return {
        // 状态
        checkResult,
        downloadStatus,
        downloadProgress,
        downloadedFile,
        lastCheckTime,
        skippedVersion,
        errorMessage,

        // 计算属性
        hasUpdate,
        isForceUpdate,
        isSilentUpdate,
        versionInfo,
        formattedFileSize,
        isDownloading,
        isDownloadComplete,

        // 方法
        checkUpdate,
        startDownload,
        installUpdate,
        skipCurrentVersion,
        resetDownload,
        retryDownload
    }
})
