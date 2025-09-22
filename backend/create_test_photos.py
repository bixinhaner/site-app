#!/usr/bin/env python3
"""
创建测试照片数据的脚本
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

def create_test_photos():
    """创建测试照片数据"""
    db = next(get_db())
    
    try:
        # 获取一些检查项
        check_items = db.query(InspectionCheckItem).limit(5).all()
        
        if not check_items:
            print("没有找到检查项")
            return
        
        # 为每个检查项创建1-3张测试照片
        for item in check_items:
            photo_count = random.randint(1, 3)
            print(f"为检查项 '{item.item_name}' 创建 {photo_count} 张照片")
            
            for i in range(photo_count):
                photo = InspectionPhoto(
                    id=str(uuid.uuid4()),
                    inspection_id=item.inspection_id,
                    check_item_id=item.id,
                    original_name=f"test_photo_{i+1}.jpg",
                    file_path=f"uploads/test_photos/test_photo_{item.id}_{i+1}.jpg",
                    file_size=random.randint(100000, 500000),
                    mime_type="image/jpeg",
                    taken_at=datetime.utcnow() - timedelta(hours=random.randint(1, 48)),
                    uploaded_by=1,  # admin用户
                    latitude=39.9042 + random.uniform(-0.1, 0.1),  # 北京附近坐标
                    longitude=116.4074 + random.uniform(-0.1, 0.1),
                    gps_accuracy=random.uniform(1.0, 10.0),
                    address=f"北京市测试地址{random.randint(1, 100)}号",
                    has_watermark=True,
                    watermark_data={"text": "Test Photo", "timestamp": datetime.utcnow().isoformat()},
                    hash_value="test_hash_" + str(uuid.uuid4())[:8],
                    review_status=random.choice([None, "approved", "pending"])
                )
                
                db.add(photo)
        
        db.commit()
        print("测试照片创建完成！")
        
        # 验证创建结果
        total_photos = db.query(InspectionPhoto).count()
        print(f"数据库中总共有 {total_photos} 张照片")
        
    except Exception as e:
        print(f"创建测试数据时出错: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_photos()