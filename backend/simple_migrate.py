#!/usr/bin/env python3
"""
简化的数据库迁移脚本 - 不依赖Alembic
直接使用SQLAlchemy创建新表

从版本 fecdc1e 升级到最新版本，新增调查档案管理系统

使用方式:
    python simple_migrate.py
"""

import sys
import os
from sqlalchemy import create_engine, text
from datetime import datetime


def get_db_path():
    """获取数据库路径"""
    # 优先使用环境变量
    db_path = os.environ.get('DATABASE_PATH')
    if not db_path:
        # 默认使用当前目录的 data.db
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
    return db_path


def get_db_url():
    """获取数据库连接URL"""
    # 优先使用已配置的 DATABASE_URL
    from app.core.config import settings
    if hasattr(settings, 'DATABASE_URL') and settings.DATABASE_URL:
        return settings.DATABASE_URL
    else:
        db_path = get_db_path()
        return f"sqlite:///{db_path}"


def backup_db():
    """备份数据库"""
    db_path = get_db_path()
    if os.path.exists(db_path):
        backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✅ 数据库已备份到: {backup_path}")
        return backup_path
    else:
        print("⚠️  数据库文件不存在，将创建新数据库")
        return None


def check_tables_exist():
    """检查表是否已存在"""
    try:
        db_url = get_db_url()
        engine = create_engine(db_url, echo=False)
        with engine.connect() as conn:
            # 检查 site_surveys 表是否已存在
            result = conn.execute(text("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='site_surveys'
            """))
            exists = result.fetchone() is not None
            if exists:
                print("⚠️  site_surveys 表已存在，跳过迁移")
                return True
            return False
    except Exception as e:
        print(f"⚠️  检查表存在性时出错: {e}")
        return False


def create_tables():
    """创建新表"""
    db_url = get_db_url()
    db_path = get_db_path()

    print(f"🔗 连接到数据库: {db_path}")
    engine = create_engine(db_url, echo=False)

    with engine.connect() as conn:
        print("\n📋 创建表结构...")

        # 1. 创建 site_surveys 表
        print("  - 创建 site_surveys 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS site_surveys (
                id VARCHAR(32) NOT NULL PRIMARY KEY,
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
                work_order_id VARCHAR(32)
            )
        """))

        # 索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_site_surveys_site_id ON site_surveys (site_id)"))

        # 2. 创建 site_survey_photos 表
        print("  - 创建 site_survey_photos 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS site_survey_photos (
                id VARCHAR(32) NOT NULL PRIMARY KEY,
                survey_id VARCHAR(32) NOT NULL,
                original_name VARCHAR(255),
                file_path VARCHAR(500) NOT NULL,
                file_size INTEGER,
                mime_type VARCHAR(100),
                category VARCHAR(50),
                sort_order INTEGER,
                exif JSON,
                latitude FLOAT,
                longitude FLOAT,
                gps_accuracy FLOAT,
                address TEXT,
                taken_at DATETIME,
                has_watermark BOOLEAN DEFAULT 0,
                watermark_data JSON,
                hash_value VARCHAR(64),
                uploaded_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_site_survey_photos_survey_id ON site_survey_photos (survey_id)"))

        # 3. 创建 site_survey_archives 表
        print("  - 创建 site_survey_archives 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS site_survey_archives (
                id VARCHAR(32) NOT NULL PRIMARY KEY,
                site_id INTEGER NOT NULL,
                work_order_id VARCHAR(32) NOT NULL,
                inspection_id VARCHAR(32) NOT NULL,
                template_id VARCHAR(32) NOT NULL,
                template_version VARCHAR(20),
                current_version INTEGER DEFAULT 1,
                content JSON NOT NULL,
                status VARCHAR(20) DEFAULT 'active',
                created_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_site_survey_archives_site_id ON site_survey_archives (site_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_site_survey_archives_work_order_id ON site_survey_archives (work_order_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_site_survey_archives_inspection_id ON site_survey_archives (inspection_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_site_survey_archives_template_id ON site_survey_archives (template_id)")

        # 4. 创建 site_survey_archive_versions 表
        print("  - 创建 site_survey_archive_versions 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS site_survey_archive_versions (
                id VARCHAR(32) NOT NULL PRIMARY KEY,
                archive_id VARCHAR(32) NOT NULL,
                version INTEGER NOT NULL,
                content JSON NOT NULL,
                diff JSON,
                change_summary TEXT,
                changed_by INTEGER,
                changed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_archive_versions_archive_id ON site_survey_archive_versions (archive_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_archive_versions_version ON site_survey_archive_versions (version)"))

        # 5. 创建 site_survey_archive_kv_index 表
        print("  - 创建 site_survey_archive_kv_index 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS site_survey_archive_kv_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                archive_id VARCHAR(32) NOT NULL,
                version INTEGER NOT NULL,
                path VARCHAR(200) NOT NULL,
                field_label VARCHAR(200),
                type VARCHAR(20),
                value_number FLOAT,
                value_bool BOOLEAN,
                value_string TEXT,
                value_datetime DATETIME,
                raw_json JSON,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kv_index_archive_id ON site_survey_archive_kv_index (archive_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kv_index_path ON site_survey_archive_kv_index (path)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kv_index_version ON site_survey_archive_kv_index (version)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kv_index_updated_at ON site_survey_archive_kv_index (updated_at)"))

        conn.commit()
        print("\n✅ 表结构创建完成！")

    # 验证表
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND (
                name LIKE 'site_survey%' OR name LIKE 'survey_archive%'
            )
            ORDER BY name
        """))
        tables = [row[0] for row in result]
        print(f"\n📊 成功创建 {len(tables)} 个表:")
        for table in tables:
            print(f"  ✓ {table}")

        # 显示表结构摘要
        print("\n📋 表结构摘要:")
        print("  - site_surveys: 调查主表（基础信息、位置、结构、电力传输等）")
        print("  - site_survey_photos: 调查照片表（GPS水印、EXIF信息）")
        print("  - site_survey_archives: 调查档案表（当前版本快照，JSON格式）")
        print("  - site_survey_archive_versions: 档案版本历史表（追加写模式）")
        print("  - site_survey_archive_kv_index: 档案KV索引表（支持复杂查询）")

    return True


def main():
    """主函数"""
    print("=" * 70)
    print("🚀 简化数据库迁移脚本 - 不依赖Alembic")
    print("=" * 70)
    print()
    print("功能说明:")
    print("  - 从版本 fecdc1e 升级到最新版本")
    print("  - 新增调查档案管理系统")
    print("  - 不依赖Alembic，直接使用SQLAlchemy")
    print()
    print("=" * 70)

    # 备份数据库
    print("\n📦 步骤1: 备份数据库")
    backup_path = backup_db()

    # 检查表是否已存在
    print("\n🔍 步骤2: 检查表是否存在")
    if check_tables_exist():
        print("\n✅ 表已存在，无需迁移")
        return

    # 创建表
    print("\n📋 步骤3: 创建新表")
    try:
        create_tables()
        print("\n" + "=" * 70)
        print("✅ 迁移完成！")
        print("=" * 70)
        print("\n📌 后续步骤:")
        print("1. 重启后端服务:")
        print("   pkill -f 'uvicorn.*8000'")
        print("   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
        print()
        print("2. 访问API文档:")
        print("   http://localhost:8000/docs")
        print()
        print("3. 测试调查档案功能:")
        print("   - 登录系统")
        print("   - 创建调查档案")
        print("   - 上传照片")
        print("   - 保存并查看结果")
        print()
        print("💡 提示:")
        print("- 如有外键约束错误，忽略即可（依赖表可能未创建）")
        print("- 备份文件位置: " + (backup_path if backup_path else "新数据库"))
        print("- 如需回滚，使用备份文件恢复: cp <备份文件> data.db")
        print()
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        print("\n🔧 故障排除:")
        print("1. 检查数据库文件权限: ls -la data.db")
        print("2. 确保已停止所有后端服务")
        print("3. 检查依赖是否安装: pip install -r requirements.txt")
        print("4. 从备份恢复: cp " + (backup_path if backup_path else "<备份文件>") + " data.db")
        sys.exit(1)


if __name__ == "__main__":
    main()
