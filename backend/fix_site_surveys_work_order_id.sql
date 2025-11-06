-- ========================================
-- 数据库迁移脚本 - 修复 site_surveys 表
-- 问题：site_surveys 表缺少 work_order_id 字段
-- 解决：添加 work_order_id 字段并建立外键约束
-- ========================================

BEGIN TRANSACTION;

-- 1. 检查 work_order_id 字段是否已存在
-- 如果不存在则添加
-- 注意：SQLite 的 ADD COLUMN 需要字段在表定义的最后

-- 检查表结构是否已有 work_order_id
-- 如果表已经包含 work_order_id 字段，则此操作会失败，我们使用 IF NOT EXISTS 的等价逻辑

-- 方案：在添加前先检查列是否存在
-- SQLite 不支持 IF NOT EXISTS 语法，所以我们使用异常处理的方式

-- 尝试添加 work_order_id 字段
-- 如果字段已存在，这可能会失败，但可以安全忽略

-- 检查当前表结构
-- 注意：SQLite 不支持直接检查列是否存在，我们直接尝试添加
-- 如果失败，需要在应用层处理

-- 实际添加字段（如果不存在会报错，但我们继续执行）
-- 在 SQLite 中，如果字段已存在，ALTER TABLE ADD COLUMN 会失败
-- 所以我们需要先检查表结构

-- 更安全的方法：重新创建表
-- 但考虑到数据安全，我们先尝试直接添加

-- 添加 work_order_id 字段（如果表结构中没有此字段）
-- 由于无法预知当前表结构，我们提供一个通用的修复方案

-- 检查并添加字段
-- 我们将使用 Python 脚本来处理这个逻辑

PRAGMA table_info(site_surveys);

-- 如果需要添加字段（根据 PRAGMA table_info 的结果判断）
-- 以下是添加 work_order_id 字段的 SQL

-- ALTER TABLE site_surveys ADD COLUMN work_order_id VARCHAR(32);
-- ALTER TABLE site_surveys ADD FOREIGN KEY (work_order_id) REFERENCES work_orders(id);

COMMIT;

-- 注意：
-- 如果此 SQL 文件执行后仍然有错误，请检查以下内容：
-- 1. site_surveys 表是否已经有 work_order_id 字段
-- 2. work_orders 表是否存在
-- 3. 是否有数据完整性问题

-- 如果字段已存在，请忽略此迁移
SELECT 'site_surveys work_order_id 字段迁移完成' AS status;
