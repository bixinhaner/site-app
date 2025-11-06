# 调查档案管理系统数据库迁移指南

## 概述

本指南用于将数据库从版本 `fecdc1e0054025762b49db19732b93d3d1de3608` 升级到最新版本，主要新增了**调查档案管理系统**功能。

## 版本差异

### 源版本 (fecdc1e)
- ✅ 基础工单管理系统
- ✅ 检查模板系统
- ✅ 设备管理系统
- ✅ 站点规划系统
- ❌ 调查档案管理系统

### 目标版本 (最新)
- ✅ 基础工单管理系统
- ✅ 检查模板系统
- ✅ 设备管理系统
- ✅ 站点规划系统
- ✅ **调查档案管理系统**（新增）

## 数据库变更详情

### 1. 新增枚举值
**文件**: `backend/app/models/work_order.py`

```python
class WorkOrderTypeEnum(str, enum.Enum):
    # 原有值...
    SITE_SURVEY = "site_survey"  # 新增
```

### 2. 新增表结构（5个表）

#### 2.1 site_surveys - 调查主表
存储站点调查的基础信息、位置信息、结构信息、电力传输等数据。

**主要字段**:
- `id` (String[32]) - 主键，调查记录ID
- `site_id` (Integer) - 关联站点ID
- `survey_date` (DateTime) - 调查日期
- `surveyor_name` (String[100]) - 调查员姓名
- `surveyor_phone` (String[30]) - 调查员电话
- `latitude/longitude` (Float) - GPS坐标
- `site_type/tower_type` (String[50]) - 站点和塔型信息
- `power_available/fiber_available` (Boolean) - 电力和光纤可用性
- `feasibility` (String[30]) - 可行性评估（feasible/conditional/infeasible）
- `work_order_id` (String[32]) - 关联工单ID

#### 2.2 site_survey_photos - 调查照片表
存储调查过程中的照片，包含GPS水印和EXIF信息。

**主要字段**:
- `id` (String[32]) - 主键，照片记录ID
- `survey_id` (String[32]) - 关联调查ID
- `file_path` (String[500]) - 文件路径
- `category` (String[50]) - 照片分类（overview/power/room/duct/roof/hazard/custom）
- `latitude/longitude` (Float) - 照片GPS坐标
- `has_watermark` (Boolean) - 是否包含水印
- `hash_value` (String[64]) - 文件哈希值（防篡改）

#### 2.3 site_survey_archives - 调查档案表（当前版本快照）
存储调查档案的当前版本，采用JSON格式存储完整内容。

**主要字段**:
- `id` (String[32]) - 主键，档案ID
- `site_id` (Integer) - 关联站点ID
- `work_order_id` (String[32]) - 关联工单ID
- `inspection_id` (String[32]) - 关联检查ID
- `template_id` (String[32]) - 关联模板ID
- `current_version` (Integer) - 当前版本号
- `content` (JSON) - 完整的档案内容（JSON格式）
- `status` (String[20]) - 状态（active/archived）

#### 2.4 site_survey_archive_versions - 档案版本历史表
采用追加写模式，记录档案的所有历史版本。

**主要字段**:
- `id` (String[32]) - 主键，版本记录ID
- `archive_id` (String[32]) - 关联档案ID
- `version` (Integer) - 版本号
- `content` (JSON) - 该版本的完整快照
- `diff` (JSON) - JSON Patch格式的差异
- `change_summary` (Text) - 变更摘要

#### 2.5 site_survey_archive_kv_index - 档案KV索引表
为档案内容建立KV索引，支持任意字段检索和统计。

**主要字段**:
- `id` (Integer) - 主键，自增ID
- `archive_id` (String[32]) - 关联档案ID
- `version` (Integer) - 关联版本号
- `path` (String[200]) - JSON路径，如"catA.itemX.fieldY"
- `type` (String[20]) - 字段类型（number/bool/string/datetime/json）
- `value_number/value_bool/value_string/value_datetime` - 不同类型的值
- `raw_json` (JSON) - 原始JSON值

## 外键依赖关系

```
sites (id)
  └─ site_surveys (site_id)
      └─ site_survey_photos (survey_id)

work_orders (id)
  └─ site_surveys (work_order_id)
  └─ site_survey_archives (work_order_id)

site_inspections (id)
  └─ site_survey_archives (inspection_id)

inspection_templates (id)
  └─ site_survey_archives (template_id)

users (id)
  ├─ site_surveys (created_by)
  ├─ site_survey_photos (uploaded_by)
  ├─ site_survey_archives (created_by, updated_by)
  └─ site_survey_archive_versions (changed_by)

site_survey_archives (id)
  ├─ site_survey_archive_versions (archive_id)
  └─ site_survey_archive_kv_index (archive_id)
```

## 迁移执行方法

### 方法一：使用迁移执行脚本（推荐）

```bash
cd /path/to/site-app/backend

# 1. 预览迁移（推荐先执行）
python execute_migration.py --dry-run

# 2. 执行迁移
python execute_migration.py

# 3. 验证结果
python execute_migration.py --dry-run

# 4. 如需回滚
python execute_migration.py --rollback
```

### 方法二：使用Alembic命令

```bash
cd /path/to/site-app/backend

# 1. 升级到最新版本
alembic upgrade add_site_survey_system

# 2. 验证结果
alembic current
alembic history --verbose

# 3. 如需回滚
alembic downgrade -1
```

### 方法三：手动执行SQL（不推荐）

```bash
# 仅在Alembic不可用时使用
sqlite3 data.db < migration_add_site_survey_system.sql
```

## 迁移前检查清单

- [ ] 备份数据库文件
  ```bash
  cp backend/data.db backend/data.db.backup.$(date +%Y%m%d_%H%M%S)
  ```

