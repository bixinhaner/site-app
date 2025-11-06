#!/usr/bin/env python3
"""
数据库迁移执行脚本
从版本 fecdc1e0054025762b49db19732b93d3d1de3608 升级到最新版本

使用方法:
    python execute_migration.py --dry-run    # 预览迁移SQL（不执行）
    python execute_migration.py              # 执行迁移
    python execute_migration.py --rollback   # 回滚迁移
"""

import argparse
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings


def get_database_url():
    """获取数据库连接URL"""
    if settings.DATABASE_URL:
        return settings.DATABASE_URL
    else:
        # SQLite 默认路径
        db_path = os.path.join(os.path.dirname(__file__), "data.db")
        return f"sqlite:///{db_path}"


def check_current_revision():
    """检查当前数据库版本"""
    engine = create_engine(get_database_url())
    with engine.connect() as conn:
        try:
            # 检查alembic_version表是否存在
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar()
            return version
        except Exception as e:
            print(f"⚠️  无法读取数据库版本: {e}")
            return None


def check_migration_files():
    """检查迁移文件是否存在"""
    migration_file = "alembic/versions/add_site_survey_system.py"
    if os.path.exists(migration_file):
        return True
    print(f"❌ 迁移文件不存在: {migration_file}")
    return False


def dry_run():
    """预览迁移SQL"""
    print("=" * 70)
    print("🔍 迁移预览模式 - 仅生成SQL，不执行数据库操作")
    print("=" * 70)
    print()

    # 检查版本
    current = check_current_revision()
    if current:
        print(f"📊 当前数据库版本: {current}")
    else:
        print("📊 当前数据库版本: 未初始化（全新数据库）")
    print()

    # 检查迁移文件
    if not check_migration_files():
        return False

    print("📋 将要执行的迁移:")
    print("  - 新增调查档案管理系统")
    print("    * site_surveys 表")
    print("    * site_survey_photos 表")
    print("    * site_survey_archives 表")
    print("    * site_survey_archive_versions 表")
    print("    * site_survey_archive_kv_index 表")
    print()

    print("⚠️  注意事项:")
    print("  1. 建议在执行前备份数据库")
    print("  2. 确保后端服务已停止")
    print("  3. 确保数据库文件有写入权限")
    print()

    # 生成SQL
    try:
        from alembic.config import Config
        from alembic import command

        # 创建临时的Alembic配置
        alembic_cfg = Config("alembic.ini")
        output = []

        # 获取upgrade SQL
        from io import StringIO
        import contextlib

        f = StringIO()
        with contextlib.redirect_stderr(f):
            command.upgrade(alembic_cfg, "add_site_survey_system", sql=True)

        sql_output = f.getvalue()

        print("=" * 70)
        print("📝 生成的SQL语句:")
        print("=" * 70)
        print(sql_output)
        print("=" * 70)

    except Exception as e:
        print(f"⚠️  无法生成SQL预览: {e}")
        print("请直接执行迁移命令: alembic upgrade add_site_survey_system")

    return True


def execute_migration():
    """执行数据库迁移"""
    print("=" * 70)
    print("🚀 开始执行数据库迁移")
    print("=" * 70)
    print()

    # 检查版本
    current = check_current_revision()
    if current:
        print(f"📊 当前数据库版本: {current}")
    else:
        print("📊 当前数据库版本: 未初始化（全新数据库）")
    print()

    # 检查迁移文件
    if not check_migration_files():
        return False

    # 执行迁移
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "add_site_survey_system")

        print("✅ 迁移执行成功！")
        print()

        # 验证结果
        new_version = check_current_revision()
        if new_version:
            print(f"📊 新数据库版本: {new_version}")

        print()
        print("🎉 升级完成！")
        print()
        print("后续操作建议:")
        print("  1. 重启后端服务")
        print("  2. 访问 http://localhost:8000/docs 测试API")
        print("  3. 验证调查档案功能是否正常")
        print()

        return True

    except Exception as e:
        print(f"❌ 迁移执行失败: {e}")
        print()
        print("可能的原因:")
        print("  1. 数据库文件权限不足")
        print("  2. 数据库版本已存在此迁移")
        print("  3. 数据库连接失败")
        print()
        print("建议操作:")
        print("  1. 检查错误信息")
        print("  2. 使用 --dry-run 预览SQL")
        print("  3. 手动执行 Alembic 命令: alembic upgrade add_site_survey_system")
        return False


def rollback_migration():
    """回滚数据库迁移"""
    print("=" * 70)
    print("⚠️  回滚数据库迁移")
    print("=" * 70)
    print()

    response = input("⚠️  确认要回滚迁移吗？这将删除所有新创建的表！[y/N]: ")
    if response.lower() != 'y':
        print("已取消回滚操作")
        return True

    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        command.downgrade(alembic_cfg, "-1")

        print("✅ 回滚执行成功！")
        print()

        new_version = check_current_revision()
        if new_version:
            print(f"📊 回滚后数据库版本: {new_version}")
        else:
            print("📊 数据库已回滚到初始状态")

        return True

    except Exception as e:
        print(f"❌ 回滚执行失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="数据库迁移执行工具")
    parser.add_argument("--dry-run", action="store_true", help="预览迁移SQL（不执行）")
    parser.add_argument("--rollback", action="store_true", help="回滚迁移")
    args = parser.parse_args()

    if args.rollback:
        return rollback_migration()
    elif args.dry_run:
        return dry_run()
    else:
        return execute_migration()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
