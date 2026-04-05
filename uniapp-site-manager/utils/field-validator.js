/**
 * App端字段验证工具
 * 与后端验证逻辑保持一致
 */

const FALLBACK_MESSAGES = {
	required: '{field}为必填项',
	minSelection: '{field}至少选择一项',
	validationFailed: '验证失败: {reason}',
	textType: '{field}必须是文本',
	minLength: '{field}长度不能少于{min}个字符',
	maxLength: '{field}长度不能超过{max}个字符',
	patternInvalid: '{field}格式不正确',
	numberType: '{field}必须是数字',
	minValue: '{field}不能小于{min}',
	maxValue: '{field}不能大于{max}',
	booleanType: '{field}必须是是/否',
	invalidOption: '{field}选项无效',
	arrayType: '{field}必须是数组',
	containsInvalidOptions: '{field}包含无效选项: {options}',
	dateType: '{field}日期格式不正确',
	dateFormat: '{field}日期格式不正确（应为YYYY-MM-DD）',
	invalidDate: '{field}是无效的日期',
	timeType: '{field}时间格式不正确',
	timeFormat: '{field}时间格式不正确（应为HH:MM）',
	invalidTime: '{field}是无效的时间',
	datetimeType: '{field}日期时间格式不正确',
	datetimeFormat: '{field}日期时间格式不正确',
	invalidDatetime: '{field}是无效的日期时间',
	requiredFieldMissing: '必填字段{field}未提交'
}

const interpolate = (template, params = {}) =>
	String(template || '').replace(/\{(\w+)\}/g, (_, k) =>
		params[k] === undefined || params[k] === null ? '' : String(params[k])
	)

const buildMessage = (translate, key, params = {}) => {
	if (typeof translate === 'function') {
		const translated = translate(key, params)
		if (translated !== null && translated !== undefined) {
			const text = String(translated).trim()
			if (text && text !== key) return text
		}
	}
	return interpolate(FALLBACK_MESSAGES[key] || '', params)
}

const normalizeFieldLabel = (field) => {
	const label = String(field?.label || field?.field_id || '').trim()
	return label || '字段'
}

/**
 * 验证单个字段值
 * @param {Object} field - 字段定义
 * @param {*} value - 字段值
 * @param {Boolean} strict - 是否严格验证
 * @param {Function} translate - 可选翻译函数，签名 (key, params) => string
 * @returns {Object} { valid: boolean, error: string }
 */
export function validateField(field, value, strict = true, translate = null) {
	try {
		const fieldLabel = normalizeFieldLabel(field)

		// 检查必填
		if (field.required && strict) {
			if (value === undefined || value === null || value === '') {
				return { valid: false, error: buildMessage(translate, 'required', { field: fieldLabel }) }
			}
			if (field.type === 'select_multi' && (!Array.isArray(value) || value.length === 0)) {
				return { valid: false, error: buildMessage(translate, 'minSelection', { field: fieldLabel }) }
			}
		}
		
		// 如果值为空且不是必填，允许通过（注意：0/false 不是空值）
		const isEmpty = (
			value === undefined ||
			value === null ||
			value === '' ||
			(Array.isArray(value) && value.length === 0)
		)
		if (isEmpty && !field.required) {
			return { valid: true, error: null }
		}
		
		// 根据字段类型验证
		switch (field.type) {
			case 'text':
			case 'rich_text':
				return validateText(field, value, translate)
				
			case 'number':
				return validateNumber(field, value, translate)
				
			case 'boolean':
				return validateBoolean(field, value, translate)
				
			case 'select_single':
				return validateSelectSingle(field, value, translate)
				
			case 'select_multi':
				return validateSelectMulti(field, value, translate)
				
			case 'date':
				return validateDate(field, value, translate)
				
			case 'time':
				return validateTime(field, value, translate)
				
			case 'datetime':
				return validateDatetime(field, value, translate)
				
			default:
				return { valid: true, error: null }
		}
	} catch (e) {
		console.error('字段验证出错:', e)
		return { valid: false, error: buildMessage(translate, 'validationFailed', { reason: e?.message || '' }) }
	}
}

/**
 * 验证文本字段
 */
function validateText(field, value, translate) {
	const fieldLabel = normalizeFieldLabel(field)
	if (typeof value !== 'string') {
		return { valid: false, error: buildMessage(translate, 'textType', { field: fieldLabel }) }
	}
	
	// 支持两种约束定义方式：field.constraints.xxx 或 field.xxx
	const constraints = field.constraints || {}
	const minLength = constraints.min_length !== undefined ? constraints.min_length : field.min_length
	const maxLength = constraints.max_length !== undefined ? constraints.max_length : field.max_length
	const pattern = constraints.pattern || field.pattern
	
	// 最小长度
	if (minLength !== undefined && value.length < minLength) {
		return { valid: false, error: buildMessage(translate, 'minLength', { field: fieldLabel, min: minLength }) }
	}
	
	// 最大长度
	if (maxLength !== undefined && value.length > maxLength) {
		return { valid: false, error: buildMessage(translate, 'maxLength', { field: fieldLabel, max: maxLength }) }
	}
	
	// 正则表达式
	if (pattern) {
		try {
			const regex = new RegExp(pattern)
			if (!regex.test(value)) {
				return { valid: false, error: buildMessage(translate, 'patternInvalid', { field: fieldLabel }) }
			}
		} catch (e) {
			console.error('正则表达式错误:', e)
		}
	}
	
	return { valid: true, error: null }
}

