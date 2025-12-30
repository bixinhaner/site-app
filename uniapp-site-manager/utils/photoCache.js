import { API_CONFIG, normalizeApiBaseUrlForMatch } from '@/config/api.js'

const CACHE_VERSION = 'v1'
const STORAGE_KEY_PREFIX = `photo_cache_${CACHE_VERSION}`

const inflight = new Map()

const safeGetStorageSync = (key) => {
	try {
		if (typeof uni === 'undefined' || typeof uni.getStorageSync !== 'function') return null
		return uni.getStorageSync(key)
	} catch (e) {
		return null
	}
}

const safeSetStorageSync = (key, value) => {
	try {
		if (typeof uni === 'undefined' || typeof uni.setStorageSync !== 'function') return
		uni.setStorageSync(key, value)
	} catch (e) {
		// ignore
	}
}

const safeRemoveStorageSync = (key) => {
	try {
		if (typeof uni === 'undefined' || typeof uni.removeStorageSync !== 'function') return
		uni.removeStorageSync(key)
	} catch (e) {
		// ignore
	}
}

const normalizeUserKey = (userInfo) => {
	const u = userInfo || safeGetStorageSync('userInfo') || {}
	const id = u?.id ?? u?.user_id
	if (id !== undefined && id !== null && String(id).trim() !== '') return String(id)
	const name = u?.username || u?.full_name || u?.name
	if (name) return String(name)
	return 'anonymous'
}

const normalizeServerKey = () => {
	try {
		return normalizeApiBaseUrlForMatch(API_CONFIG.BASE_URL) || 'unknown_server'
	} catch (e) {
		return 'unknown_server'
	}
}

export const createPhotoCacheContext = (userInfo) => {
	return {
		userKey: normalizeUserKey(userInfo),
		serverKey: normalizeServerKey()
	}
}

export const getPhotoCacheStorageKey = (photoId, ctx) => {
	const id = String(photoId || '').trim()
	if (!id) return ''
	const serverKey = String(ctx?.serverKey || normalizeServerKey())
	const userKey = String(ctx?.userKey || normalizeUserKey(null))
	return `${STORAGE_KEY_PREFIX}:${serverKey}:${userKey}:${id}`
}

const isRemoteUrl = (url) => {
	return typeof url === 'string' && url.startsWith('http')
}

const fileExists = (filePath) => {
	return new Promise((resolve) => {
		const path = String(filePath || '').trim()
		if (!path) return resolve(false)
		if (isRemoteUrl(path)) return resolve(false)

		// 优先使用 getFileSystemManager（小程序）
		try {
			const fsm = typeof uni.getFileSystemManager === 'function' ? uni.getFileSystemManager() : null
			if (fsm && typeof fsm.accessSync === 'function') {
				try {
					fsm.accessSync(path)
					return resolve(true)
				} catch (e) {
					return resolve(false)
				}
			}
		} catch (e) {
			// ignore
		}

		// 其次使用 getFileInfo（App/小程序）
		if (typeof uni.getFileInfo === 'function') {
			uni.getFileInfo({
				filePath: path,
				success: () => resolve(true),
				fail: () => resolve(false)
			})
			return
		}

		// 最后兜底：无法判断时，假设存在
		return resolve(true)
	})
}

const removeSavedFile = async (filePath) => {
	const path = String(filePath || '').trim()
	if (!path) return
	if (isRemoteUrl(path)) return

	// App/小程序：removeSavedFile
	if (typeof uni.removeSavedFile === 'function') {
		await new Promise((resolve) => {
			uni.removeSavedFile({
				filePath: path,
				success: () => resolve(),
				fail: () => resolve()
			})
		})
		return
	}

	// 小程序：FileSystemManager.unlink
	try {
		const fsm = typeof uni.getFileSystemManager === 'function' ? uni.getFileSystemManager() : null
		if (fsm && typeof fsm.unlink === 'function') {
			await new Promise((resolve) => {
				fsm.unlink({
					filePath: path,
					success: () => resolve(),
					fail: () => resolve()
				})
			})
		}
	} catch (e) {
		// ignore
	}
}

export const getCachedPhotoPath = async (photoId, ctx) => {
	const storageKey = getPhotoCacheStorageKey(photoId, ctx)
	if (!storageKey) return ''
	const entry = safeGetStorageSync(storageKey)
	const savedFilePath = entry?.savedFilePath || entry?.path || ''
	if (!savedFilePath) return ''
	const ok = await fileExists(savedFilePath)
	if (!ok) {
		safeRemoveStorageSync(storageKey)
		return ''
	}
	return savedFilePath
}

