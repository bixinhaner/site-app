#!/usr/bin/env python3
"""
数据库初始化脚本
创建表结构并添加测试用户
"""

from sqlalchemy.orm import Session
from app.core.database import engine, Base, get_db
from app.models.user import User
from app.models.site import Site
from app.core.security import get_password_hash

def init_database():
    """初始化数据库"""
    print("正在初始化数据库...")
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建完成")
    
    # 创建数据库会话
    db = next(get_db())
    
    try:
        # 检查是否已有用户
        existing_user = db.query(User).filter(User.username == "admin").first()
        
        if not existing_user:
            # 创建默认管理员用户
            admin_user = User(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                full_name="系统管理员",
                role="admin",
                is_active=True,
                department="IT部门",
                position="系统管理员"
            )
            db.add(admin_user)
            
            # 创建测试用户
            test_user = User(
                username="test",
                email="test@example.com",
                hashed_password=get_password_hash("test123"),
                full_name="测试用户",
                role="user",
                is_active=True,
                department="测试部门",
                position="测试员"
            )
            db.add(test_user)
            
            # 创建检查员用户
            inspector_user = User(
                username="inspector",
                email="inspector@example.com",
                hashed_password=get_password_hash("inspector123"),
                full_name="安装施工人员",
                role="inspector",
                is_active=True,
                department="工程部",
                position="安装施工人员"
            )
            db.add(inspector_user)
            
            # 创建Tom用户
            tom_user = User(
                username="tom",
                email="tom@example.com",
                hashed_password=get_password_hash("tom123456"),
                full_name="Tom",
                role="inspector",
                is_active=True,
                department="工程部",
                position="安装施工人员"
            )
            db.add(tom_user)
            
            db.commit()
            print("✅ 默认用户创建完成")
            print("   管理员: admin / admin123")
            print("   测试用户: test / test123")
            print("   检查员: inspector / inspector123")
            print("   Tom用户: tom / tom123456")
        else:
            print("ℹ️ 管理员用户已存在")
            
        # 单独检查Tom用户是否存在
        tom_existing = db.query(User).filter(User.username == "tom").first()
        if not tom_existing:
            # 创建Tom用户
            tom_user = User(
                username="tom",
                email="tom@example.com",
                hashed_password=get_password_hash("tom123456"),
                full_name="Tom",
                role="inspector",
                is_active=True,
                department="工程部",
                position="安装施工人员"
            )
            db.add(tom_user)
            db.commit()
            print("✅ Tom用户创建完成: tom / tom123456")
        else:
            print("ℹ️ Tom用户已存在")
            
        # 检查是否有测试站点
        existing_site = db.query(Site).first()
        
        if not existing_site:
            # 创建测试站点
            test_sites = [
                Site(
                    site_name="北京移动基站001",
                    site_code="BJ-001",
                    site_type="macro",
                    address="北京市朝阳区三里屯街道",
                    latitude=39.936404,
                    longitude=116.443303,
                    status="operational",
                    operator="中国移动",
                    frequency_band="2.6GHz",
                    technology="5G",
                    coverage_area="商业区",
                    power_supply="市电+备用电池",
                    installation_date="2024-01-15",
                    maintenance_schedule="每月第一周",
                    contact_person="张工程师",
                    contact_phone="13800138001"
                ),
                Site(
                    site_name="上海联通基站002",
                    site_code="SH-002",
                    site_type="micro",
                    address="上海市浦东新区陆家嘴金融区",
                    latitude=31.235929,
                    longitude=121.503009,
                    status="maintenance",
                    operator="中国联通",
                    frequency_band="3.5GHz",
                    technology="5G",
                    coverage_area="商务区",
                    power_supply="市电",
                    installation_date="2024-02-20",
                    maintenance_schedule="双周维护",
                    contact_person="李工程师", 
                    contact_phone="13800138002"
                ),
                Site(
                    site_name="广州电信基站003",
                    site_code="GZ-003",
                    site_type="macro",
                    address="广州市天河区珠江新城",
                    latitude=23.120049,
                    longitude=113.325998,
                    status="operational",
                    operator="中国电信",
                    frequency_band="2.1GHz",
                    technology="4G/5G",
                    coverage_area="住宅区",
                    power_supply="市电+太阳能",
                    installation_date="2023-12-10",
                    maintenance_schedule="每月定期",
                    contact_person="王工程师",
                    contact_phone="13800138003"
                )
            ]
            
            for site in test_sites:
                db.add(site)
            
            db.commit()
            print("✅ 测试站点创建完成")
            print(f"   共创建 {len(test_sites)} 个测试站点")
        else:
            print("ℹ️ 站点已存在，跳过站点创建")
            
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        db.rollback()
    finally:
        db.close()
        
    print("\n🎉 数据库初始化完成！")
    print("\n📖 使用说明:")
    print("1. 启动后端服务: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print("2. 访问API文档: http://localhost:8000/docs")
    print("3. 使用上述账号登录前端应用")

if __name__ == "__main__":
    init_database()