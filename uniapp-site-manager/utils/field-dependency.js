/**
 * 字段依赖关系处理工具
 * 支持字段A的值影响字段B的选项、显示等
 */

/**
 * 字段依赖类型枚举
 */
export const DependencyType = {
	OPTIONS: 'options',     // 影响选项（动态选项）
	VISIBILITY: 'visibility', // 影响显示/隐藏
	REQUIRED: 'required',    // 影响是否必填
	DISABLED: 'disabled',    // 影响是否禁用
	VALUE: 'value'          // 影响默认值
}

/**
 * 字段依赖配置结构
 * {
 *   target_field: '目标字段ID',
 *   source_field: '源字段ID', 
 *   type: 'options|visibility|required|disabled|value',
 *   condition: { operator: '==|!=|>|<|in|not_in', value: xxx },
 *   effect: { options: [...] | visible: true | required: true | disabled: true | value: xxx }
 * }
 */

/**
 * 处理字段依赖关系
 * @param {Array} fields - 字段列表
 * @param {Object} fieldValues - 字段值映射 { field_id: value }
 * @returns {Array} 处理后的字段列表
 */
export function processFieldDependencies(fields, fieldValues) {
	if (!fields || fields.length === 0) return fields
	
	const processedFields = fields.map(field => {
		const newField = { ...field }
		
		// 处理该字段的所有依赖配置
		if (field.dependencies && Array.isArray(field.dependencies)) {
			field.dependencies.forEach(dep => {
				const sourceValue = fieldValues[dep.source_field]
				const conditionMet = evaluateCondition(sourceValue, dep.condition)
				
				if (conditionMet) {
					// 应用依赖效果
					applyDependencyEffect(newField, dep)
				} else {
					// 移除依赖效果（恢复默认）
					removeDependencyEffect(newField, dep)
				}
			})
		}
		
		return newField
	})
	
	return processedFields
}

/**
 * 评估依赖条件是否满足
 * @param {*} value - 源字段的值
 * @param {Object} condition - 条件配置 { operator, value }
 * @returns {Boolean}
 */
function evaluateCondition(value, condition) {
	if (!condition) return true
	
	const { operator, value: condValue } = condition
	
	switch (operator) {
		case '==':
		case 'equals':
			return value == condValue
			
		case '===':
		case 'strict_equals':
			return value === condValue
			
		case '!=':
		case 'not_equals':
			return value != condValue
			
		case '>':
		case 'greater_than':
			return parseFloat(value) > parseFloat(condValue)
			
		case '>=':
		case 'greater_or_equal':
			return parseFloat(value) >= parseFloat(condValue)
			
		case '<':
		case 'less_than':
			return parseFloat(value) < parseFloat(condValue)
			
		case '<=':
		case 'less_or_equal':
			return parseFloat(value) <= parseFloat(condValue)
			
		case 'in':
		case 'includes':
			if (Array.isArray(condValue)) {
				return condValue.includes(value)
			}
			return false
			
		case 'not_in':
		case 'not_includes':
			if (Array.isArray(condValue)) {
				return !condValue.includes(value)
			}
			return true
			
		case 'contains':
			if (Array.isArray(value)) {
				return value.includes(condValue)
			}
			return String(value).includes(String(condValue))
			
		case 'not_contains':
			if (Array.isArray(value)) {
				return !value.includes(condValue)
			}
			return !String(value).includes(String(condValue))
			
		case 'empty':
			return !value || value === '' || (Array.isArray(value) && value.length === 0)
			
		case 'not_empty':
			return !!value && value !== '' && (!Array.isArray(value) || value.length > 0)
			
		case 'true':
			return value === true || value === 'true'
			
		case 'false':
			return value === false || value === 'false'
			
		default:
			console.warn(`未知的条件操作符: ${operator}`)
			return false
	}
}

/**
 * 应用依赖效果
 * @param {Object} field - 目标字段
 * @param {Object} dependency - 依赖配置
 */
