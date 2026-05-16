const normalizeLocale = (value) => {
	const s = String(value || '').trim().toLowerCase().replace('_', '-')
	if (!s) return 'zh'
	if (s === 'zh' || s === 'zh-cn' || s === 'zh-hans') return 'zh'
	if (s === 'en' || s === 'en-us' || s === 'en-gb') return 'en'
	if (s === 'id' || s === 'id-id') return 'id'
	return s
}

const hasChinese = (value) => /[\u4e00-\u9fff]/.test(String(value || ''))

const normalizeCandidateText = (value) => {
	const text = typeof value === 'string' ? value.trim() : ''
	if (!text || text === '[object Object]') return ''
	return text
}

const tryParseJsonText = (value) => {
	const text = normalizeCandidateText(value)
	if (!text || (text[0] !== '{' && text[0] !== '[')) return null
	try {
		return JSON.parse(text)
	} catch (e) {
		return null
	}
}

const extractFirstTextFromList = (list, visited) => {
	if (!Array.isArray(list) || !list.length) return ''
	for (const item of list) {
		const text = extractInspectionBackendDetailText(item, visited)
		if (text) return text
	}
	return ''
}

const extractFirstTextFromMap = (value, visited) => {
	if (!value || typeof value !== 'object' || Array.isArray(value)) return ''
	for (const item of Object.values(value)) {
		const text = extractInspectionBackendDetailText(item, visited)
		if (text) return text
	}
	return ''
}

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

export const extractInspectionBackendDetailText = (input, visited = new WeakSet()) => {
	const directText = normalizeCandidateText(input)
	if (directText) {
		const parsed = tryParseJsonText(directText)
		if (parsed && typeof parsed === 'object') {
			const nestedText = extractInspectionBackendDetailText(parsed, visited)
			if (nestedText) return nestedText
		}
		return directText
	}
	if (!input || typeof input !== 'object') return ''
	if (visited.has(input)) return ''
	visited.add(input)

	const nestedCandidates = [
		input.detail,
		input.data,
		input.response?.data,
		input.response,
		input.error
	]
	for (const candidate of nestedCandidates) {
		const text = extractInspectionBackendDetailText(candidate, visited)
		if (text) return text
	}

	const directKeys = ['message', 'reason', 'errMsg']
	for (const key of directKeys) {
		const text = normalizeCandidateText(input[key])
		if (!text) continue
		const parsed = tryParseJsonText(text)
		if (parsed && typeof parsed === 'object') {
			const nestedText = extractInspectionBackendDetailText(parsed, visited)
			if (nestedText) return nestedText
		}
		return text
	}

	const violationsText = extractFirstTextFromList(input.violations, visited)
	if (violationsText) return violationsText

	const errorsListText = extractFirstTextFromList(input.errors, visited)
	if (errorsListText) return errorsListText

	return extractFirstTextFromMap(input.errors, visited)
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

const TEMPLATE_SYNC_MESSAGE_KEY_BY_MODE = {
	applied_now: 'inspection.templateSyncAppliedContent',
	next_submit: 'inspection.templateSyncPendingContent',
	frozen: 'inspection.templateSyncFrozenContent'
}

export const localizeInspectionTemplateSyncMessage = (
	input,
	{
		t = null,
		currentLocale = 'zh'
	} = {}
) => {
	const raw = extractInspectionBackendDetailText(input)
	const mode = String(input?.apply_mode || '').trim()
	const key = input?.just_applied
		? 'inspection.templateSyncAppliedContent'
		: TEMPLATE_SYNC_MESSAGE_KEY_BY_MODE[mode]

	if (key && typeof t === 'function') return t(key)
	return raw
}
