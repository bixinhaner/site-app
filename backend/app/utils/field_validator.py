"""
字段值验证工具
支持检查模板中定义的所有字段类型的验证
"""
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date, time
import re

from app.schemas.inspection_enhanced import FieldTypeEnum, FieldDefinition, FieldConstraints


class FieldValidationError(Exception):
    """字段验证异常"""
    pass


class FieldValidator:
    """字段验证器"""
    
    @staticmethod
    def validate_field_value(
        field_def: FieldDefinition,
        value: Any,
        strict: bool = True
    ) -> tuple[bool, Optional[str]]:
        """
        验证字段值是否符合字段定义
        
        Args:
            field_def: 字段定义
            value: 字段值
            strict: 是否严格验证（True时必填字段不能为空）
            
        Returns:
            (is_valid, error_message)
        """
        try:
            # 检查必填
            if field_def.required and strict:
                if value is None or value == '' or (isinstance(value, list) and len(value) == 0):
                    return False, f"字段 {field_def.label} 为必填项"
            
            # 如果值为空且不是必填，允许通过
            if value is None or value == '':
                return True, None
            
            # 根据字段类型验证
            if field_def.type == FieldTypeEnum.TEXT:
                return FieldValidator._validate_text(value, field_def.constraints)
            
            elif field_def.type == FieldTypeEnum.RICH_TEXT:
                return FieldValidator._validate_rich_text(value, field_def.constraints)
            
            elif field_def.type == FieldTypeEnum.NUMBER:
                return FieldValidator._validate_number(value, field_def.constraints)
            
            elif field_def.type == FieldTypeEnum.BOOLEAN:
                return FieldValidator._validate_boolean(value)
            
            elif field_def.type == FieldTypeEnum.SELECT_SINGLE:
                return FieldValidator._validate_select_single(value, field_def.options)
            
            elif field_def.type == FieldTypeEnum.SELECT_MULTI:
                return FieldValidator._validate_select_multi(value, field_def.options)
            
            elif field_def.type == FieldTypeEnum.DATE:
                return FieldValidator._validate_date(value)
            
            elif field_def.type == FieldTypeEnum.TIME:
                return FieldValidator._validate_time(value)
            
            elif field_def.type == FieldTypeEnum.DATETIME:
                return FieldValidator._validate_datetime(value)
            
            else:
                return True, None  # 未知类型，默认通过
                
        except Exception as e:
            return False, f"验证失败: {str(e)}"
    
    @staticmethod
    def _validate_text(value: Any, constraints: Optional[FieldConstraints]) -> tuple[bool, Optional[str]]:
        """验证文本字段"""
        if not isinstance(value, str):
            return False, "值必须是字符串类型"
        
        if constraints:
            # 最小长度
            if constraints.min_length is not None and len(value) < constraints.min_length:
                return False, f"文本长度不能少于 {constraints.min_length} 个字符"
            
            # 最大长度
            if constraints.max_length is not None and len(value) > constraints.max_length:
                return False, f"文本长度不能超过 {constraints.max_length} 个字符"
            
            # 正则表达式
            if constraints.pattern:
                try:
                    if not re.match(constraints.pattern, value):
                        return False, "文本格式不符合要求"
                except re.error:
                    return False, "正则表达式配置错误"
        
        return True, None
    
    @staticmethod
    def _validate_rich_text(value: Any, constraints: Optional[FieldConstraints]) -> tuple[bool, Optional[str]]:
        """验证富文本字段"""
        if not isinstance(value, str):
            return False, "值必须是字符串类型"
        
        if constraints:
            # 最小长度
            if constraints.min_length is not None and len(value) < constraints.min_length:
                return False, f"内容长度不能少于 {constraints.min_length} 个字符"
            
            # 最大长度
            if constraints.max_length is not None and len(value) > constraints.max_length:
                return False, f"内容长度不能超过 {constraints.max_length} 个字符"
        
        return True, None
    
    @staticmethod
    def _validate_number(value: Any, constraints: Optional[FieldConstraints]) -> tuple[bool, Optional[str]]:
        """验证数字字段"""
        try:
            num_value = float(value) if not isinstance(value, (int, float)) else value
        except (ValueError, TypeError):
            return False, "值必须是数字类型"
        
        if constraints:
            # 最小值
            if constraints.min is not None and num_value < constraints.min:
                return False, f"数值不能小于 {constraints.min}"
            
            # 最大值
            if constraints.max is not None and num_value > constraints.max:
                return False, f"数值不能大于 {constraints.max}"
        
        return True, None
    
    @staticmethod
    def _validate_boolean(value: Any) -> tuple[bool, Optional[str]]:
        """验证布尔字段"""
        if not isinstance(value, bool):
            # 尝试转换常见的布尔值表示
            if isinstance(value, str):
                if value.lower() in ['true', 'yes', '1']:
                    return True, None
                elif value.lower() in ['false', 'no', '0']:
                    return True, None
            elif isinstance(value, int):
                if value in [0, 1]:
                    return True, None
            
            return False, "值必须是布尔类型（true/false）"
        
        return True, None
    
    @staticmethod
    def _validate_select_single(value: Any, options: Optional[List]) -> tuple[bool, Optional[str]]:
        """验证单选字段"""
        if not options:
            return True, None  # 没有选项定义，允许任何值
        
        # 提取所有有效的选项值
        valid_values = []
        for opt in options:
            if hasattr(opt, 'value'):  # Pydantic对象
                valid_values.append(opt.value)
            elif isinstance(opt, dict):
                valid_values.append(opt.get('value'))
            else:
                valid_values.append(opt)
        
        # 检查值是否在有效选项中
        if value not in valid_values:
            return False, f"值必须是以下选项之一: {', '.join(map(str, valid_values))}"
        
        return True, None
    
    @staticmethod
    def _validate_select_multi(value: Any, options: Optional[List]) -> tuple[bool, Optional[str]]:
        """验证多选字段"""
        if not isinstance(value, list):
            return False, "值必须是数组类型"
        
        if not options:
            return True, None  # 没有选项定义，允许任何值
        
        # 提取所有有效的选项值
        valid_values = []
        for opt in options:
            if hasattr(opt, 'value'):  # Pydantic对象
                valid_values.append(opt.value)
            elif isinstance(opt, dict):
                valid_values.append(opt.get('value'))
            else:
                valid_values.append(opt)
        
        # 检查每个值是否在有效选项中
        for v in value:
            if v not in valid_values:
                return False, f"值 {v} 不在有效选项中"
        
        return True, None
    
    @staticmethod
    def _validate_date(value: Any) -> tuple[bool, Optional[str]]:
        """验证日期字段"""
        # 如果已经是date对象
        if isinstance(value, date) and not isinstance(value, datetime):
            return True, None
        
        # 尝试解析字符串
        if isinstance(value, str):
            try:
                # 支持 YYYY-MM-DD 格式
                datetime.strptime(value, '%Y-%m-%d')
                return True, None
            except ValueError:
                try:
                    # 支持 ISO 格式
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return True, None
                except ValueError:
                    return False, "日期格式不正确，应为 YYYY-MM-DD"
        
        return False, "日期格式不正确"
    
    @staticmethod
    def _validate_time(value: Any) -> tuple[bool, Optional[str]]:
        """验证时间字段"""
        # 如果已经是time对象
        if isinstance(value, time):
            return True, None
        
        # 尝试解析字符串
        if isinstance(value, str):
            try:
                # 支持 HH:MM:SS 或 HH:MM 格式
                time.fromisoformat(value)
                return True, None
            except ValueError:
                return False, "时间格式不正确，应为 HH:MM:SS 或 HH:MM"
        
        return False, "时间格式不正确"
    
    @staticmethod
    def _validate_datetime(value: Any) -> tuple[bool, Optional[str]]:
        """验证日期时间字段"""
        # 如果已经是datetime对象
        if isinstance(value, datetime):
            return True, None
        
        # 尝试解析字符串
        if isinstance(value, str):
            try:
                # 支持 ISO 格式
                datetime.fromisoformat(value.replace('Z', '+00:00'))
                return True, None
            except ValueError:
                try:
                    # 支持常见格式
                    datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                    return True, None
                except ValueError:
                    return False, "日期时间格式不正确，应为 YYYY-MM-DD HH:MM:SS"
        
        return False, "日期时间格式不正确"
    
    @staticmethod
    def validate_check_item_data(
        fields_definition: List[FieldDefinition],
        data_values: List[Dict[str, Any]],
        strict: bool = True
    ) -> Dict[str, Any]:
        """
        验证检查项的所有字段数据
        
        Args:
            fields_definition: 字段定义列表
            data_values: 数据值列表 [{"field_name": "xxx", "value": xxx}, ...]
            strict: 是否严格验证
            
        Returns:
            验证结果字典 {"valid": bool, "errors": {...}}
        """
        errors = {}
        
        # 将字段定义转换为字典以便查找
        fields_map = {field.field_id: field for field in fields_definition}
        
        # 验证每个提交的数据值
        for data_item in data_values:
            field_name = data_item.get('field_name')
            value = data_item.get('value')
            
            # 查找字段定义
            field_def = fields_map.get(field_name)
            if not field_def:
                if strict:
                    errors[field_name] = "未定义的字段"
                continue
            
            # 验证字段值
            is_valid, error_msg = FieldValidator.validate_field_value(field_def, value, strict)
            if not is_valid:
                errors[field_name] = error_msg
        
        # 检查必填字段是否都有提交
        if strict:
            submitted_fields = {item.get('field_name') for item in data_values}
            for field_def in fields_definition:
                if field_def.required and field_def.field_id not in submitted_fields:
                    errors[field_def.field_id] = f"必填字段 {field_def.label} 未提交"
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    @staticmethod
    def get_field_type_description(field_type: FieldTypeEnum) -> str:
        """获取字段类型的描述"""
        descriptions = {
            FieldTypeEnum.TEXT: "文本输入",
            FieldTypeEnum.NUMBER: "数字输入",
            FieldTypeEnum.BOOLEAN: "是/否选择",
            FieldTypeEnum.SELECT_SINGLE: "单选",
            FieldTypeEnum.SELECT_MULTI: "多选",
            FieldTypeEnum.DATE: "日期选择",
            FieldTypeEnum.TIME: "时间选择",
            FieldTypeEnum.DATETIME: "日期时间选择",
            FieldTypeEnum.RICH_TEXT: "富文本编辑器"
        }
        return descriptions.get(field_type, "未知类型")
