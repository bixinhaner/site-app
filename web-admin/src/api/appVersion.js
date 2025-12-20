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

    // 上传APK文件
    uploadApk: (file, onProgress) => {
        const formData = new FormData()
        formData.append('file', file)

        return request.post('/api/app-version/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            },
            onUploadProgress: (progressEvent) => {
                if (onProgress && progressEvent.total) {
                    const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
                    onProgress(percent)
                }
            }
        })
    }
}

export default appVersionAPI
