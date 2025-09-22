#!/usr/bin/env python3
"""
为现有工单的检查项添加照片的脚本
"""
import sys
import os
import uuid
from datetime import datetime, timedelta
import random

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import get_db
from app.models.inspection import InspectionPhoto, InspectionCheckItem
from app.models.work_order import WorkOrder

def update_work_order_photos():
    """为现有工单的检查项添加照片"""
    db = next(get_db())
    
    try:
        # 获取第一个工单及其检查项
        work_order = db.query(WorkOrder).filter(
            WorkOrder.id == "9e8b480c-f2b3-474d-9bb5-37b0a4ebc29b"
        ).first()
        
        if not work_order:
            print("工单不存在")
            return
            
        print(f"工单: {work_order.title}, 检查ID: {work_order.inspection_id}")
        
        # 获取该工单关联检查的检查项
        check_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == work_order.inspection_id
        ).limit(3).all()  # 只处理前3个检查项
        
        if not check_items:
            print("没有找到检查项")
            return
        
        # 清除现有照片
        db.query(InspectionPhoto).filter(
            InspectionPhoto.inspection_id == work_order.inspection_id
        ).delete()
        
        # 为每个检查项创建1-3张测试照片
        for item in check_items:
            photo_count = random.randint(1, 3)
            print(f"为检查项 '{item.item_name}' 创建 {photo_count} 张照片")
            
            for i in range(photo_count):
                photo = InspectionPhoto(
                    id=str(uuid.uuid4()),
                    inspection_id=item.inspection_id,
                    check_item_id=item.id,
                    original_name=f"检查项照片_{i+1}.jpg",
                    file_path=f"uploads/work_orders/{work_order.id}/photo_{item.id}_{i+1}.jpg",
                    file_size=random.randint(100000, 500000),
                    mime_type="image/jpeg",
                    taken_at=datetime.utcnow() - timedelta(hours=random.randint(1, 48)),
                    uploaded_by=1,  # admin用户
                    latitude=39.9042 + random.uniform(-0.1, 0.1),  # 北京附近坐标
                    longitude=116.4074 + random.uniform(-0.1, 0.1),
                    gps_accuracy=random.uniform(1.0, 10.0),
                    address=f"北京市朝阳区测试地址{random.randint(1, 100)}号",
                    has_watermark=True,
                    watermark_data={"text": f"工单:{work_order.title}", "timestamp": datetime.utcnow().isoformat()},
                    hash_value="work_order_hash_" + str(uuid.uuid4())[:8],
                    review_status=random.choice([None, "approved", "pending"])
                )
                
                db.add(photo)
        
        db.commit()
        print("工单照片创建完成！")
        
        # 验证创建结果
        total_photos = db.query(InspectionPhoto).filter(
            InspectionPhoto.inspection_id == work_order.inspection_id
        ).count()
        print(f"该工单检查中总共有 {total_photos} 张照片")
        
    except Exception as e:
        print(f"创建测试数据时出错: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_work_order_photos()