- [ ] 停止后端服务
  ```bash
  pkill -f "uvicorn.*8000"
  # 或
  # 使用PM2管理服务: pm2 stop site-app
  ```

- [ ] 检查数据库文件权限
  ```bash
  ls -la backend/data.db
  # 确保当前用户有读写权限
  ```

- [ ] 确认依赖表已存在
  ```bash
  # 检查以下表是否存在：
  - users
  - sites
  - work_orders
  - site_inspections
  - inspection_templates
  ```

## 迁移后验证清单

- [ ] 检查数据库版本
  ```bash
  python execute_migration.py --dry-run
  # 或
  sqlite3 backend/data.db "SELECT * FROM alembic_version;"
  ```

- [ ] 检查新表是否创建
  ```bash
  sqlite3 backend/data.db ".tables" | grep -E "(site_survey|survey_archive)"
  ```

- [ ] 启动后端服务
  ```bash
  cd backend
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  ```

- [ ] 测试API接口
  ```bash
  curl http://localhost:8000/health
  curl http://localhost:8000/docs
  ```

- [ ] 测试调查档案功能
  - 登录系统
  - 创建调查档案
  - 上传照片
  - 保存并查看结果

## 常见问题解决

### Q1: 迁移脚本执行失败，提示"table already exists"
**原因**: 数据库中已存在同名表

**解决**:
```bash
# 检查当前数据库状态
sqlite3 backend/data.db ".schema site_surveys"

# 如果表结构不一致，需要先删除旧表
sqlite3 backend/data.db "DROP TABLE IF EXISTS site_surveys;"

# 重新执行迁移
python execute_migration.py
```

### Q2: 迁移脚本执行失败，提示"foreign key constraint failed"
**原因**: 依赖的外键表不存在或不匹配

**解决**:
```bash
# 检查依赖表
sqlite3 backend/data.db "SELECT name FROM sqlite_master WHERE type='table';"

# 确保所有依赖表存在：
# - users
# - sites
# - work_orders
# - site_inspections
# - inspection_templates

# 如有缺失，参考项目文档初始化数据库
python start_backend.py
```

### Q3: 权限错误"database is locked"
**原因**: 数据库文件被其他进程占用

**解决**:
```bash
# 1. 停止所有可能访问数据库的进程
pkill -f "uvicorn"
pkill -f "python.*app.main"
pkill -f "sqlite"

# 2. 检查文件锁
lsof backend/data.db

# 3. 重启后执行迁移
python execute_migration.py
```

### Q4: 迁移成功后API调用500错误
**原因**: 模型变更未同步到代码

**解决**:
```bash
# 1. 重启后端服务
pkill -f "uvicorn.*8000"
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 2. 检查日志
tail -f logs/app.log

# 3. 检查API文档是否正常
curl http://localhost:8000/docs
```

## API接口说明

迁移后新增的API接口：

### 调查管理
- `POST /api/surveys` - 创建调查记录
- `GET /api/surveys/{id}` - 获取调查详情
- `PUT /api/surveys/{id}` - 更新调查记录
- `GET /api/surveys?site_id={site_id}` - 查询站点的调查记录

### 调查照片
- `POST /api/surveys/{id}/photos` - 上传调查照片
- `GET /api/surveys/{id}/photos` - 获取调查照片列表
- `DELETE /api/photos/{photo_id}` - 删除照片

### 调查档案
- `POST /api/survey-archives` - 创建档案
- `GET /api/survey-archives/{id}` - 获取档案详情
- `POST /api/survey-archives/{id}/versions` - 创建档案版本
- `GET /api/survey-archives/{id}/versions` - 获取版本历史

### 档案索引
- `GET /api/survey-archives/{id}/index` - 获取档案KV索引
- `POST /api/survey-archives/index/search` - 搜索档案内容

## 性能优化建议

1. **索引优化**
   - 已为所有外键字段创建索引
   - 为常用查询字段创建复合索引
   - KV索引表支持高效的条件查询

2. **存储优化**
   - JSON字段建议内容不超过10MB
   - 大型照片建议存储在文件系统，数据库只存路径
   - 定期清理过期的临时数据

3. **查询优化**
   - 使用KV索引进行复杂条件查询
   - 避免对JSON字段进行全表扫描
   - 合理使用分页查询

## 数据安全与备份

1. **定期备份**
   ```bash
   # 每日备份脚本
   #!/bin/bash
   BACKUP_DIR="/backup/site-app/$(date +%Y%m%d)"
   mkdir -p $BACKUP_DIR
   cp backend/data.db $BACKUP_DIR/
   tar -czf $BACKUP_DIR/uploads.tar.gz uploads/
   ```

2. **数据恢复**
   ```bash
   # 恢复数据库
   cp backup/20251106/data.db backend/data.db
   alembic upgrade head
   ```

3. **数据迁移到MySQL**
   ```bash
   # 如需从SQLite迁移到MySQL
   python -c "
   from sqlalchemy import create_engine
   from app.core.database import Base

   sqlite_engine = create_engine('sqlite:///data.db')
   mysql_engine = create_engine('mysql://user:pass@host/db')

   Base.metadata.create_all(mysql_engine)
   # 使用mysqldump或其他工具进行数据迁移
   "
   ```

## 技术支持

如遇到问题，请：

1. 查看迁移日志：`backend/logs/migration.log`
2. 检查数据库状态：`python execute_migration.py --dry-run`
3. 参考项目文档：`docs/` 目录
4. 提交Issue：https://github.com/your-repo/issues

---

**文档版本**: v1.0
**最后更新**: 2025-11-06
**适用版本**: fecdc1e → 最新版本