/**
 * 验证数字字段
 */
function validateNumber(field, value, translate) {
	const fieldLabel = normalizeFieldLabel(field)
	const numValue = parseFloat(value)
	
	if (isNaN(numValue)) {
		return { valid: false, error: buildMessage(translate, 'numberType', { field: fieldLabel }) }
	}
	
	// 支持两种约束定义方式：field.constraints.xxx 或 field.xxx
	const constraints = field.constraints || {}
	const min = constraints.min !== undefined ? constraints.min : field.min
	const max = constraints.max !== undefined ? constraints.max : field.max
	
	// 最小值
	if (min !== undefined && numValue < min) {
		return { valid: false, error: buildMessage(translate, 'minValue', { field: fieldLabel, min }) }
	}
	
	// 最大值
	if (max !== undefined && numValue > max) {
		return { valid: false, error: buildMessage(translate, 'maxValue', { field: fieldLabel, max }) }
	}
	
	return { valid: true, error: null }
}

/**
 * 验证布尔字段
 */
function validateBoolean(field, value, translate) {
	const fieldLabel = normalizeFieldLabel(field)
	if (typeof value !== 'boolean' && value !== 'true' && value !== 'false' && value !== 0 && value !== 1) {
		return { valid: false, error: buildMessage(translate, 'booleanType', { field: fieldLabel }) }
	}
	
	return { valid: true, error: null }
}

/**
 * 验证单选字段
 */
function validateSelectSingle(field, value, translate) {
	const fieldLabel = normalizeFieldLabel(field)
	if (!field.options || field.options.length === 0) {
		return { valid: true, error: null }
	}
	
	const validValues = field.options.map(opt => opt.value)
	
	if (!validValues.includes(value)) {
		return { valid: false, error: buildMessage(translate, 'invalidOption', { field: fieldLabel }) }
	}
	
	return { valid: true, error: null }
}

/**
 * 验证多选字段
 */
function validateSelectMulti(field, value, translate) {
	const fieldLabel = normalizeFieldLabel(field)
	if (!Array.isArray(value)) {
		return { valid: false, error: buildMessage(translate, 'arrayType', { field: fieldLabel }) }
	}
	
	if (!field.options || field.options.length === 0) {
		return { valid: true, error: null }
	}
	
	const validValues = field.options.map(opt => opt.value)
	const invalidValues = value.filter(v => !validValues.includes(v))
	
	if (invalidValues.length > 0) {
		return {
			valid: false,
			error: buildMessage(translate, 'containsInvalidOptions', {
				field: fieldLabel,
				options: invalidValues.join(', ')
			})
		}
	}
	
	return { valid: true, error: null }
}

/**
 * 验证日期字段
 */
function validateDate(field, value, translate) {
	const fieldLabel = normalizeFieldLabel(field)
	if (typeof value !== 'string') {
		return { valid: false, error: buildMessage(translate, 'dateType', { field: fieldLabel }) }
	}
	
	// 验证格式 YYYY-MM-DD
	const dateRegex = /^\d{4}-\d{2}-\d{2}$/
	if (!dateRegex.test(value)) {
		return { valid: false, error: buildMessage(translate, 'dateFormat', { field: fieldLabel }) }
	}
	
	// 验证日期有效性
	const date = new Date(value)
	if (isNaN(date.getTime())) {
		return { valid: false, error: buildMessage(translate, 'invalidDate', { field: fieldLabel }) }
	}
	
	return { valid: true, error: null }
}

/**
 * 验证时间字段
 */
function validateTime(field, value, translate) {
	const fieldLabel = normalizeFieldLabel(field)
	if (typeof value !== 'string') {
		return { valid: false, error: buildMessage(translate, 'timeType', { field: fieldLabel }) }
	}
	
	// 验证格式 HH:MM 或 HH:MM:SS
	const timeRegex = /^\d{2}:\d{2}(:\d{2})?$/
	if (!timeRegex.test(value)) {
		return { valid: false, error: buildMessage(translate, 'timeFormat', { field: fieldLabel }) }
	}
	
	// 验证时间有效性
	const parts = value.split(':')
	const hours = parseInt(parts[0])
	const minutes = parseInt(parts[1])
	
	if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
		return { valid: false, error: buildMessage(translate, 'invalidTime', { field: fieldLabel }) }
	}
	
	return { valid: true, error: null }
}

/**
 * 验证日期时间字段
 */
