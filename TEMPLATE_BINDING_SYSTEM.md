# 可定制检查模板绑定系统

## 概述

本系统实现了灵活的检查模板绑定机制，支持同一模板绑定到多个维度（站点、站点类型、任务类型、区域、客户等），并通过智能解析器根据上下文自动选择最匹配的模板。

## 🎯 核心特性

### 1. 多维度绑定支持
- **站点维度**: 特定站点专属绑定
- **站点类型**: 宏站、微站、室内站、室外站
- **任务类型**: 开站检查、维护任务、应急检修等
- **区域维度**: 按地理区域划分
- **客户维度**: 不同运营商客户
- **标签系统**: 灵活的标签匹配
- **时间窗口**: 支持有效期限制

### 2. 智能优先级匹配
- **匹配度算法**: 基于条件匹配的评分系统
- **优先级规则**: 数值越大优先级越高
- **冲突解决**: 自动选择最优匹配
- **兜底机制**: 确保始终有可用模板

### 3. 实时解析能力
- **上下文解析**: 根据检查创建时的上下文信息
- **动态匹配**: 实时计算最佳模板
- **解析测试**: 提供测试界面验证匹配逻辑

## 🏗️ 系统架构

### 数据模型

```python
# 检查模板（去除站点绑定）
class InspectionTemplate(Base):
    id: str
    template_name: str
    template_data: dict  # JSON格式模板数据
    created_by: int
    created_at: datetime
    updated_at: datetime

# 模板绑定
class TemplateBinding(Base):
    id: int
    template_id: str
    
    # 绑定条件（可空，多维组合）
    site_id: Optional[int]
    site_type: Optional[str]
    task_type: Optional[TaskTypeEnum]
    region: Optional[str]
    customer: Optional[str]
    tags: Optional[List[str]]
    
    # 绑定配置
    priority: int  # 1-100，数值越大优先级越高
    active: bool
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    notes: Optional[str]
```

### 解析器核心逻辑

```python
# 匹配度计算规则
def calculate_match_score(binding, context):
    score = 0.0
    
    # 站点ID精确匹配（+2.0）
    if binding.site_id == context.site_id:
        score += 2.0
    
    # 站点类型匹配（+1.0）
    if binding.site_type == context.site_type:
        score += 1.0
    
    # 任务类型匹配（+1.0）
    if binding.task_type == context.task_type:
        score += 1.0
    
    # 区域/客户匹配（+0.5 each）
    if binding.region == context.region:
        score += 0.5
    if binding.customer == context.customer:
        score += 0.5
    
    # 标签匹配（+0.2）
    if has_tag_intersection(binding.tags, context.tags):
        score += 0.2
    
    return score

# 排序规则: 匹配度 → 优先级 → 更新时间
def sort_matches(matches):
    return sorted(matches, 
        key=lambda x: (x.match_score, x.priority, x.updated_at), 
        reverse=True)
```

## 📊 匹配优先级示例

### 场景1: VIP站点专属
```yaml
上下文:
  site_id: 1001
  site_type: "macro"
  task_type: "opening_inspection"

匹配结果:
  - 绑定: 站点1001专属 (匹配度: 2.0, 优先级: 95) ✅ 最佳匹配
  - 绑定: 宏站开站通用 (匹配度: 2.0, 优先级: 80)
```

### 场景2: 标签匹配优先
```yaml
上下文:
  site_type: "macro"
  task_type: "opening_inspection"
  tags: ["5G", "试点"]

匹配结果:
  - 绑定: 5G试点专用 (匹配度: 2.2, 优先级: 85) ✅ 最佳匹配
  - 绑定: 宏站开站通用 (匹配度: 2.0, 优先级: 80)
```

### 场景3: 兜底匹配
```yaml
上下文:
  site_type: "unknown"
  task_type: "custom"

匹配结果:
  - 绑定: 通用兜底模板 (匹配度: 0.1, 优先级: 10) ✅ 兜底匹配
```

## 🛠️ API接口

### 模板管理
```http
# 获取模板列表
GET /api/inspections/templates
?skip=0&limit=100&site_id=&site_type=&task_type=&q=

# 创建模板
POST /api/inspections/templates
{
  "template_name": "新检查模板",
  "template_data": { ... }
}

# 更新模板
PUT /api/inspections/templates/{template_id}
{
  "template_name": "更新后的名称",
  "template_data": { ... }
}
```

### 绑定管理
```http
# 获取模板绑定
GET /api/inspections/templates/{template_id}/bindings
?skip=0&limit=100&active_only=false

# 创建绑定
POST /api/inspections/templates/{template_id}/bindings
{
  "site_id": 1001,
  "site_type": "macro",
  "task_type": "opening_inspection",
  "priority": 80,
  "active": true,
  "notes": "宏站开站专用"
}

# 更新绑定
PUT /api/inspections/templates/{template_id}/bindings/{binding_id}
{
  "priority": 85,
  "active": false
}

# 批量更新优先级
POST /api/inspections/templates/{template_id}/bindings/batch-update
{
  "binding_updates": [
    {"id": 1, "priority": 90},
    {"id": 2, "priority": 80}
  ]
}
```

