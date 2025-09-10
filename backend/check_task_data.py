#!/usr/bin/env python3
"""
检查任务数据
"""

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.inspection import TaskAssignment
from app.models.site import Site

def check_task_data():
    """检查任务数据"""
    print("正在检查任务数据...")
    
    # 创建数据库会话
    db = next(get_db())
    
    try:
        # 查询所有任务
        tasks = db.query(TaskAssignment).all()
        
        print(f"共有 {len(tasks)} 个任务:")
        for task in tasks:
            # 获取站点信息
            site_name = "未找到站点"
            if task.site_id:
                site = db.query(Site).filter(Site.id == task.site_id).first()
                if site:
                    site_name = site.site_name
            
            print(f"  任务: {task.task_title}")
            print(f"    站点ID: {task.site_id}")
            print(f"    站点名: {site_name}")
            print(f"    任务状态: {task.status}")
            print(f"    分配给: {task.assigned_to}")
            print()
            
    except Exception as e:
        print(f"❌ 检查失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_task_data()