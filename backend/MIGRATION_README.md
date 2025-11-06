# 数据库迁移快速指南

## 📦 迁移文件

已为你生成以下迁移文件：

1. **`alembic/versions/add_site_survey_system.py`** - Alembic迁移脚本
2. **`execute_migration.py`** - 迁移执行脚本（推荐使用）
3. **`SITE_SURVEYS_MIGRATION_GUIDE.md`** - 详细迁移文档

## 🚀 快速执行

### 步骤1：备份数据库
```bash
cd /path/to/site-app/backend
cp data.db data.db.backup.$(date +%Y%m%d_%H%M%S)
```

### 步骤2：执行迁移（推荐）
```bash
# 预览迁移（先执行）
python execute_migration.py --dry-run

# 执行迁移
python execute_migration.py
```

### 步骤3：验证
```bash
# 重启后端服务
pkill -f "uvicorn.*8000"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 测试API
curl http://localhost:8000/docs
```

## 📋 变更内容

本次迁移从 `fecdc1e` 升级到最新版本，新增：

- ✅ 调查档案管理系统
- ✅ 5个新表结构
- ✅ 完整的版本历史追踪
- ✅ KV索引支持复杂查询

## 🔍 详细文档

完整文档请查看：`SITE_SURVEYS_MIGRATION_GUIDE.md`

## ❓ 遇到问题？

1. 查看详细文档中的"常见问题解决"部分
2. 使用 `--dry-run` 预览SQL语句
3. 检查数据库文件权限：`ls -la data.db`
4. 停止所有后端服务后重试

## 📞 技术支持

如需帮助，请提供：
- 迁移脚本输出结果
- 错误日志完整内容
- 数据库版本信息：`python execute_migration.py --dry-run`
