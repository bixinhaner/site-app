import request from '@/utils/request'

/**
 * App版本管理API
 */
export const appVersionAPI = {
    // 获取版本列表
    getVersions: (params = {}) => {
        const queryParams = new URLSearchParams()
        if (params.skip !== undefined) queryParams.append('skip', params.skip)
        if (params.limit !== undefined) queryParams.append('limit', params.limit)
        if (params.is_active !== undefined) queryParams.append('is_active', params.is_active)
        return request.get(`/api/app-version/versions?${queryParams.toString()}`)
    },

    // 获取单个版本详情
    getVersion: (id) => {
        return request.get(`/api/app-version/versions/${id}`)
    },

    // 创建新版本
    createVersion: (data) => {
        return request.post('/api/app-version/versions', data)
    },

    // 更新版本
    updateVersion: (id, data) => {
        return request.put(`/api/app-version/versions/${id}`, data)
    },

    // 删除版本
    deleteVersion: (id) => {
        return request.delete(`/api/app-version/versions/${id}`)
    },

    // 获取最新版本
    getLatestVersion: () => {
        return request.get('/api/app-version/latest')
    },

    // 获取版本统计
    getStats: () => {
        return request.get('/api/app-version/stats')
    },

    // 获取使用统计详情（DAU、版本分布等）
    getUsageStats: (days = 30) => {
        return request.get('/api/app-version/usage-stats', { params: { days } })
    },

    // 上传APK文件
    uploadApk: (file, onProgress) => {
        const formData = new FormData()
        formData.append('file', file)

        return request.post('/api/app-version/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            },
            timeout: 1800000, // 30分钟超时，防止大文件上传中断
            onUploadProgress: (progressEvent) => {
                if (onProgress && progressEvent.total) {
                    const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
                    onProgress(percent)
                }
            }
        })
    },

    // ============ Release Notes API ============

    // 获取版本的Release Note
    getReleaseNote: (versionId) => {
        return request.get(`/api/app-version/release-notes/${versionId}`)
    },

    // 创建Release Note
    createReleaseNote: (data) => {
        return request.post('/api/app-version/release-notes', data)
    },

    // 更新Release Note
    updateReleaseNote: (releaseNoteId, data) => {
        return request.put(`/api/app-version/release-notes/${releaseNoteId}`, data)
    },

    // 删除Release Note
    deleteReleaseNote: (releaseNoteId) => {
        return request.delete(`/api/app-version/release-notes/${releaseNoteId}`)
    },

    // 上传Release Note图片
    uploadReleaseNoteImage: (file, onProgress) => {
        const formData = new FormData()
        formData.append('file', file)

        return request.post('/api/app-version/release-notes/upload-image', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            },
            timeout: 300000, // 5分钟超时
            onUploadProgress: (progressEvent) => {
                if (onProgress && progressEvent.total) {
                    const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
                    onProgress(percent)
                }
            }
        })
    },

    // 获取下载日志
    getDownloadLogs: (params) => {
        return request.get('/api/app-version/download-logs', { params })
    }
}

export default appVersionAPI