### 模板解析
```http
# 解析最佳模板
POST /api/inspections/templates/resolve?show_all=false
{
  "site_id": 1001,
  "site_type": "macro", 
  "task_type": "opening_inspection",
  "region": "北京",
  "customer": "中国移动",
  "tags": ["5G", "重要"]
}

# 响应示例
{
  "success": true,
  "result": {
    "template_id": "xxx",
    "binding_id": 123,
    "match_score": 2.2,
    "priority": 85,
    "explain": "精确匹配站点ID 1001; 标签匹配 ['5G'] (匹配度: 2.2, 优先级: 85)",
    "template_name": "5G试点开站模板",
    "template_data": { ... },
    "binding_details": { ... }
  }
}
```

## 🎨 Web管理界面

### 模板管理页面
- **路径**: `/inspections/templates`
- **功能**: 
  - 模板列表查看和搜索
  - 创建/编辑模板
  - 模板结构可视化编辑
  - 绑定统计显示

### 绑定管理界面
- **路径**: `/inspections/templates/{id}` (绑定管理Tab)
- **功能**:
  - 绑定规则列表
  - 拖拽排序调整优先级
  - 创建/编辑/删除绑定
  - 批量启用/禁用

### 解析测试面板
- **功能**:
  - 输入测试上下文
  - 实时查看解析结果
  - 显示所有匹配项和排序
  - 解析逻辑解释

## 📋 绑定策略最佳实践

### 1. 优先级分层设计
```
90-100: VIP/特殊站点专属
80-89:  特殊项目/标签匹配
70-79:  类型+任务组合匹配
60-69:  单一任务类型匹配
50-59:  区域/客户专属
40-49:  标签辅助匹配
10-39:  通用兜底策略
1-9:    备用/测试绑定
```

### 2. 绑定条件组合策略
- **精确绑定**: `site_id` 用于VIP站点
- **类型绑定**: `site_type + task_type` 用于标准场景
- **任务绑定**: `task_type` 用于通用任务
- **区域绑定**: `region` 用于地域特殊要求
- **客户绑定**: `customer` 用于客户定制
- **标签绑定**: `tags` 用于项目/活动特殊需求
- **时间绑定**: `valid_from/to` 用于临时活动

### 3. 典型绑定配置示例
```python
# VIP站点专属（最高优先级）
{
  "site_id": 1001,
  "priority": 95,
  "notes": "总部大楼VIP站点专属模板"
}

# 5G宏站开站标准流程
{
  "site_type": "macro",
  "task_type": "opening_inspection", 
  "tags": ["5G"],
  "priority": 85,
  "notes": "5G宏站开站标准检查流程"
}

# 春节保障应急模板（限时）
{
  "task_type": "power_issue",
  "tags": ["春节保障"],
  "priority": 90,
  "valid_from": "2024-02-01T00:00:00Z",
  "valid_to": "2024-02-29T23:59:59Z",
  "notes": "春节保障期间断电应急处理"
}

# 通用兜底模板
{
  "priority": 10,
  "notes": "系统兜底检查模板"
}
```

## 🧪 测试和验证

### 单元测试运行
```bash
# 运行模板解析器测试
python -m pytest backend/test_template_resolver.py -v

# 运行演示脚本
python backend/demo_template_system.py
```

### 测试覆盖场景
- ✅ 精确站点匹配
- ✅ 多条件组合匹配
- ✅ 优先级排序验证
- ✅ 时间窗口过滤
- ✅ 激活状态过滤
- ✅ 标签匹配逻辑
- ✅ 兜底机制验证
- ✅ 绑定条件验证
- ✅ 匹配度计算准确性

## 🔧 系统集成

### 检查创建流程集成
```python
# 在检查创建时自动应用模板解析
async def create_inspection(inspection_data, db, current_user):
    # 1. 构建解析上下文
    site = db.query(Site).filter(Site.id == inspection_data.site_id).first()
    resolve_context = ResolveContext(
        site_id=inspection_data.site_id,
        site_type=getattr(site, 'site_type', None),
        task_id=inspection_data.task_id,
        task_type=inspection_data.inspection_type,
        region=getattr(site, 'region', None),
        customer=getattr(site, 'customer', None),
        tags=[]
    )
    
    # 2. 解析模板
    resolver = create_resolver(db)
    match_result = resolver.resolve_template(resolve_context)
    
    # 3. 使用匹配的模板或创建默认模板
    if match_result:
        template = match_result.template
    else:
        template = await create_default_template(db, inspection_data.site_id, inspection_data.inspection_type)
    
    # 4. 创建检查记录
    # ... 继续检查创建逻辑
```

## 🚀 部署和使用

### 数据库迁移
```bash
# 运行数据库迁移
cd backend
alembic upgrade head
```

### 启动服务
```bash
# 启动后端API服务
python backend/start_backend.py

# 启动Web管理界面
cd web-admin
npm run dev
```

### 初始化演示数据
```bash
# 运行演示脚本创建示例数据
python backend/demo_template_system.py
```

## 📈 系统监控

### 关键指标
- 模板匹配成功率
- 平均解析响应时间
- 绑定规则命中分布
- 兜底模板使用频率

### 日志记录
- 模板解析决策过程
- 绑定规则匹配详情
- 性能指标统计

## 🔮 扩展计划

### 功能增强
- [ ] 模板版本管理
- [ ] 绑定规则审批流程
- [ ] 批量绑定导入/导出
- [ ] 模板使用情况分析
- [ ] 智能推荐绑定规则

### 性能优化
- [ ] 绑定规则缓存
- [ ] 解析结果缓存
- [ ] 异步解析支持
- [ ] 批量解析API

---

## 📞 技术支持

如有问题或需要技术支持，请联系开发团队或查看相关文档。

**注意**: 本系统已经完全实现并经过测试，可以直接投入生产使用。