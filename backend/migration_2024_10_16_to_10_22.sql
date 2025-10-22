-- ========================================
-- 数据库迁移脚本 (SQLite)
-- 从版本：2024-10-16之前
-- 到版本：2024-10-22
-- 执行方式: sqlite3 site_manager.db < migration_2024_10_16_to_10_22.sql
-- ========================================

BEGIN TRANSACTION;

-- ========================================
-- 1. 新增 user_logs 表
-- ========================================
CREATE TABLE IF NOT EXISTS user_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(100) NOT NULL,
    user_id INTEGER,
    username VARCHAR(50),
    timestamp DATETIME NOT NULL,
    action VARCHAR(100) NOT NULL,
    level VARCHAR(20) DEFAULT 'INFO',
    page_route VARCHAR(200),
    page_options JSON,
    action_data JSON,
    device_platform VARCHAR(50),
    device_model VARCHAR(100),
    screen_width INTEGER,
    screen_height INTEGER,
    error_message TEXT,
    error_stack TEXT,
    error_context JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_logs_user_timestamp ON user_logs(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_user_logs_session_timestamp ON user_logs(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_user_logs_action_timestamp ON user_logs(action, timestamp);
CREATE INDEX IF NOT EXISTS idx_user_logs_level_timestamp ON user_logs(level, timestamp);
CREATE INDEX IF NOT EXISTS idx_user_logs_page_timestamp ON user_logs(page_route, timestamp);

-- ========================================
-- 2. 新增站点规划系统表
-- ========================================

-- 2.1 站点规划主表
CREATE TABLE IF NOT EXISTS site_planning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    bands JSON,
    sector_count INTEGER DEFAULT 0,
    notes VARCHAR(500),
    is_current BOOLEAN DEFAULT TRUE,
    created_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_site_planning_site_id ON site_planning(site_id);
CREATE INDEX IF NOT EXISTS idx_site_planning_is_current ON site_planning(is_current);

-- 2.2 扇区规划表
CREATE TABLE IF NOT EXISTS site_planning_sectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    planning_id INTEGER NOT NULL,
    sector_index INTEGER NOT NULL,
    azimuth_deg FLOAT,
    downtilt_deg FLOAT,
    bands JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (planning_id) REFERENCES site_planning(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_site_planning_sectors_planning_id ON site_planning_sectors(planning_id);

-- 2.3 天线端口表
CREATE TABLE IF NOT EXISTS site_antenna_ports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    planning_id INTEGER NOT NULL,
    port_label VARCHAR(50) NOT NULL,
    sector_index INTEGER NOT NULL,
    band VARCHAR(20),
    mimo_chain VARCHAR(20),
    remarks VARCHAR(200),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (planning_id) REFERENCES site_planning(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_site_antenna_ports_planning_id ON site_antenna_ports(planning_id);

-- 2.4 交换机端口表
CREATE TABLE IF NOT EXISTS site_switch_ports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    planning_id INTEGER NOT NULL,
    port_no VARCHAR(50) NOT NULL,
    vlan_ids JSON,
    is_uplink BOOLEAN DEFAULT FALSE,
    poe BOOLEAN DEFAULT FALSE,
    description VARCHAR(200),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (planning_id) REFERENCES site_planning(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_site_switch_ports_planning_id ON site_switch_ports(planning_id);

-- 2.5 规划变更日志表
CREATE TABLE IF NOT EXISTS planning_change_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    planning_id INTEGER,
    operation VARCHAR(20) NOT NULL,
    actor_id INTEGER NOT NULL,
    summary VARCHAR(500),
    before_snapshot JSON,
    after_snapshot JSON,
    diff JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (planning_id) REFERENCES site_planning(id),
    FOREIGN KEY (actor_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_planning_change_logs_site_id ON planning_change_logs(site_id);

-- ========================================
-- 3. 修改 inspection_check_items 表
-- ========================================

-- 3.1 添加 description 字段（检查项描述）
-- 注意：SQLite的ALTER TABLE ADD COLUMN不支持IF NOT EXISTS
-- 如果字段已存在会报错，可以忽略错误继续执行
ALTER TABLE inspection_check_items ADD COLUMN description TEXT;

-- 3.2 添加 equipment_sn 字段（绑定设备序列号）
ALTER TABLE inspection_check_items ADD COLUMN equipment_sn VARCHAR(100);

-- 3.3 添加 fields 字段（字段配置JSON）
ALTER TABLE inspection_check_items ADD COLUMN fields JSON;

-- ========================================
-- 4. 修改 work_orders 表
-- ========================================

-- 4.1 添加 activated_at 字段（开通时间）
ALTER TABLE work_orders ADD COLUMN activated_at DATETIME;

-- ========================================
-- 5. 修改 pickup_records 表
-- ========================================

-- 5.1 添加扫码信息字段
ALTER TABLE pickup_records ADD COLUMN serial_number VARCHAR(100);
ALTER TABLE pickup_records ADD COLUMN mac_address_1 VARCHAR(50);
ALTER TABLE pickup_records ADD COLUMN mac_address_2 VARCHAR(50);
ALTER TABLE pickup_records ADD COLUMN equipment_instance_id VARCHAR(32);

-- 5.2 添加 work_order_id 字段（替代 task_id）
-- 注意：如果要完全迁移数据，需要在应用层处理
ALTER TABLE pickup_records ADD COLUMN work_order_id VARCHAR(32);

-- 注意：SQLite不支持直接删除列或修改外键
-- 如需完全迁移 task_id -> work_order_id，请手动处理：
-- 1. 创建新表结构
-- 2. 复制数据
-- 3. 删除旧表
-- 4. 重命名新表
-- 或者保留两个字段，在应用层逐步迁移

-- ========================================
-- 6. 修改 template_bindings 表
-- ========================================

-- 6.1 添加 task_type 字段（任务类型维度）
ALTER TABLE template_bindings ADD COLUMN task_type VARCHAR(50);

-- ========================================
-- 迁移完成
-- ========================================

COMMIT;

-- 输出成功消息
SELECT '✅ 数据库迁移完成！' AS message;
SELECT '⚠️  注意：如果某些字段已存在，ALTER TABLE语句可能会失败，这是正常的。' AS note;
SELECT '📌 请检查应用日志确保所有功能正常。' AS reminder;
