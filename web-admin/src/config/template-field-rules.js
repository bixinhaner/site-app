/**
 * 模板字段规则配置
 * 定义哪些字段是结构性的（不可修改），哪些是非结构性的（可修改）
 */

export const TemplateFieldRules = {
  // 检查分类级别
  category: {
    structural: [
      'category_id',          // 分类ID
      'sector_specific',      // 是否扇区级别
      'cell_specific',        // 是否小区级别
    ],
    nonStructural: [
      'category_name',        // 分类名称
      'description',          // 分类描述
    ]
  },
  
  // 检查项级别
  item: {
    structural: [
      'item_id',              // 检查项ID
      'required_type',        // photo/data/both
    ],
    nonStructural: [
      'item_name',            // 检查项名称
      'description',          // 检查项描述
      'assigned_role',        // 分配角色（可选）
    ]
  },
  
  // 字段级别
  field: {
    structural: [
      'field_id',             // 字段ID
      'type',                 // 字段类型
      'required',             // 必填属性（false→true 为结构性变更）
    ],
    nonStructural: [
      'label',                // 字段标签
      'placeholder',          // 占位符
      'default_value',        // 默认值
      'constraints',          // 约束条件
      'options',              // 选项列表
    ]
  }
};

/**
 * 判断字段是否为结构性字段
 * @param {string} level - 字段层级: 'category', 'item', 'field'
 * @param {string} fieldName - 字段名称
 * @returns {boolean} 是否为结构性字段
 */
export function isStructuralField(level, fieldName) {
  const rules = TemplateFieldRules[level];
  if (!rules) return false;
  return rules.structural.includes(fieldName);
}

/**
 * 获取字段的禁用原因
 * @param {string} level - 字段层级
 * @param {string} fieldName - 字段名称
 * @param {boolean} isTemplateUsed - 模板是否被使用
 * @returns {string|null} 禁用原因，null 表示不禁用
 */
export function getFieldDisabledReason(level, fieldName, isTemplateUsed) {
  if (!isTemplateUsed) {
    return null; // 未使用，不禁用
  }
  
  if (isStructuralField(level, fieldName)) {
    return '该检查模板已有工单使用，此属性不允许修改（会影响数据结构）';
  }
  
  return null; // 非结构性字段，允许修改
}

/**
 * 获取操作的禁用原因
 * @param {string} operation - 操作类型
 * @param {boolean} isTemplateUsed - 模板是否被使用
 * @returns {string|null} 禁用原因，null 表示不禁用
 */
export function getOperationDisabledReason(operation, isTemplateUsed) {
  if (!isTemplateUsed) {
    return null;
  }
  
  const reasons = {
    'add_category': '该检查模板已有工单使用，不允许添加新的检查分类',
    'delete_category': '该检查模板已有工单使用，不允许删除检查分类',
    'add_item': '该检查模板已有工单使用，不允许添加新的检查项',
    'delete_item': '该检查模板已有工单使用，不允许删除检查项',
    'add_field': '该检查模板已有工单使用，不允许添加新的字段',
    'delete_field': '该检查模板已有工单使用，不允许删除字段',
  };
  
  return reasons[operation] || null;
}

/**
 * 特殊规则：required 从 false 改为 true 是结构性变更
 * @param {boolean} oldValue - 旧值
 * @param {boolean} newValue - 新值
 * @param {boolean} isTemplateUsed - 模板是否被使用
 * @returns {Object} { allowed: boolean, reason: string|null }
 */
export function canChangeRequired(oldValue, newValue, isTemplateUsed) {
  if (!isTemplateUsed) {
    return { allowed: true, reason: null };
  }
  
  if (!oldValue && newValue) {
    return { 
      allowed: false, 
      reason: '该检查模板已有工单使用，不允许将字段从非必填改为必填' 
    };
  }
  
  return { allowed: true, reason: null };
}

/**
 * 获取所有结构性操作列表（用于批量禁用）
 * @returns {Array} 结构性操作列表
 */
export function getStructuralOperations() {
  return [
    'add_category',
    'delete_category',
    'add_item',
    'delete_item',
    'add_field',
    'delete_field'
  ];
}

/**
 * 检查字段变更是否为结构性变更
 * @param {Object} oldField - 旧字段配置
 * @param {Object} newField - 新字段配置
 * @returns {boolean} 是否为结构性变更
 */
export function isStructuralChange(oldField, newField) {
  // 字段ID变更
  if (oldField.field_id !== newField.field_id) {
    return true;
  }
  
  // 字段类型变更
  if (oldField.type !== newField.type) {
    return true;
  }
  
  // required 从 false 改为 true
  if (!oldField.required && newField.required) {
    return true;
  }
  
  return false;
}
