const normalizeLocale = (value) => {
	const s = String(value || '').trim().toLowerCase().replace('_', '-')
	if (!s) return 'zh'
	if (s === 'zh' || s === 'zh-cn' || s === 'zh-hans') return 'zh'
	if (s === 'en' || s === 'en-us' || s === 'en-gb') return 'en'
	if (s === 'id' || s === 'id-id') return 'id'
	return s
}

const hasChinese = (value) => /[\u4e00-\u9fff]/.test(String(value || ''))

const DEFAULT_ERROR_MAPPINGS = [
	{
		test: /(设备未出库|无法进行检查|not\s*(in|into)\s*stock|not\s*stocked|not\s*issued|cannot\s*(do|perform)\s*inspection|cannot\s*inspect)/i,
		key: 'inspection.equipmentNotStockedForInspection'
	},
	{
		test: /(设备未领料|未领料|not\s*picked\s*up)/i,
		key: 'inspection.equipmentNotPickedUp'
	}
]

export const extractInspectionBackendDetailText = (input) => {
	if (typeof input === 'string') return input.trim()
	if (!input || typeof input !== 'object') return ''

	const detail = input.detail
	if (typeof detail === 'string') return detail.trim()
	if (detail && typeof detail === 'object') {
		if (typeof detail.message === 'string') return detail.message.trim()
		if (Array.isArray(detail.violations) && detail.violations.length > 0) {
			const first = detail.violations[0]
			if (typeof first === 'string') return first.trim()
			if (first && typeof first === 'object' && typeof first.message === 'string') {
				return first.message.trim()
			}
		}
	}

	if (typeof input.message === 'string') return input.message.trim()
	return ''
}

export const localizeInspectionBackendMessage = (
	input,
	{
		t = null,
		currentLocale = 'zh',
		fallbackKey = 'messages.operationFailed',
		fallbackParams = {},
		mappings = DEFAULT_ERROR_MAPPINGS
	} = {}
) => {
	const raw = extractInspectionBackendDetailText(input)
	const locale = normalizeLocale(currentLocale)
	const fallbackText = typeof t === 'function' ? t(fallbackKey, fallbackParams) : ''

	if (!raw) return fallbackText

	const normalized = raw.toLowerCase()
	const matched = Array.isArray(mappings)
		? mappings.find((item) => item?.test instanceof RegExp && item.test.test(normalized))
		: null

	if (matched && typeof t === 'function') {
		return t(matched.key, fallbackParams)
	}
	if (locale !== 'zh' && hasChinese(raw)) {
		return fallbackText
	}
	return raw
}

