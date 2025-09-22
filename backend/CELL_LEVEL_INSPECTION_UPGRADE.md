# 小区级检查功能升级说明

## 概述

将检查模板从传统的扇区级升级为小区级，支持基于站点规划数据自动生成对应数量的检查项，实现精细化的基站检查管理。

## 核心改进

### 1. 数据模型升级

**检查项模型 (InspectionCheckItem)**
```sql
-- 新增字段
ALTER TABLE inspection_check_items ADD COLUMN band VARCHAR(20);        -- 频段
ALTER TABLE inspection_check_items ADD COLUMN cell_id VARCHAR(20);     -- 小区ID

-- 工单项模型 (WorkOrderItem) 同步升级
ALTER TABLE work_order_items ADD COLUMN band VARCHAR(20);
ALTER TABLE work_order_items ADD COLUMN cell_id VARCHAR(20);
```

### 2. 小区生成服务

**CellGenerator 服务**
- 基于站点规划数据动态生成小区配置
- 支持扇区×频段的小区组合
- 提供向后兼容的传统生成方式

```python
# 示例：3扇区×2频段 = 6个小区
cells = CellGenerator.generate_cells_from_planning(db, site_id)
# 生成结果：1_n41, 1_n78, 2_n41, 2_n3, 3_n78, 3_n3
```

### 3. 检查模板结构

**新增小区级检查类型**
```json
{
  "category_id": "cell_rf",
  "category_name": "小区射频检查",
  "cell_specific": true,    // 新增：小区级标识
  "items": [
    {
      "item_id": "cell_power",
      "item_name": "小区功率测量",
      "required_type": "both"
    }
  ]
}
```

**检查类型层级**
- `站点级` (site_level): 整个站点1个检查项
- `扇区级` (sector_specific): 每个扇区1个检查项  
- `小区级` (cell_specific): 每个小区1个检查项 ⭐ **新增**

## 功能特性

### 1. 智能检查项生成

**基于规划数据自动生成**
- 读取站点规划中的扇区数量和频段配置
- 为每个扇区×频段组合生成对应检查项
- 包含完整的方位角、下倾角等规划参数

### 2. 精细化检查管理

**小区级检查支持**
- 小区功率测量 (每个小区独立)
- 小区覆盖测试 (RSRP、SINR等)
- 小区参数配置 (PCI、频点、带宽)
- 小区级故障诊断

### 3. 向后兼容

**兼容现有模板**
- 扇区级检查 (`sector_specific`) 继续工作
- 站点级检查保持不变
- 渐进式升级，无需一次性修改所有模板

## 测试结果

### 测试场景
**站点配置**: 3扇区，每扇区2个频段（n41/n78, n41/n3, n78/n3）
**生成小区**: 6个小区 (1_n41, 1_n78, 2_n41, 2_n3, 3_n78, 3_n3)

### 检查项统计

| 检查类型 | 传统方式 | 小区级方式 | 改进效果 |
|---------|---------|-----------|---------|
| 站点基础检查 | 2项 | 2项 | 无变化 |
| 扇区物理检查 | 3项 | 3项 | 无变化 |
| 小区射频检查 | 6项 | 12项 | **+100%** |
| 小区配置检查 | 3项 | 6项 | **+100%** |
| **总计** | **14项** | **23项** | **+64.3%** |

## 使用指南

### 1. 创建小区级检查模板

```json
{
  "category_id": "cell_config",
  "category_name": "小区配置检查", 
  "cell_specific": true,
  "items": [
    {
      "item_id": "cell_params",
      "item_name": "小区参数配置",
      "required_type": "data",
      "data_fields": [
        {"field_id": "pci", "field_name": "PCI"},
        {"field_id": "earfcn", "field_name": "频点"}
      ]
    }
  ]
}
```

### 2. 配置站点规划

```json
{
  "site_id": 123,
  "bands": ["n41", "n78", "n3"],
  "sector_count": 3,
  "sectors": [
    {"sector_index": 1, "bands": ["n41", "n78"]},
    {"sector_index": 2, "bands": ["n41", "n3"]},
    {"sector_index": 3, "bands": ["n78", "n3"]}
  ]
}
```

### 3. 工单生成自动化

工单创建时自动：
- 读取站点规划数据
- 生成对应数量的小区检查项
- 包含扇区ID、频段、小区ID等信息

## 核心优势

### 1. 精确检查覆盖
- 每个小区独立检查，避免遗漏
- 支持多频段站点的细粒度管理
- 检查结果可追溯到具体小区

### 2. 数据驱动
- 基于实际站点规划生成检查项
- 规划变更自动反映到检查流程
- 消除硬编码的扇区数量限制

### 3. 业务适配
- 符合5G多频段部署特点
- 支持复杂的小区配置场景
- 满足精细化运维需求

## 迁移建议

### 阶段1：数据库升级
```bash
# 运行数据库迁移
alembic upgrade head
```

### 阶段2：模板升级
- 将重要的扇区级检查升级为小区级
- 新建小区专项检查模板
- 保留站点级基础检查

### 阶段3：逐步部署
- 选择试点站点验证功能
- 收集用户反馈优化流程
- 全面推广小区级检查

## 技术架构

```
站点规划数据 → 小区生成器 → 检查项创建 → 工单执行
     ↓              ↓            ↓          ↓
SitePlanning → CellGenerator → CheckItem → Inspection
```

**核心服务**
- `CellGenerator`: 小区配置生成
- `TemplateResolver`: 模板解析和匹配  
- `InspectionAPI`: 检查记录管理
- `WorkOrderAPI`: 工单流程管理

## 总结

通过引入小区级检查，系统能够更精确地反映5G基站的复杂配置，提供细粒度的检查管理能力。结合站点规划数据的自动化生成，大幅提升了检查效率和质量，为精细化运维提供了强有力的技术支撑。