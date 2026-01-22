import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const STORAGE_KEY = 'stock_offline_document'
const TTL_MS = 24 * 60 * 60 * 1000

const safeGetStorage = (key) => {
	try {
		return uni.getStorageSync(key)
	} catch (e) {
		return null
	}
}

const safeSetStorage = (key, value) => {
	try {
		uni.setStorageSync(key, value)
	} catch (e) {
		// ignore
	}
}

const safeRemoveStorage = (key) => {
	try {
		uni.removeStorageSync(key)
	} catch (e) {
		// ignore
	}
}

const normalizeDoc = (raw) => {
	if (!raw || typeof raw !== 'object') return null
	const id = String(raw.id || '').trim()
	if (!id) return null
	const remark = String(raw.remark || '').trim()
	const photos = Array.isArray(raw.photos) ? raw.photos.filter(Boolean) : []
	const savedAt = Number(raw.saved_at_ms || 0)
	return {
		id,
		remark,
		photos,
		saved_at_ms: savedAt > 0 ? savedAt : 0,
	}
}

export const useOfflineDocumentStore = defineStore('offlineDocument', () => {
	const current = ref(normalizeDoc(safeGetStorage(STORAGE_KEY)))

	const isExpired = computed(() => {
		if (!current.value) return true
		const savedAt = Number(current.value.saved_at_ms || 0)
		if (!savedAt) return true
		return Date.now() - savedAt >= TTL_MS
	})

	const activeDoc = computed(() => {
		if (!current.value) return null
		if (isExpired.value) return null
		return current.value
	})

	const hydrate = () => {
		const doc = normalizeDoc(safeGetStorage(STORAGE_KEY))
		current.value = doc
		if (doc && !doc.saved_at_ms) {
			// 兼容老数据：无 saved_at_ms 视为过期
			clear()
			return
		}
		if (doc && isExpired.value) clear()
	}

	const setCurrent = ({ id, remark = '', photos = [] }) => {
		const doc = normalizeDoc({
			id,
			remark,
			photos,
			saved_at_ms: Date.now(),
		})
		current.value = doc
		if (doc) safeSetStorage(STORAGE_KEY, doc)
		else safeRemoveStorage(STORAGE_KEY)
	}

	const clear = () => {
		current.value = null
		safeRemoveStorage(STORAGE_KEY)
	}

	return {
		current,
		activeDoc,
		isExpired,
		hydrate,
		setCurrent,
		clear,
	}
})