function validateDatetime(field, value, translate) {
	const fieldLabel = normalizeFieldLabel(field)
	if (typeof value !== 'string') {
		return { valid: false, error: buildMessage(translate, 'datetimeType', { field: fieldLabel }) }
	}
	
	// 验证格式 YYYY-MM-DD HH:MM 或 YYYY-MM-DDTHH:MM:SS
	const datetimeRegex = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$/
	if (!datetimeRegex.test(value)) {
		return { valid: false, error: buildMessage(translate, 'datetimeFormat', { field: fieldLabel }) }
	}
	
	// 验证日期时间有效性
	const datetime = new Date(value.replace(' ', 'T'))
	if (isNaN(datetime.getTime())) {
		return { valid: false, error: buildMessage(translate, 'invalidDatetime', { field: fieldLabel }) }
	}
	
	return { valid: true, error: null }
}

/**
 * 验证所有字段
 * @param {Array} fields - 字段定义数组
 * @param {Array} dataValues - 数据值数组 [{ field_name, value }]
 * @param {Boolean} strict - 是否严格验证
 * @param {Function} translate - 可选翻译函数，签名 (key, params) => string
 * @returns {Object} { valid: boolean, errors: { field_id: error } }
 */
export function validateAllFields(fields, dataValues, strict = true, translate = null) {
	const errors = {}
	
	// 创建字段映射
	const fieldsMap = {}
	fields.forEach(field => {
		fieldsMap[field.field_id] = field
	})
	
	// 创建值映射
	const valuesMap = {}
	dataValues.forEach(item => {
		valuesMap[item.field_name] = item.value
	})
	
	// 验证每个字段
	fields.forEach(field => {
		const value = valuesMap[field.field_id]
		const result = validateField(field, value, strict, translate)
		
		if (!result.valid) {
			errors[field.field_id] = result.error
		}
	})
	
	// 检查必填字段是否都有提交
	if (strict) {
		const submittedFields = new Set(dataValues.map(item => item.field_name))
		fields.forEach(field => {
			if (field.required && !submittedFields.has(field.field_id)) {
				errors[field.field_id] = buildMessage(translate, 'requiredFieldMissing', {
					field: normalizeFieldLabel(field)
				})
			}
		})
	}
	
	return {
		valid: Object.keys(errors).length === 0,
		errors
	}
}

/**
 * 获取字段的显示提示
 * @param {Object} field - 字段定义
 * @returns {String} 提示文本
 */
export function getFieldHint(field) {
	const hints = []
	
	// 支持两种约束定义方式
	const constraints = field.constraints || {}
	const min = constraints.min !== undefined ? constraints.min : field.min
	const max = constraints.max !== undefined ? constraints.max : field.max
	const minLength = constraints.min_length !== undefined ? constraints.min_length : field.min_length
	const maxLength = constraints.max_length !== undefined ? constraints.max_length : field.max_length
	
	// 数字约束提示
	if (field.type === 'number') {
		if (min !== undefined && max !== undefined) {
			hints.push(`范围: ${min} - ${max}`)
		} else if (min !== undefined) {
			hints.push(`最小: ${min}`)
		} else if (max !== undefined) {
			hints.push(`最大: ${max}`)
		}
	}
	
	// 文本长度提示
	if (field.type === 'text' || field.type === 'rich_text') {
		if (maxLength) {
			hints.push(`最多${maxLength}字符`)
		}
		if (minLength) {
			hints.push(`至少${minLength}字符`)
		}
	}
	
	// 帮助文本
	return hints.join(' | ')
}

/**
 * 获取字段类型的描述
 * @param {String} fieldType - 字段类型
 * @returns {String} 描述文本
 */
export function getFieldTypeDescription(fieldType) {
	const descriptions = {
		'text': '文本输入',
		'number': '数字输入',
		'boolean': '是/否选择',
		'select_single': '单选',
		'select_multi': '多选',
		'date': '日期选择',
		'time': '时间选择',
		'datetime': '日期时间选择',
		'rich_text': '富文本编辑'
	}
	return descriptions[fieldType] || '未知类型'
}

/**
 * 格式化字段值用于显示
 * @param {Object} field - 字段定义
 * @param {*} value - 字段值
 * @returns {String} 格式化后的文本
 */
export function formatFieldValue(field, value) {
	if (value === undefined || value === null || value === '') {
		return '未填写'
	}
	
	switch (field.type) {
		case 'boolean':
			return value === true || value === 'true' ? '是' : '否'
			
		case 'select_single':
			if (field.options) {
				const option = field.options.find(opt => opt.value === value)
				return option ? option.label : value
			}
			return value
			
		case 'select_multi':
			if (Array.isArray(value) && field.options) {
				const labels = value.map(v => {
					const option = field.options.find(opt => opt.value === v)
					return option ? option.label : v
				})
				return labels.join(', ')
			}
			return Array.isArray(value) ? value.join(', ') : value
			
		case 'number':
			const numValue = parseFloat(value)
			if (!isNaN(numValue) && field.unit) {
				return `${numValue}${field.unit}`
			}
			return value
			
		default:
			return String(value)
	}
}

export default {
	validateField,
	validateAllFields,
	getFieldHint,
	getFieldTypeDescription,
	formatFieldValue
}
