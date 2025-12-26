"""
模板绑定相关的 Pydantic 模式
"""

from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, validator, field_serializer

from app.utils.timezone import to_utc_iso



class ResolveContextSchema(BaseModel):
    """解析上下文请求模式"""
    site_id: Optional[int] = None
    site_type: Optional[str] = None
    task_id: Optional[str] = None
    task_type: Optional[str] = None
    region: Optional[str] = None
    customer: Optional[str] = None
    tags: Optional[List[str]] = None


    @validator('site_type')
    def validate_site_type(cls, v):
        if v is not None:
            valid_types = ['macro', 'micro', 'indoor', 'outdoor']
            if v not in valid_types:
                raise ValueError(f"Invalid site_type. Valid values: {valid_types}")
        return v


class TemplateBindingCreate(BaseModel):
    """创建模板绑定请求"""
    template_id: str = Field(..., description="模板ID")
    
    # 条件维度
    site_id: Optional[int] = Field(None, description="站点ID")
    site_type: Optional[str] = Field(None, description="站点类型")
    region: Optional[str] = Field(None, description="区域")
    customer: Optional[str] = Field(None, description="客户")
    tags: Optional[List[str]] = Field(None, description="标签数组")
    
    # 绑定配置
    priority: int = Field(50, ge=1, le=100, description="优先级 (1-100, 数字越大优先级越高)")
    active: bool = Field(True, description="是否活跃")
    valid_from: Optional[datetime] = Field(None, description="生效时间")
    valid_to: Optional[datetime] = Field(None, description="失效时间")
    notes: Optional[str] = Field(None, description="备注")

    @validator('valid_to')
    def validate_time_window(cls, v, values):
        if v and values.get('valid_from') and v <= values['valid_from']:
            raise ValueError("valid_to must be after valid_from")
        return v


class TemplateBindingUpdate(BaseModel):
    """更新模板绑定请求"""
    # 条件维度
    site_id: Optional[int] = None
    site_type: Optional[str] = None
    region: Optional[str] = None
    customer: Optional[str] = None
    tags: Optional[List[str]] = None
    
    # 绑定配置
    priority: Optional[int] = Field(None, ge=1, le=100)
    active: Optional[bool] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    notes: Optional[str] = None

    @validator('valid_to')
    def validate_time_window(cls, v, values):
        if v and values.get('valid_from') and v <= values['valid_from']:
            raise ValueError("valid_to must be after valid_from")
        return v


class TemplateBindingResponse(BaseModel):
    """模板绑定响应"""
    id: int
    template_id: str
    
    # 条件维度
    site_id: Optional[int]
    site_type: Optional[str]
    region: Optional[str]
    customer: Optional[str]
    tags: Optional[List[str]]
    
    # 绑定配置
    priority: int
    active: bool
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    notes: Optional[str]
    
    # 系统字段
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    # 关联信息
    template_name: Optional[str] = None
    site_name: Optional[str] = None
    creator_name: Optional[str] = None

    @field_serializer('valid_from', 'valid_to', 'created_at', 'updated_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class TemplateMatchResultSchema(BaseModel):
    """模板匹配结果"""
    template_id: str
    binding_id: int
    match_score: float
    priority: int
    explain: str
    
    # 模板信息
    template_name: str
    template_data: Any
    
    # 绑定详情
    binding_details: TemplateBindingResponse

    class Config:
        from_attributes = True


class TemplateResolveResponse(BaseModel):
    """模板解析响应"""
    success: bool
    result: Optional[TemplateMatchResultSchema] = None
    message: Optional[str] = None
    all_matches: Optional[List[TemplateMatchResultSchema]] = None


class InspectionTemplateCreate(BaseModel):
    """创建检查模板"""
    template_name: str = Field(..., min_length=1, max_length=100)
    template_data: dict = Field(..., description="模板数据(JSON)")

    @validator('template_data')
    def validate_template_data(cls, v):
        if not isinstance(v, dict):
            raise ValueError("template_data must be a JSON object")
        
        # 基本结构验证
        if 'check_categories' not in v:
            raise ValueError("template_data must contain 'check_categories'")
        
        categories = v['check_categories']
        if not isinstance(categories, list):
            raise ValueError("check_categories must be an array")
        
        # 验证每个分类
        for category in categories:
            if not isinstance(category, dict):
                raise ValueError("Each category must be an object")
            
            required_fields = ['category_id', 'category_name', 'items']
            for field in required_fields:
                if field not in category:
                    raise ValueError(f"Category missing required field: {field}")
            
            # 验证检查项
            items = category['items']
            if not isinstance(items, list):
                raise ValueError("Category items must be an array")
            
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Each item must be an object")
                
                item_required_fields = ['item_id', 'item_name', 'required_type']
                for field in item_required_fields:
                    if field not in item:
                        raise ValueError(f"Item missing required field: {field}")
                
                # 验证 required_type
                if item['required_type'] not in ['photo', 'data', 'both']:
                    raise ValueError("Item required_type must be 'photo', 'data', or 'both'")
        
        return v


class TemplateExportResponse(BaseModel):
    """检查模板导出响应（JSON 内容）"""
    template_name: str
    template_data: Dict[str, Any]
    description: Optional[str] = None
    metadata: Dict[str, Any]


class TemplateImportPayload(BaseModel):
    """检查模板导入请求（JSON 内容）"""
    template_name: str = Field(..., min_length=1, max_length=100, description="新模板名称，必须唯一")
    template: Dict[str, Any] = Field(..., description="完整模板JSON，至少包含 template_data")

    @validator("template")
    def validate_template(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("template must be a JSON object")

        template_data = v.get("template_data")
        if template_data is None:
            raise ValueError("template.template_data is required")

        # 复用 InspectionTemplateCreate 的校验逻辑
        InspectionTemplateCreate.validate_template_data(template_data)  # type: ignore[arg-type]
        return v


class InspectionTemplateUpdate(BaseModel):
    """更新检查模板"""
    template_name: Optional[str] = Field(None, min_length=1, max_length=100)
    template_data: Optional[dict] = None

    @validator('template_data')
    def validate_template_data(cls, v):
        if v is not None:
            # 使用与创建相同的验证逻辑
            return InspectionTemplateCreate.validate_template_data(v)
        return v


class InspectionTemplateResponse(BaseModel):
    """检查模板响应"""
    id: str
    template_name: str
    template_data: dict
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    # 关联信息
    creator_name: Optional[str] = None
    bindings_count: int = 0
    active_bindings_count: int = 0
    work_orders_count: int = 0
    active_work_orders_count: int = 0

    @field_serializer('created_at', 'updated_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class TemplateBindingBatchUpdate(BaseModel):
    """批量更新绑定优先级"""
    binding_updates: List[dict] = Field(..., description="绑定更新列表")
    
    @validator('binding_updates')
    def validate_binding_updates(cls, v):
        for update in v:
            if 'id' not in update or 'priority' not in update:
                raise ValueError("Each update must have 'id' and 'priority' fields")
            
            if not isinstance(update['priority'], int) or update['priority'] < 1 or update['priority'] > 100:
                raise ValueError("Priority must be an integer between 1 and 100")
        
        return v