export const saveLocalPhotoToCache = async ({ photoId, localFilePath, ctx }) => {
	const id = String(photoId || '').trim()
	const localPath = String(localFilePath || '').trim()
	if (!id || !localPath) return { ok: false, reason: 'missing_params' }
	if (typeof uni.saveFile !== 'function') return { ok: false, reason: 'saveFile_unsupported' }

	// 已缓存则跳过
	const cached = await getCachedPhotoPath(id, ctx)
	if (cached) return { ok: true, persisted: true, localPath: cached, fromCache: true }

	const res = await new Promise((resolve) => {
		uni.saveFile({
			tempFilePath: localPath,
			success: (r) => resolve({ ok: true, savedFilePath: r.savedFilePath }),
			fail: (e) => resolve({ ok: false, error: e })
		})
	})

	if (!res.ok || !res.savedFilePath) return { ok: false, reason: 'save_failed', error: res.error }

	const storageKey = getPhotoCacheStorageKey(id, ctx)
	if (storageKey) {
		safeSetStorageSync(storageKey, {
			savedFilePath: res.savedFilePath,
			updatedAt: new Date().toISOString()
		})
	}

	return { ok: true, persisted: true, localPath: res.savedFilePath, fromCache: false }
}

const downloadRemoteToTemp = ({ url, onProgress }) => {
	return new Promise((resolve, reject) => {
		if (!url || typeof uni.downloadFile !== 'function') {
			return reject(new Error('download_unsupported'))
		}

		const task = uni.downloadFile({
			url,
			success: (res) => {
				if (res.statusCode && res.statusCode !== 200) {
					return reject(new Error(`download_http_${res.statusCode}`))
				}
				const tempFilePath = res.tempFilePath || res.filePath
				if (!tempFilePath) return reject(new Error('download_no_temp_file'))
				return resolve({ tempFilePath, task })
			},
			fail: (err) => reject(err)
		})

		if (task && typeof task.onProgressUpdate === 'function' && typeof onProgress === 'function') {
			task.onProgressUpdate((p) => {
				const progress = typeof p?.progress === 'number' ? p.progress : 0
				onProgress(Math.max(0, Math.min(100, progress)))
			})
		}
	})
}

export const ensurePhotoCached = async ({ photoId, remoteUrl, ctx, onProgress }) => {
	const id = String(photoId || '').trim()
	const url = String(remoteUrl || '').trim()
	if (!id || !url) return { ok: false, reason: 'missing_params' }

	// 若已缓存且文件存在，直接返回
	const cached = await getCachedPhotoPath(id, ctx)
	if (cached) return { ok: true, localPath: cached, persisted: true, fromCache: true }

	const storageKey = getPhotoCacheStorageKey(id, ctx)
	if (!storageKey) return { ok: false, reason: 'invalid_storage_key' }

	// 去重：同一个 photo 只允许一个下载任务
	if (inflight.has(storageKey)) {
		const entry = inflight.get(storageKey)
		if (typeof onProgress === 'function') {
			entry.subscribers.add(onProgress)
			if (typeof entry.progress === 'number') onProgress(entry.progress)
		}
		return entry.promise
	}

	const entry = {
		progress: 0,
		subscribers: new Set()
	}
	if (typeof onProgress === 'function') entry.subscribers.add(onProgress)

	const notifyProgress = (p) => {
		entry.progress = p
		entry.subscribers.forEach((cb) => {
			try { cb(p) } catch (e) { /* ignore */ }
		})
	}

	entry.promise = (async () => {
		try {
			notifyProgress(0)

			const { tempFilePath } = await downloadRemoteToTemp({
				url,
				onProgress: (p) => notifyProgress(p)
			})

			// 下载完成
			notifyProgress(100)

			// 尝试持久化保存
			if (typeof uni.saveFile !== 'function') {
				return { ok: true, localPath: tempFilePath, persisted: false, fromCache: false }
			}

			const saveRes = await new Promise((resolve) => {
				uni.saveFile({
					tempFilePath,
					success: (r) => resolve({ ok: true, savedFilePath: r.savedFilePath }),
					fail: (e) => resolve({ ok: false, error: e })
				})
			})

			if (saveRes.ok && saveRes.savedFilePath) {
				safeSetStorageSync(storageKey, {
					savedFilePath: saveRes.savedFilePath,
					updatedAt: new Date().toISOString()
				})
				return { ok: true, localPath: saveRes.savedFilePath, persisted: true, fromCache: false }
			}

			// saveFile 失败：仍返回 tempFilePath 以便展示（但不持久化）
			return { ok: true, localPath: tempFilePath, persisted: false, fromCache: false, saveError: saveRes.error }
		} catch (error) {
			return { ok: false, reason: 'download_failed', error }
		} finally {
			inflight.delete(storageKey)
		}
	})()

	inflight.set(storageKey, entry)
	return entry.promise
}

export const removeCachedPhoto = async ({ photoId, ctx }) => {
	const storageKey = getPhotoCacheStorageKey(photoId, ctx)
	if (!storageKey) return
	const entry = safeGetStorageSync(storageKey)
	const savedFilePath = entry?.savedFilePath || entry?.path || ''
	safeRemoveStorageSync(storageKey)
	if (savedFilePath) {
		try {
			await removeSavedFile(savedFilePath)
		} catch (e) {
			// ignore
		}
	}
}