function applyDependencyEffect(field, dependency) {
	const { type, effect } = dependency
	
	switch (type) {
		case DependencyType.OPTIONS:
			// 动态修改选项
			if (effect.options) {
				field.options = effect.options
				// 如果当前值不在新选项中，清空值
				if (field.value) {
					const validValues = effect.options.map(opt => opt.value)
					if (field.type === 'select_single' && !validValues.includes(field.value)) {
						field.value = null
					} else if (field.type === 'select_multi' && Array.isArray(field.value)) {
						field.value = field.value.filter(v => validValues.includes(v))
					}
				}
			}
			break
			
		case DependencyType.VISIBILITY:
			// 控制显示/隐藏
			field.hidden = !effect.visible
			// 如果隐藏，清空值（可选）
			if (field.hidden && effect.clear_on_hide) {
				field.value = null
			}
			break
			
		case DependencyType.REQUIRED:
			// 控制是否必填
			field.required = effect.required
			break
			
		case DependencyType.DISABLED:
			// 控制是否禁用
			field.disabled = effect.disabled
			break
			
		case DependencyType.VALUE:
			// 设置默认值（仅当字段没有值时）
			if (!field.value && effect.value !== undefined) {
				field.value = effect.value
			}
			break
			
		default:
			console.warn(`未知的依赖类型: ${type}`)
	}
}

/**
 * 移除依赖效果（恢复默认）
 * @param {Object} field - 目标字段
 * @param {Object} dependency - 依赖配置
 */
function removeDependencyEffect(field, dependency) {
	const { type } = dependency
	
	switch (type) {
		case DependencyType.OPTIONS:
			// 恢复原始选项（如果有保存）
			if (field.original_options) {
				field.options = field.original_options
			}
			break
			
		case DependencyType.VISIBILITY:
			// 显示字段
			field.hidden = false
			break
			
		case DependencyType.REQUIRED:
			// 恢复原始必填状态（如果有保存）
			if (field.original_required !== undefined) {
				field.required = field.original_required
			}
			break
			
		case DependencyType.DISABLED:
			// 恢复为可用
			field.disabled = false
			break
			
		case DependencyType.VALUE:
			// 值类型的依赖不需要移除效果
			break
	}
}

/**
 * 初始化字段依赖（保存原始状态）
 * @param {Array} fields - 字段列表
 * @returns {Array} 初始化后的字段列表
 */
export function initializeFieldDependencies(fields) {
	return fields.map(field => {
		// 保存原始状态，以便依赖不满足时恢复
		if (field.dependencies && Array.isArray(field.dependencies)) {
			field.original_options = field.options ? [...field.options] : null
			field.original_required = field.required
			field.original_disabled = field.disabled
		}
		return field
	})
}

/**
 * 检查字段是否应该显示
 * @param {Object} field - 字段对象
 * @returns {Boolean}
 */
export function shouldShowField(field) {
	return !field.hidden
}

/**
 * 获取字段的当前选项
 * @param {Object} field - 字段对象
 * @returns {Array} 选项列表
 */
export function getFieldOptions(field) {
	return field.options || []
}

/**
 * 检查字段是否必填
 * @param {Object} field - 字段对象
 * @returns {Boolean}
 */
export function isFieldRequired(field) {
	return field.required === true
}

/**
 * 检查字段是否禁用
 * @param {Object} field - 字段对象
 * @returns {Boolean}
 */
export function isFieldDisabled(field) {
	return field.disabled === true
}

/**
 * 示例依赖配置
 */
export const DependencyExamples = {
	// 示例1: 设备类型影响频段选项
	deviceTypeAffectsFrequency: {
		target_field: 'frequency_band',
		source_field: 'device_type',
		type: DependencyType.OPTIONS,
		condition: { operator: '==', value: 'macro' },
		effect: {
			options: [
				{ label: 'n41', value: 'n41' },
				{ label: 'n78', value: 'n78' },
				{ label: 'n3', value: 'n3' }
			]
		}
	},
	
	// 示例2: 是否有备用电源决定备用电源类型是否显示
	backupPowerAffectsType: {
		target_field: 'backup_power_type',
		source_field: 'has_backup_power',
		type: DependencyType.VISIBILITY,
		condition: { operator: 'true' },
		effect: { visible: true }
	},
	
	// 示例3: 站点类型影响天线数量是否必填
	siteTypeAffectsAntennaRequired: {
		target_field: 'antenna_count',
		source_field: 'site_type',
		type: DependencyType.REQUIRED,
		condition: { operator: 'in', value: ['macro', 'micro'] },
		effect: { required: true }
	},
	
	// 示例4: 自动模式时禁用手动配置
	autoModeDisablesManual: {
		target_field: 'manual_config',
		source_field: 'config_mode',
		type: DependencyType.DISABLED,
		condition: { operator: '==', value: 'auto' },
		effect: { disabled: true }
	}
}

export default {
	DependencyType,
	processFieldDependencies,
	initializeFieldDependencies,
	shouldShowField,
	getFieldOptions,
	isFieldRequired,
	isFieldDisabled,
	DependencyExamples
}
