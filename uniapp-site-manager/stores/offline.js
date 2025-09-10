import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'

export const useOfflineStore = defineStore('offline', () => {
	// 状态
	const isOnline = ref(true)
	const offlineQueue = ref([])
	const syncInProgress = ref(false)
	const lastSyncTime = ref(null)
	
	// 数据库相关
	const dbName = 'SiteInspectionDB'
	const dbVersion = 1
	let db = null
	
	// 计算属性
	const pendingDataCount = computed(() => {
		return offlineQueue.value.filter(item => !item.synced).length
	})
	
	const syncStatus = computed(() => {
		if (syncInProgress.value) return 'syncing'
		if (pendingDataCount.value > 0) return 'pending'
		return 'synced'
	})
	
	// 初始化离线存储
	const initOfflineStorage = async () => {
		try {
			// 初始化IndexedDB（如果支持）
			if (typeof window !== 'undefined' && window.indexedDB) {
				await initIndexedDB()
			}
			
			// 监听网络状态
			setupNetworkListener()
			
			// 加载离线数据队列
			await loadOfflineQueue()
			
			console.log('离线存储初始化成功')
		} catch (error) {
			console.error('离线存储初始化失败:', error)
			// 降级到localStorage
			await initLocalStorage()
		}
	}
	
	// 初始化IndexedDB
	const initIndexedDB = async () => {
		return new Promise((resolve, reject) => {
			const request = indexedDB.open(dbName, dbVersion)
			
			request.onerror = () => reject(request.error)
			request.onsuccess = () => {
				db = request.result
				resolve(db)
			}
			
			request.onupgradeneeded = (event) => {
				const database = event.target.result
				
				// 创建检查记录表
				if (!database.objectStoreNames.contains('inspections')) {
					const inspectionStore = database.createObjectStore('inspections', {
						keyPath: 'id',
						autoIncrement: false
					})
					inspectionStore.createIndex('siteId', 'siteId', { unique: false })
					inspectionStore.createIndex('status', 'status', { unique: false })
					inspectionStore.createIndex('createdAt', 'createdAt', { unique: false })
				}
				
				// 创建检查项表
				if (!database.objectStoreNames.contains('checkItems')) {
					const itemStore = database.createObjectStore('checkItems', {
						keyPath: 'id',
						autoIncrement: false
					})
					itemStore.createIndex('inspectionId', 'inspectionId', { unique: false })
					itemStore.createIndex('status', 'status', { unique: false })
				}
				
				// 创建照片表
				if (!database.objectStoreNames.contains('photos')) {
					const photoStore = database.createObjectStore('photos', {
						keyPath: 'id',
						autoIncrement: false
					})
					photoStore.createIndex('inspectionId', 'inspectionId', { unique: false })
					photoStore.createIndex('checkItemId', 'checkItemId', { unique: false })
				}
				
				// 创建同步队列表
				if (!database.objectStoreNames.contains('syncQueue')) {
					const syncStore = database.createObjectStore('syncQueue', {
						keyPath: 'id',
						autoIncrement: true
					})
					syncStore.createIndex('dataType', 'dataType', { unique: false })
					syncStore.createIndex('synced', 'synced', { unique: false })
					syncStore.createIndex('createdAt', 'createdAt', { unique: false })
				}
			}
		})
	}
	
	// 降级到localStorage
	const initLocalStorage = async () => {
		console.log('使用localStorage作为离线存储')
		// localStorage已经可以直接使用，无需初始化
	}
	
	// 设置网络监听
	const setupNetworkListener = () => {
		// uni-app网络状态监听
		uni.onNetworkStatusChange((res) => {
			const wasOnline = isOnline.value
			isOnline.value = res.isConnected
			
			console.log('网络状态变化:', res)
			
			// 网络恢复时自动同步
			if (!wasOnline && isOnline.value && pendingDataCount.value > 0) {
				setTimeout(() => {
					syncAllData()
				}, 2000) // 延迟2秒确保网络稳定
			}
		})
		
		// 获取当前网络状态
		uni.getNetworkType({
			success: (res) => {
				isOnline.value = res.networkType !== 'none'
			}
		})
	}
	
	// 保存离线数据
	const saveOfflineData = async (data) => {
		try {
			const offlineItem = {
				id: generateOfflineId(),
				localId: data.localId || generateOfflineId(),
				dataType: data.type,
				data: data.data,
				createdAt: new Date().toISOString(),
				updatedAt: new Date().toISOString(),
				synced: false,
				syncAttempts: 0,
				lastSyncAttempt: null,
				syncError: null
			}
			
			// 保存到IndexedDB
			if (db) {
				await saveToIndexedDB('syncQueue', offlineItem)
			} else {
				// 降级到localStorage
				await saveToLocalStorage('offlineQueue', offlineItem)
			}
			
			// 更新内存队列
			offlineQueue.value.push(offlineItem)
			
			console.log('离线数据保存成功:', offlineItem)
			return offlineItem.id
			
		} catch (error) {
			console.error('保存离线数据失败:', error)
			throw error
		}
	}
	
	// 保存检查记录到离线存储
	const saveInspectionOffline = async (inspection) => {
		try {
			const offlineInspection = {
				...inspection,
				id: inspection.id || generateOfflineId('inspection'),
				isOffline: true,
				lastModified: new Date().toISOString()
			}
			
			if (db) {
				await saveToIndexedDB('inspections', offlineInspection)
			} else {
				const key = `inspection_${offlineInspection.id}`
				await saveToLocalStorage(key, offlineInspection)
			}
			
			// 添加到同步队列
			await saveOfflineData({
				type: 'inspection',
				localId: offlineInspection.id,
				data: offlineInspection
			})
			
			return offlineInspection
		} catch (error) {
			console.error('保存检查记录失败:', error)
			throw error
		}
	}
	
	// 保存检查项到离线存储
	const saveCheckItemOffline = async (checkItem) => {
		try {
			const offlineCheckItem = {
				...checkItem,
				id: checkItem.id || generateOfflineId('checkitem'),
				isOffline: true,
				lastModified: new Date().toISOString()
			}
			
			if (db) {
				await saveToIndexedDB('checkItems', offlineCheckItem)
			} else {
				const key = `checkitem_${offlineCheckItem.id}`
				await saveToLocalStorage(key, offlineCheckItem)
			}
			
			// 添加到同步队列
			await saveOfflineData({
				type: 'checkItem',
				localId: offlineCheckItem.id,
				data: offlineCheckItem
			})
			
			return offlineCheckItem
		} catch (error) {
			console.error('保存检查项失败:', error)
			throw error
		}
	}
	
	// 保存照片到离线存储
	const savePhotoOffline = async (photo) => {
		try {
			const offlinePhoto = {
				...photo,
				id: photo.id || generateOfflineId('photo'),
				isOffline: true,
				lastModified: new Date().toISOString()
			}
			
			if (db) {
				await saveToIndexedDB('photos', offlinePhoto)
			} else {
				const key = `photo_${offlinePhoto.id}`
				await saveToLocalStorage(key, offlinePhoto)
			}
			
			// 添加到同步队列
			await saveOfflineData({
				type: 'photo',
				localId: offlinePhoto.id,
				data: offlinePhoto
			})
			
			return offlinePhoto
		} catch (error) {
			console.error('保存照片失败:', error)
			throw error
		}
	}
	
	// 获取离线检查记录
	const getOfflineInspections = async () => {
		try {
			if (db) {
				return await getFromIndexedDB('inspections')
			} else {
				return await getFromLocalStorage('inspection_')
			}
		} catch (error) {
			console.error('获取离线检查记录失败:', error)
			return []
		}
	}
	
	// 获取离线检查项
	const getOfflineCheckItems = async (inspectionId) => {
		try {
			if (db) {
				return await getFromIndexedDBByIndex('checkItems', 'inspectionId', inspectionId)
			} else {
				const allItems = await getFromLocalStorage('checkitem_')
				return allItems.filter(item => item.inspectionId === inspectionId)
			}
		} catch (error) {
			console.error('获取离线检查项失败:', error)
			return []
		}
	}
	
	// 获取离线照片
	const getOfflinePhotos = async (inspectionId, checkItemId) => {
		try {
			let photos = []
			
			if (db) {
				if (checkItemId) {
					photos = await getFromIndexedDBByIndex('photos', 'checkItemId', checkItemId)
				} else {
					photos = await getFromIndexedDBByIndex('photos', 'inspectionId', inspectionId)
				}
			} else {
				const allPhotos = await getFromLocalStorage('photo_')
				photos = allPhotos.filter(photo => {
					if (checkItemId) {
						return photo.checkItemId === checkItemId
					}
					return photo.inspectionId === inspectionId
				})
			}
			
			return photos
		} catch (error) {
			console.error('获取离线照片失败:', error)
			return []
		}
	}
	
	// 获取待同步的数据
	const getPendingData = async () => {
		try {
			let pendingItems = []
			
			if (db) {
				pendingItems = await getFromIndexedDBByIndex('syncQueue', 'synced', false)
			} else {
				const offlineData = uni.getStorageSync('offlineQueue') || []
				pendingItems = offlineData.filter(item => !item.synced)
			}
			
			return pendingItems.sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt))
		} catch (error) {
			console.error('获取待同步数据失败:', error)
			return []
		}
	}
	
	// 同步所有数据
	const syncAllData = async () => {
		if (syncInProgress.value || !isOnline.value) {
			console.log('同步已在进行中或网络不可用')
			return { success: false, message: '同步条件不满足' }
		}
		
		try {
			syncInProgress.value = true
			
			const pendingData = await getPendingData()
			console.log('开始同步数据，待同步项:', pendingData.length)
			
			let syncedCount = 0
			let failedCount = 0
			const results = []
			
			for (const item of pendingData) {
				try {
					const result = await syncSingleItem(item)
					if (result.success) {
						syncedCount++
						await markAsSynced(item.id)
					} else {
						failedCount++
						await updateSyncError(item.id, result.error)
					}
					results.push(result)
				} catch (error) {
					failedCount++
					await updateSyncError(item.id, error.message)
					results.push({ success: false, error: error.message })
				}
			}
			
			lastSyncTime.value = new Date().toISOString()
			
			// 更新离线队列
			await loadOfflineQueue()
			
			console.log(`同步完成: 成功${syncedCount}项，失败${failedCount}项`)
			
			return {
				success: true,
				synced: syncedCount,
				failed: failedCount,
				total: pendingData.length,
				results
			}
			
		} catch (error) {
			console.error('数据同步失败:', error)
			return { success: false, error: error.message }
		} finally {
			syncInProgress.value = false
		}
	}
	
	// 同步单个数据项
	const syncSingleItem = async (item) => {
		try {
			const { dataType, data, localId } = item
			
			// 根据数据类型调用不同的同步方法
			switch (dataType) {
				case 'inspection':
					return await syncInspection(data, localId)
				case 'checkItem':
					return await syncCheckItem(data, localId)
				case 'photo':
					return await syncPhoto(data, localId)
				default:
					throw new Error(`未知的数据类型: ${dataType}`)
			}
		} catch (error) {
			console.error('同步单项数据失败:', error)
			return { success: false, error: error.message }
		}
	}
	
	// 同步检查记录
	const syncInspection = async (inspectionData, localId) => {
		try {
			// 调用API创建或更新检查记录
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.INSPECTIONS.CREATE),
				method: 'POST',
				header: {
					'Authorization': `Bearer ${getAuthToken()}`,
					'Content-Type': 'application/json'
				},
				data: {
					...inspectionData,
					localId // 传递本地ID用于关联
				}
			})
			
			if (response.statusCode === 200) {
				const serverData = response.data
				
				// 更新本地数据的服务器ID
				await updateLocalInspectionId(localId, serverData.id)
				
				return { success: true, serverId: serverData.id }
			} else {
				throw new Error(`HTTP ${response.statusCode}: ${response.data.detail || '同步失败'}`)
			}
		} catch (error) {
			throw new Error(`同步检查记录失败: ${error.message}`)
		}
	}
	
	// 同步检查项
	const syncCheckItem = async (checkItemData, localId) => {
		try {
			const response = await uni.request({
				url: buildApiUrl(`/api/inspections/${checkItemData.inspectionId}/items`),
				method: 'POST',
				header: {
					'Authorization': `Bearer ${getAuthToken()}`,
					'Content-Type': 'application/json'
				},
				data: {
					...checkItemData,
					localId
				}
			})
			
			if (response.statusCode === 200) {
				const serverData = response.data
				await updateLocalCheckItemId(localId, serverData.id)
				return { success: true, serverId: serverData.id }
			} else {
				throw new Error(`HTTP ${response.statusCode}: ${response.data.detail || '同步失败'}`)
			}
		} catch (error) {
			throw new Error(`同步检查项失败: ${error.message}`)
		}
	}
	
	// 同步照片
	const syncPhoto = async (photoData, localId) => {
		try {
			// 上传照片文件
			const uploadResponse = await uni.uploadFile({
				url: buildApiUrl(`/api/inspections/${photoData.inspectionId}/photos/`),
				filePath: photoData.filePath,
				name: 'file',
				header: {
					'Authorization': `Bearer ${getAuthToken()}`
				},
				formData: {
					checkItemId: photoData.checkItemId,
					gpsLatitude: photoData.gps?.latitude,
					gpsLongitude: photoData.gps?.longitude,
					gpsAccuracy: photoData.gps?.accuracy,
					localId
				}
			})
			
			if (uploadResponse.statusCode === 200) {
				const serverData = JSON.parse(uploadResponse.data)
				await updateLocalPhotoId(localId, serverData.id)
				return { success: true, serverId: serverData.id }
			} else {
				throw new Error(`HTTP ${uploadResponse.statusCode}: 照片上传失败`)
			}
		} catch (error) {
			throw new Error(`同步照片失败: ${error.message}`)
		}
	}
	
	// 工具函数
	const generateOfflineId = (prefix = 'offline') => {
		const timestamp = Date.now()
		const random = Math.random().toString(36).substr(2, 9)
		return `${prefix}_${timestamp}_${random}`
	}
	
	const getAuthToken = () => {
		// 从用户store或localStorage获取认证token
		return uni.getStorageSync('token') || ''
	}
	
	// IndexedDB操作
	const saveToIndexedDB = async (storeName, data) => {
		return new Promise((resolve, reject) => {
			const transaction = db.transaction([storeName], 'readwrite')
			const store = transaction.objectStore(storeName)
			const request = store.put(data)
			
			request.onsuccess = () => resolve(request.result)
			request.onerror = () => reject(request.error)
		})
	}
	
	const getFromIndexedDB = async (storeName) => {
		return new Promise((resolve, reject) => {
			const transaction = db.transaction([storeName], 'readonly')
			const store = transaction.objectStore(storeName)
			const request = store.getAll()
			
			request.onsuccess = () => resolve(request.result)
			request.onerror = () => reject(request.error)
		})
	}
	
	const getFromIndexedDBByIndex = async (storeName, indexName, value) => {
		return new Promise((resolve, reject) => {
			const transaction = db.transaction([storeName], 'readonly')
			const store = transaction.objectStore(storeName)
			const index = store.index(indexName)
			const request = index.getAll(value)
			
			request.onsuccess = () => resolve(request.result)
			request.onerror = () => reject(request.error)
		})
	}
	
	// localStorage操作
	const saveToLocalStorage = async (key, data) => {
		try {
			uni.setStorageSync(key, data)
		} catch (error) {
			console.error('localStorage保存失败:', error)
			throw error
		}
	}
	
	const getFromLocalStorage = async (prefix) => {
		try {
			const keys = uni.getStorageInfoSync().keys
			const matchedKeys = keys.filter(key => key.startsWith(prefix))
			
			const results = []
			for (const key of matchedKeys) {
				const data = uni.getStorageSync(key)
				if (data) {
					results.push(data)
				}
			}
			
			return results
		} catch (error) {
			console.error('localStorage读取失败:', error)
			return []
		}
	}
	
	// 加载离线队列
	const loadOfflineQueue = async () => {
		try {
			const pendingData = await getPendingData()
			offlineQueue.value = pendingData
		} catch (error) {
			console.error('加载离线队列失败:', error)
		}
	}
	
	// 标记为已同步
	const markAsSynced = async (itemId) => {
		try {
			if (db) {
				const transaction = db.transaction(['syncQueue'], 'readwrite')
				const store = transaction.objectStore('syncQueue')
				const getRequest = store.get(itemId)
				
				getRequest.onsuccess = () => {
					const item = getRequest.result
					if (item) {
						item.synced = true
						item.syncedAt = new Date().toISOString()
						store.put(item)
					}
				}
			} else {
				const offlineData = uni.getStorageSync('offlineQueue') || []
				const itemIndex = offlineData.findIndex(item => item.id === itemId)
				
				if (itemIndex !== -1) {
					offlineData[itemIndex].synced = true
					offlineData[itemIndex].syncedAt = new Date().toISOString()
					uni.setStorageSync('offlineQueue', offlineData)
				}
			}
		} catch (error) {
			console.error('标记同步状态失败:', error)
		}
	}
	
	// 更新同步错误
	const updateSyncError = async (itemId, error) => {
		try {
			if (db) {
				const transaction = db.transaction(['syncQueue'], 'readwrite')
				const store = transaction.objectStore('syncQueue')
				const getRequest = store.get(itemId)
				
				getRequest.onsuccess = () => {
					const item = getRequest.result
					if (item) {
						item.syncAttempts = (item.syncAttempts || 0) + 1
						item.lastSyncAttempt = new Date().toISOString()
						item.syncError = error
						store.put(item)
					}
				}
			} else {
				const offlineData = uni.getStorageSync('offlineQueue') || []
				const itemIndex = offlineData.findIndex(item => item.id === itemId)
				
				if (itemIndex !== -1) {
					offlineData[itemIndex].syncAttempts = (offlineData[itemIndex].syncAttempts || 0) + 1
					offlineData[itemIndex].lastSyncAttempt = new Date().toISOString()
					offlineData[itemIndex].syncError = error
					uni.setStorageSync('offlineQueue', offlineData)
				}
			}
		} catch (error) {
			console.error('更新同步错误失败:', error)
		}
	}
	
	// ID更新函数（用于同步后更新本地数据的服务器ID）
	const updateLocalInspectionId = async (localId, serverId) => {
		// 实现本地检查记录ID更新逻辑
		console.log(`更新检查记录ID: ${localId} -> ${serverId}`)
	}
	
	const updateLocalCheckItemId = async (localId, serverId) => {
		// 实现本地检查项ID更新逻辑
		console.log(`更新检查项ID: ${localId} -> ${serverId}`)
	}
	
	const updateLocalPhotoId = async (localId, serverId) => {
		// 实现本地照片ID更新逻辑
		console.log(`更新照片ID: ${localId} -> ${serverId}`)
	}
	
	// 清理已同步的数据
	const cleanupSyncedData = async (olderThanDays = 7) => {
		try {
			const cutoffDate = new Date()
			cutoffDate.setDate(cutoffDate.getDate() - olderThanDays)
			
			if (db) {
				const transaction = db.transaction(['syncQueue'], 'readwrite')
				const store = transaction.objectStore('syncQueue')
				const index = store.index('synced')
				const request = index.openCursor(true) // true表示已同步的数据
				
				request.onsuccess = (event) => {
					const cursor = event.target.result
					if (cursor) {
						const item = cursor.value
						if (new Date(item.syncedAt) < cutoffDate) {
							cursor.delete()
						}
						cursor.continue()
					}
				}
			} else {
				const offlineData = uni.getStorageSync('offlineQueue') || []
				const cleanedData = offlineData.filter(item => {
					if (item.synced && item.syncedAt) {
						return new Date(item.syncedAt) >= cutoffDate
					}
					return true
				})
				uni.setStorageSync('offlineQueue', cleanedData)
			}
			
			console.log(`清理${olderThanDays}天前的已同步数据`)
		} catch (error) {
			console.error('清理同步数据失败:', error)
		}
	}
	
	// 获取离线存储统计信息
	const getStorageStats = async () => {
		try {
			const pendingData = await getPendingData()
			const offlineInspections = await getOfflineInspections()
			
			let totalSize = 0
			const storageInfo = uni.getStorageInfoSync()
			
			// 估算存储大小
			storageInfo.keys.forEach(key => {
				if (key.includes('offline') || key.includes('inspection') || key.includes('photo')) {
					const data = uni.getStorageSync(key)
					if (data) {
						totalSize += JSON.stringify(data).length
					}
				}
			})
			
			return {
				pendingItems: pendingData.length,
				offlineInspections: offlineInspections.length,
				estimatedSize: totalSize,
				lastSyncTime: lastSyncTime.value,
				storageKeys: storageInfo.keys.length,
				currentSize: storageInfo.currentSize,
				limitSize: storageInfo.limitSize
			}
		} catch (error) {
			console.error('获取存储统计失败:', error)
			return {
				pendingItems: 0,
				offlineInspections: 0,
				estimatedSize: 0,
				lastSyncTime: null,
				storageKeys: 0,
				currentSize: 0,
				limitSize: 0
			}
		}
	}
	
	// 导出的方法和状态
	return {
		// 状态
		isOnline,
		offlineQueue,
		syncInProgress,
		lastSyncTime,
		pendingDataCount,
		syncStatus,
		
		// 方法
		initOfflineStorage,
		saveOfflineData,
		saveInspectionOffline,
		saveCheckItemOffline,
		savePhotoOffline,
		getOfflineInspections,
		getOfflineCheckItems,
		getOfflinePhotos,
		getPendingData,
		syncAllData,
		cleanupSyncedData,
		getStorageStats,
		
		// 工具方法
		generateOfflineId,
		
		// 兼容性方法
		getPendingDataCount: () => pendingDataCount.value
	}
})