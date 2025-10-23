#!/usr/bin/env python3
"""
数据库迁移脚本
智能检测并执行所需的数据库结构变更
"""

import sys
import sqlite3
from datetime import datetime

def get_existing_columns(cursor, table_name):
    """获取表的现有列"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}

def table_exists(cursor, table_name):
    """检查表是否存在"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None

def add_column_if_not_exists(cursor, table_name, column_name, column_type):
    """如果列不存在则添加"""
    existing_columns = get_existing_columns(cursor, table_name)
    if column_name not in existing_columns:
        print(f"  ✅ 添加字段: {table_name}.{column_name}")
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        return True
    else:
        print(f"  ⏭️  字段已存在: {table_name}.{column_name}")
        return False

def run_migration(db_path='site_manager.db'):
    """执行数据库迁移"""
    
    print("=" * 80)
    print("数据库迁移工具")
    print("从版本：2024-10-16之前")
    print("到版本：2024-10-22")
    print("=" * 80)
    print()
    
    # 备份提示
    backup_name = f"site_manager.db.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"⚠️  建议先备份数据库:")
    print(f"   cp {db_path} {backup_name}")
    print()
    
    response = input("是否继续执行迁移? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ 迁移已取消")
        return False
    
    print()
    print("开始迁移...")
    print()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        changes_made = 0
        
        # ========================================
        # 1. 创建新表
        # ========================================
        print("【1】检查并创建新表...")
        
        new_tables = {
            'user_logs': '''
                CREATE TABLE user_logs (
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
                )
            ''',
            'site_planning': '''
                CREATE TABLE site_planning (
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
                )
            ''',
            'site_planning_sectors': '''
                CREATE TABLE site_planning_sectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    planning_id INTEGER NOT NULL,
                    sector_index INTEGER NOT NULL,
                    azimuth_deg FLOAT,
                    downtilt_deg FLOAT,
                    bands JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (planning_id) REFERENCES site_planning(id) ON DELETE CASCADE
                )
            ''',
            'site_antenna_ports': '''
                CREATE TABLE site_antenna_ports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    planning_id INTEGER NOT NULL,
                    port_label VARCHAR(50) NOT NULL,
                    sector_index INTEGER NOT NULL,
                    band VARCHAR(20),
                    mimo_chain VARCHAR(20),
                    remarks VARCHAR(200),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (planning_id) REFERENCES site_planning(id) ON DELETE CASCADE
                )
            ''',
            'site_switch_ports': '''
                CREATE TABLE site_switch_ports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    planning_id INTEGER NOT NULL,
                    port_no VARCHAR(50) NOT NULL,
                    vlan_ids JSON,
                    is_uplink BOOLEAN DEFAULT FALSE,
                    poe BOOLEAN DEFAULT FALSE,
                    description VARCHAR(200),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (planning_id) REFERENCES site_planning(id) ON DELETE CASCADE
                )
            ''',
            'planning_change_logs': '''
                CREATE TABLE planning_change_logs (
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
                )
            '''
            ,
            'site_surveys': '''
                CREATE TABLE site_surveys (
                    id VARCHAR(32) PRIMARY KEY,
                    site_id INTEGER NOT NULL,
                    survey_date DATETIME NOT NULL,
                    surveyor_name VARCHAR(100) NOT NULL,
                    surveyor_phone VARCHAR(30),
                    latitude FLOAT,
                    longitude FLOAT,
                    address TEXT,
                    gps_accuracy FLOAT,
                    site_type VARCHAR(50),
                    tower_type VARCHAR(50),
                    available_height_m FLOAT,
                    load_capacity_kg FLOAT,
                    power_available BOOLEAN,
                    power_distance_m FLOAT,
                    power_capacity_kw FLOAT,
                    earthing_feasible BOOLEAN,
                    fiber_available BOOLEAN,
                    fiber_distance_m FLOAT,
                    duct_notes TEXT,
                    microwave_los BOOLEAN,
                    los_azimuth_deg FLOAT,
                    los_distance_km FLOAT,
                    sensitive_points TEXT,
                    safety_notes TEXT,
                    permits_constraints TEXT,
                    owner_name VARCHAR(100),
                    owner_phone VARCHAR(30),
                    access_time_window VARCHAR(100),
                    entry_constraints TEXT,
                    feasibility VARCHAR(30),
                    risks TEXT,
                    recommendations TEXT,
                    extra_data JSON,
                    created_by INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (site_id) REFERENCES sites(id),
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
            ''',
            'site_survey_photos': '''
                CREATE TABLE site_survey_photos (
                    id VARCHAR(32) PRIMARY KEY,
                    survey_id VARCHAR(32) NOT NULL,
                    original_name VARCHAR(255),
                    file_path VARCHAR(500) NOT NULL,
                    file_size INTEGER,
                    mime_type VARCHAR(100),
                    category VARCHAR(50),
                    latitude FLOAT,
                    longitude FLOAT,
                    gps_accuracy FLOAT,
                    address TEXT,
                    taken_at DATETIME,
                    has_watermark BOOLEAN DEFAULT FALSE,
                    watermark_data JSON,
                    hash_value VARCHAR(64),
                    uploaded_by INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (survey_id) REFERENCES site_surveys(id) ON DELETE CASCADE,
                    FOREIGN KEY (uploaded_by) REFERENCES users(id)
                )
            '''
        }
        
        for table_name, create_sql in new_tables.items():
            if not table_exists(cursor, table_name):
                print(f"  ✅ 创建表: {table_name}")
                cursor.execute(create_sql)
                changes_made += 1
            else:
                print(f"  ⏭️  表已存在: {table_name}")
        
        # 创建索引
        print()
        print("【2】创建索引...")
        
        indexes = [
            ("idx_user_logs_user_timestamp", "user_logs", "user_id, timestamp"),
            ("idx_user_logs_session_timestamp", "user_logs", "session_id, timestamp"),
            ("idx_user_logs_action_timestamp", "user_logs", "action, timestamp"),
            ("idx_user_logs_level_timestamp", "user_logs", "level, timestamp"),
            ("idx_user_logs_page_timestamp", "user_logs", "page_route, timestamp"),
            ("idx_site_planning_site_id", "site_planning", "site_id"),
            ("idx_site_planning_is_current", "site_planning", "is_current"),
            ("idx_site_planning_sectors_planning_id", "site_planning_sectors", "planning_id"),
            ("idx_site_antenna_ports_planning_id", "site_antenna_ports", "planning_id"),
            ("idx_site_switch_ports_planning_id", "site_switch_ports", "planning_id"),
            ("idx_planning_change_logs_site_id", "planning_change_logs", "site_id"),
            ("idx_site_surveys_site_id", "site_surveys", "site_id"),
            ("idx_site_surveys_survey_date", "site_surveys", "survey_date"),
            ("idx_site_surveys_feasibility", "site_surveys", "feasibility"),
            ("idx_site_survey_photos_survey_id", "site_survey_photos", "survey_id"),
        ]
        
        for index_name, table_name, columns in indexes:
            # 检查索引是否已存在
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,)
            )
            if cursor.fetchone() is None:
                print(f"  ✅ 创建索引: {index_name}")
                cursor.execute(f"CREATE INDEX {index_name} ON {table_name}({columns})")
                changes_made += 1
            else:
                print(f"  ⏭️  索引已存在: {index_name}")
        
        # ========================================
        # 3. 修改现有表
        # ========================================
        print()
        print("【3】修改现有表...")
        
        # 3.1 inspection_check_items
        if table_exists(cursor, 'inspection_check_items'):
            print()
            print("  📋 inspection_check_items:")
            if add_column_if_not_exists(cursor, 'inspection_check_items', 'description', 'TEXT'):
                changes_made += 1
            if add_column_if_not_exists(cursor, 'inspection_check_items', 'equipment_sn', 'VARCHAR(100)'):
                changes_made += 1
            if add_column_if_not_exists(cursor, 'inspection_check_items', 'fields', 'JSON'):
                changes_made += 1
        
        # 3.2 work_orders
        if table_exists(cursor, 'work_orders'):
            print()
            print("  📋 work_orders:")
            if add_column_if_not_exists(cursor, 'work_orders', 'activated_at', 'DATETIME'):
                changes_made += 1
        
        # 3.3 pickup_records
        if table_exists(cursor, 'pickup_records'):
            print()
            print("  📋 pickup_records:")
            if add_column_if_not_exists(cursor, 'pickup_records', 'serial_number', 'VARCHAR(100)'):
                changes_made += 1
            if add_column_if_not_exists(cursor, 'pickup_records', 'mac_address_1', 'VARCHAR(50)'):
                changes_made += 1
            if add_column_if_not_exists(cursor, 'pickup_records', 'mac_address_2', 'VARCHAR(50)'):
                changes_made += 1
            if add_column_if_not_exists(cursor, 'pickup_records', 'equipment_instance_id', 'VARCHAR(32)'):
                changes_made += 1
            if add_column_if_not_exists(cursor, 'pickup_records', 'work_order_id', 'VARCHAR(32)'):
                changes_made += 1
        
        # 3.4 template_bindings
        if table_exists(cursor, 'template_bindings'):
            print()
            print("  📋 template_bindings:")
            if add_column_if_not_exists(cursor, 'template_bindings', 'task_type', 'VARCHAR(50)'):
                changes_made += 1
        
        # 提交更改
        conn.commit()
        
        print()
        print("=" * 80)
        print(f"✅ 迁移完成！共执行 {changes_made} 项变更")
        print("=" * 80)
        print()
        print("📌 下一步:")
        print("  1. 检查应用日志确保无错误")
        print("  2. 验证各功能模块正常工作")
        print("  3. 如有问题可回滚到备份数据库")
        print()
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ 数据库错误: {e}")
        conn.rollback()
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    import os
    
    # 获取数据库路径
    db_path = os.environ.get('DB_PATH', 'site_manager.db')
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"数据库路径: {db_path}")
    print()
    
    success = run_migration(db_path)
    
    sys.exit(0 if success else 1)
