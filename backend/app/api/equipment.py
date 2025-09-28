from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import json
from datetime import datetime

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.equipment import (
    Equipment, 
    EquipmentPackage, 
    EquipmentPackageItem,
    EquipmentCategoryEnum,
    EquipmentStatusEnum
)

router = APIRouter()

# ===== 设备型号管理 =====

@router.get("/", response_model=List[dict])
async def get_equipment_list(
    category: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取设备型号列表"""
    query = db.query(Equipment)
    
    if category:
        query = query.filter(Equipment.category == category)
    if status:
        query = query.filter(Equipment.status == status)
    
    equipment_list = query.offset(skip).limit(limit).all()
    
    return [
        {
            "id": eq.id,
            "equipment_code": eq.equipment_code,
            "equipment_name": eq.equipment_name,
            "category": eq.category,
            "model": eq.model,
            "brand": eq.brand,
            "specifications": eq.specifications,
            "unit": eq.unit,
            "barcode_prefix": eq.barcode_prefix,
            "status": eq.status,
            "created_at": eq.created_at.isoformat() if eq.created_at else None
        }
        for eq in equipment_list
    ]

@router.post("/")
async def create_equipment(
    equipment_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建设备型号"""
    if current_user.role not in ["admin", "warehouse_manager"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
    # 检查设备编码是否重复
    existing = db.query(Equipment).filter(Equipment.equipment_code == equipment_data["equipment_code"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="设备编码已存在")
    
    equipment = Equipment(
        equipment_code=equipment_data["equipment_code"],
        equipment_name=equipment_data["equipment_name"],
        category=equipment_data["category"],
        model=equipment_data.get("model"),
        brand=equipment_data.get("brand"),
        specifications=equipment_data.get("specifications", {}),
        unit=equipment_data.get("unit", "台"),
        barcode_prefix=equipment_data.get("barcode_prefix"),
        description=equipment_data.get("description"),
        created_by=current_user.id
    )
    
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    
    return {"message": "设备型号创建成功", "equipment_id": equipment.id}

@router.put("/{equipment_id}")
async def update_equipment(
    equipment_id: int,
    equipment_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新设备型号"""
    if current_user.role not in ["admin", "warehouse_manager"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    
    # 更新字段
    for key, value in equipment_data.items():
        if hasattr(equipment, key) and key != "id":
            setattr(equipment, key, value)
    
    db.commit()
    return {"message": "设备型号更新成功"}

@router.delete("/{equipment_id}")
async def delete_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除设备型号"""
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    
    # 检查是否有关联的套装或库存
    package_items = db.query(EquipmentPackageItem).filter(EquipmentPackageItem.equipment_id == equipment_id).first()
    if package_items:
        raise HTTPException(status_code=400, detail="设备已在套装中使用，无法删除")
    
    db.delete(equipment)
    db.commit()
    return {"message": "设备型号删除成功"}

# ===== 设备套装管理 =====

@router.get("/packages", response_model=List[dict])
async def get_equipment_packages(
    site_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取设备套装列表"""
    query = db.query(EquipmentPackage)  # 移除状态过滤，显示所有套装
    
    if site_type:
        query = query.filter(EquipmentPackage.site_type == site_type)
    
    packages = query.offset(skip).limit(limit).all()
    
    result = []
    for package in packages:
        # 获取套装明细
        items = []
        for item in package.package_items:
            items.append({
                "equipment_id": item.equipment_id,
                "equipment_name": item.equipment.equipment_name,
                "equipment_code": item.equipment.equipment_code,
                "category": item.equipment.category,
                "quantity": item.quantity,
                "unit": item.equipment.unit,
                "is_required": item.is_required,
                "notes": item.notes
            })
        
        result.append({
            "id": package.id,
            "package_code": package.package_code,
            "package_name": package.package_name,
            "main_equipment_id": package.main_equipment_id,
            "main_equipment_name": package.main_equipment.equipment_name if package.main_equipment else None,
            "site_type": package.site_type,
            "description": package.description,
            "status": package.status,  # 添加状态字段
            "items": items,
            "created_at": package.created_at.isoformat() if package.created_at else None
        })
    
    return result

@router.post("/packages")
async def create_equipment_package(
    package_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建设备套装"""
    if current_user.role not in ["admin", "manager", "warehouse_manager"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
    # 检查套装编码是否重复
    existing = db.query(EquipmentPackage).filter(EquipmentPackage.package_code == package_data["package_code"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="套装编码已存在")
    
    # 创建套装
    package = EquipmentPackage(
        package_code=package_data["package_code"],
        package_name=package_data["package_name"],
        main_equipment_id=package_data["main_equipment_id"],
        site_type=package_data.get("site_type"),
        description=package_data.get("description"),
        created_by=current_user.id
    )
    
    db.add(package)
    db.flush()  # 获取package.id
    
    # 创建套装明细
    items_data = package_data.get("items", [])
    for item_data in items_data:
        package_item = EquipmentPackageItem(
            package_id=package.id,
            equipment_id=item_data["equipment_id"],
            quantity=item_data["quantity"],
            is_required=item_data.get("is_required", True),
            notes=item_data.get("notes")
        )
        db.add(package_item)
    
    db.commit()
    return {"message": "设备套装创建成功", "package_id": package.id}

@router.get("/packages/{package_id}")
async def get_package_detail(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取套装详情"""
    package = db.query(EquipmentPackage).filter(EquipmentPackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="套装不存在")
    
    # 构建套装详情
    items = []
    for item in package.package_items:
        items.append({
            "equipment_id": item.equipment_id,
            "equipment_name": item.equipment.equipment_name,
            "equipment_code": item.equipment.equipment_code,
            "category": item.equipment.category,
            "quantity": item.quantity,
            "unit": item.equipment.unit,
            "is_required": item.is_required,
            "notes": item.notes
        })
    
    return {
        "id": package.id,
        "package_code": package.package_code,
        "package_name": package.package_name,
        "main_equipment": {
            "id": package.main_equipment.id,
            "name": package.main_equipment.equipment_name,
            "code": package.main_equipment.equipment_code
        } if package.main_equipment else None,
        "site_type": package.site_type,
        "description": package.description,
        "items": items,
        "created_at": package.created_at.isoformat() if package.created_at else None
    }

@router.put("/packages/{package_id}")
async def update_equipment_package(
    package_id: int,
    package_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新设备套装"""
    if current_user.role not in ["admin", "manager", "warehouse_manager"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
    package = db.query(EquipmentPackage).filter(EquipmentPackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="套装不存在")
    
    # 更新基本信息
    for key in ["package_name", "main_equipment_id", "site_type", "description", "status"]:
        if key in package_data:
            setattr(package, key, package_data[key])
    
    # 更新套装明细
    if "items" in package_data:
        # 删除旧的明细
        db.query(EquipmentPackageItem).filter(EquipmentPackageItem.package_id == package_id).delete()
        
        # 添加新的明细
        for item_data in package_data["items"]:
            package_item = EquipmentPackageItem(
                package_id=package.id,
                equipment_id=item_data["equipment_id"],
                quantity=item_data["quantity"],
                is_required=item_data.get("is_required", True),
                notes=item_data.get("notes")
            )
            db.add(package_item)
    
    db.commit()
    return {"message": "设备套装更新成功"}

@router.delete("/packages/{package_id}")
async def delete_equipment_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除设备套装"""
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
    package = db.query(EquipmentPackage).filter(EquipmentPackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="套装不存在")
    
    # 检查是否有关联的库存事务
    from app.models.equipment import StockTransaction
    transaction = db.query(StockTransaction).filter(StockTransaction.package_id == package_id).first()
    if transaction:
        raise HTTPException(status_code=400, detail="套装已有出入库记录，无法删除")
    
    # 删除套装明细
    db.query(EquipmentPackageItem).filter(EquipmentPackageItem.package_id == package_id).delete()
    
    # 删除套装
    db.delete(package)
    db.commit()
    
    return {"message": "设备套装删除成功"}

@router.get("/{equipment_code}/barcode-info")
async def get_equipment_by_barcode(
    equipment_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """通过条码获取设备信息（扫码时使用）"""
    from app.models.equipment import EquipmentInstance
    
    print(f"🔍 [后端API] 收到条码查询请求: {equipment_code}")
    print(f"🔍 [后端API] 用户: {current_user.username}")
    
    # 首先通过SN查找设备实例
    print(f"🔍 [后端API] 步骤1: 通过SN查找设备实例")
    equipment_instance = db.query(EquipmentInstance).filter(
        EquipmentInstance.serial_number == equipment_code
    ).first()
    
    print(f"🔍 [后端API] 设备实例查询结果: {equipment_instance}")
    if equipment_instance:
        print(f"🔍 [后端API] 找到设备实例: ID={equipment_instance.id}, SN={equipment_instance.serial_number}")
    
    equipment = None
    
    if equipment_instance:
        # 如果找到设备实例，获取对应的设备型号
        print(f"🔍 [后端API] 步骤2a: 从设备实例获取设备型号")
        equipment = equipment_instance.equipment
        print(f"🔍 [后端API] 从实例获取设备: {equipment.equipment_name if equipment else 'None'}")
    else:
        print(f"🔍 [后端API] 步骤2b: 通过条码前缀匹配设备型号")
        # 通过条码前缀匹配设备型号
        equipment_list = db.query(Equipment).filter(Equipment.barcode_prefix.isnot(None)).all()
        print(f"🔍 [后端API] 查询到{len(equipment_list)}个有条码前缀的设备")
        
        for eq in equipment_list:
            print(f"🔍 [后端API] 检查设备: {eq.equipment_name}, 前缀: {eq.barcode_prefix}")
            if eq.barcode_prefix and equipment_code.startswith(eq.barcode_prefix):
                equipment = eq
                print(f"🔍 [后端API] 匹配成功: {eq.equipment_name}")
                break
        
        if not equipment:
            print(f"🔍 [后端API] 步骤2c: 直接匹配设备编码")
            # 尝试直接匹配设备编码
            equipment = db.query(Equipment).filter(Equipment.equipment_code == equipment_code).first()
            if equipment:
                print(f"🔍 [后端API] 直接匹配成功: {equipment.equipment_name}")
            else:
                print(f"🔍 [后端API] 直接匹配失败")
    
    if not equipment:
        print(f"❌ [后端API] 未找到对应的设备")
        raise HTTPException(status_code=404, detail="未找到对应的设备")
    
    print(f"🔍 [后端API] 步骤3: 查找包含此设备的套装")
    print(f"🔍 [后端API] 设备ID: {equipment.id}, 设备名称: {equipment.equipment_name}")
    
    # 查找包含此设备的套装
    packages = db.query(EquipmentPackage).filter(
        EquipmentPackage.main_equipment_id == equipment.id,
        EquipmentPackage.status == EquipmentStatusEnum.ACTIVE
    ).all()
    
    print(f"🔍 [后端API] 找到{len(packages)}个套装")
    
    package_list = []
    for package in packages:
        print(f"🔍 [后端API] 处理套装: {package.package_name}")
        items = []
        for item in package.package_items:
            items.append({
                "equipment_name": item.equipment.equipment_name,
                "equipment_code": item.equipment.equipment_code,
                "quantity": item.quantity,
                "unit": item.equipment.unit,
                "is_required": item.is_required
            })
        
        package_info = {
            "id": package.id,
            "package_code": package.package_code,
            "package_name": package.package_name,
            "site_type": package.site_type,
            "items": items
        }
        package_list.append(package_info)
        print(f"🔍 [后端API] 套装信息: {package_info}")
    
    result = {
        "equipment": {
            "id": equipment.id,
            "code": equipment.equipment_code,
            "name": equipment.equipment_name,
            "category": equipment.category
        },
        "equipment_instance": {
            "id": equipment_instance.id if equipment_instance else None,
            "serial_number": equipment_instance.serial_number if equipment_instance else None,
            "mac_address": equipment_instance.mac_address if equipment_instance else None,
            "status": equipment_instance.status if equipment_instance else None,
            "warehouse_name": equipment_instance.warehouse.warehouse_name if equipment_instance and equipment_instance.warehouse else None
        } if equipment_instance else None,
        "available_packages": package_list
    }
    
    print(f"✅ [后端API] 返回结果:")
    print(f"✅ [后端API] 设备: {result['equipment']}")
    print(f"✅ [后端API] 设备实例: {result['equipment_instance']}")
    print(f"✅ [后端API] 套装数量: {len(result['available_packages'])}")
    
    return result