#!/bin/bash
# 数据库迁移检查和修复脚本

echo "======================================"
echo "site_surveys work_order_id 迁移检查"
echo "======================================"
echo

# 查找数据库文件
DB_PATH=""
if [ -f "site_manager.db" ]; then
    DB_PATH="site_manager.db"
elif [ -f "../site_manager.db" ]; then
    DB_PATH="../site_manager.db"
elif [ -f "/usr/local/site-app/backend/site_manager.db" ]; then
    DB_PATH="/usr/local/site-app/backend/site_manager.db"
else
    echo "❌ 未找到 site_manager.db 文件"
    echo "当前目录: $(pwd)"
    echo "请在包含 site_manager.db 的目录中执行此脚本"
    exit 1
fi

echo "📍 数据库文件: $DB_PATH"
echo

# 检查当前表结构
echo "1. 检查 site_surveys 表结构..."
sqlite3 "$DB_PATH" "PRAGMA table_info(site_surveys);" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 无法访问数据库或表不存在"
    exit 1
fi

echo
echo "2. 检查是否包含 work_order_id 字段..."
HAS_FIELD=$(sqlite3 "$DB_PATH" "PRAGMA table_info(site_surveys);" 2>/dev/null | grep -c "work_order_id" || true)
if [ "$HAS_FIELD" -eq 0 ]; then
    echo "❌ work_order_id 字段不存在！"
    echo
    echo "3. 尝试添加 work_order_id 字段..."
    sqlite3 "$DB_PATH" "ALTER TABLE site_surveys ADD COLUMN work_order_id VARCHAR(32);" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✅ 字段添加成功！"
    else
        echo "❌ 字段添加失败！"
        echo "可能原因："
        echo "  - 字段已存在但未被检测到"
        echo "  - 表被锁定"
        echo "  - 权限不足"
        exit 1
    fi
else
    echo "✅ work_order_id 字段已存在"
fi

echo
echo "4. 验证最终表结构..."
sqlite3 "$DB_PATH" "PRAGMA table_info(site_surveys);" | grep -E "(id|work_order_id)"

echo
echo "======================================"
echo "✅ 检查完成！"
echo "======================================"
echo
echo "请重启后端服务："
echo "  pkill -f 'uvicorn.*8000'"
echo "  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo
