/**
 * 时间工具函数
 */

/**
 * 解析后端返回的UTC时间字符串
 * 后端返回格式: "2025-09-18 03:28:35" 或 "2025-09-18T03:28:35"
 * 需要添加Z标记以正确解析为UTC时间
 */
export function parseUTCTime(timeStr) {
	if (!timeStr) return null
	
	let timeString = String(timeStr).trim()
	timeString = timeString.replace(' ', 'T')

	// 如果没有时区标记，添加 Z 表示 UTC 时间（兼容 -05:00 / +0800 等偏移写法）
	const hasTzSuffix = /Z$|[+-]\\d{2}:\\d{2}$|[+-]\\d{4}$/.test(timeString)
	if (!hasTzSuffix) {
		timeString = timeString + 'Z'
	}
	
	return new Date(timeString)
}

/**
 * 格式化时间为相对时间（如：刚刚、5分钟前、3小时前）
 * @param {string} timeStr - 时间字符串
 * @param {Function} t - i18n翻译函数
 */
export function formatTimeAgo(timeStr, t) {
	const time = parseUTCTime(timeStr)
	if (!time || isNaN(time.getTime())) return ''
	
	const now = new Date()
	const diff = now - time
	
	if (diff < 0) return t('common.justNow') // 未来时间，显示为"刚刚"
	if (diff < 60000) return t('common.justNow')
	if (diff < 3600000) return t('common.minutesAgo', { minutes: Math.floor(diff / 60000) })
	if (diff < 86400000) return t('common.hoursAgo', { hours: Math.floor(diff / 3600000) })
	if (diff < 2592000000) return t('common.daysAgo', { days: Math.floor(diff / 86400000) })
	
	// 超过30天，返回格式化日期
	return formatDate(time)
}

/**
 * 格式化日期为 YYYY-MM-DD HH:mm:ss
 */
export function formatDateTime(timeStr) {
	const time = parseUTCTime(timeStr)
	if (!time || isNaN(time.getTime())) return ''
	
	const year = time.getFullYear()
	const month = String(time.getMonth() + 1).padStart(2, '0')
	const day = String(time.getDate()).padStart(2, '0')
	const hours = String(time.getHours()).padStart(2, '0')
	const minutes = String(time.getMinutes()).padStart(2, '0')
	const seconds = String(time.getSeconds()).padStart(2, '0')
	
	return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

/**
 * 格式化日期为 YYYY-MM-DD
 */
export function formatDate(timeStr) {
	const time = typeof timeStr === 'string' ? parseUTCTime(timeStr) : timeStr
	if (!time || isNaN(time.getTime())) return ''
	
	const year = time.getFullYear()
	const month = String(time.getMonth() + 1).padStart(2, '0')
	const day = String(time.getDate()).padStart(2, '0')
	
	return `${year}-${month}-${day}`
}

/**
 * 格式化时间为 HH:mm:ss
 */
export function formatTime(timeStr) {
	const time = parseUTCTime(timeStr)
	if (!time || isNaN(time.getTime())) return ''
	
	const hours = String(time.getHours()).padStart(2, '0')
	const minutes = String(time.getMinutes()).padStart(2, '0')
	const seconds = String(time.getSeconds()).padStart(2, '0')
	
	return `${hours}:${minutes}:${seconds}`
}
