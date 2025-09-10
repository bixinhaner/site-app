#!/usr/bin/env python3
"""
修复用户密码
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User

def fix_user_passwords():
    """修复用户密码"""
    
    db = SessionLocal()
    
    try:
        # 修复admin用户密码
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            admin_user.hashed_password = get_password_hash("admin123")
            print("✅ admin用户密码设置为: admin123")
        
        # 修复test_user密码
        test_user = db.query(User).filter(User.username == "test_user").first()
        if test_user:
            test_user.hashed_password = get_password_hash("password123")
            print("✅ test_user用户密码设置为: password123")
        
        db.commit()
        print("✅ 用户密码修复完成")
        
        # 验证修复
        from app.core.security import verify_password
        
        admin_user = db.query(User).filter(User.username == "admin").first()
        test_user = db.query(User).filter(User.username == "test_user").first()
        
        admin_ok = verify_password("admin123", admin_user.hashed_password)
        test_ok = verify_password("password123", test_user.hashed_password)
        
        print(f"admin验证: {'✅ 通过' if admin_ok else '❌ 失败'}")
        print(f"test_user验证: {'✅ 通过' if test_ok else '❌ 失败'}")
        
    finally:
        db.close()

if __name__ == "__main__":
    fix_user_passwords()