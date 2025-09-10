#!/usr/bin/env python3
"""
检查站点分配情况
"""

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.site import Site
from app.models.user import User

def check_site_assignments():
    """检查站点分配情况"""
    print("正在检查站点分配情况...")
    
    # 创建数据库会话
    db = next(get_db())
    
    try:
        # 查询所有站点
        sites = db.query(Site).all()
        
        print(f"共有 {len(sites)} 个站点:")
        for site in sites:
            assigned_user_name = "未分配"
            if site.assigned_to:
                assigned_user = db.query(User).filter(User.id == site.assigned_to).first()
                if assigned_user:
                    assigned_user_name = assigned_user.username
            
            print(f"  {site.site_name} ({site.site_code})")
            print(f"    状态: {site.status}")
            print(f"    分配给: {assigned_user_name}")
            print()
            
    except Exception as e:
        print(f"❌ 检查失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_site_assignments()