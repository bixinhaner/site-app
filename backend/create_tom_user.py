#!/usr/bin/env python3
"""
创建Tom用户脚本
"""

from sqlalchemy.orm import Session
from app.core.database import engine, get_db
from app.models.user import User
from app.core.security import get_password_hash

def create_tom_user():
    """创建Tom用户"""
    print("正在创建Tom用户...")
    
    # 创建数据库会话
    db = next(get_db())
    
    try:
        # 检查Tom用户是否已存在
        existing_user = db.query(User).filter(User.username == "tom").first()
        
        if existing_user:
            print("ℹ️ 用户Tom已存在")
            return
            
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
        
        print("✅ Tom用户创建成功")
        print(f"   用户名: {tom_user.username}")
        print(f"   全名: {tom_user.full_name}")
        print(f"   角色: {tom_user.role}")
        print(f"   部门: {tom_user.department}")
        print(f"   职位: {tom_user.position}")
        print(f"   邮箱: {tom_user.email}")
        print("   密码: tom123456")
        
    except Exception as e:
        print(f"❌ 创建用户失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_tom_user()