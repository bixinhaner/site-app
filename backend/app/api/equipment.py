from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
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
    EquipmentStatusEnum,
    Inventory,
    SNImportRecord,
    StockTransaction,
    StockTransactionItem,
    TransactionTypeEnum,
    InventoryStatusEnum,
    Warehouse,
    PickupRecord,
)
from app.models.equipment import EquipmentInstance  # noqa: E402
from app.models.work_order import AuditEvent
from app.models.inspection import InspectionCheckItem, CheckItemStatusEnum, SiteInspection
from app.models.site import Site
from app.services.authz_service import user_has_any_role_or_permission
from app.utils.timezone import to_utc_iso

router = APIRouter()


def _ensure_equipment_write_access(current_user: User) -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "warehouse_manager"],
        permission_codes=["inventory:equipment:write"],
    ):
        raise HTTPException(status_code=403, detail="权限不足")


def _ensure_package_write_access(current_user: User) -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager", "warehouse_manager"],
        permission_codes=["inventory:package:write"],
    ):
        raise HTTPException(status_code=403, detail="权限不足")


def _ensure_package_delete_access(current_user: User) -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager"],
        permission_codes=["inventory:package:write"],
    ):
        raise HTTPException(status_code=403, detail="权限不足")

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
            "created_at": to_utc_iso(eq.created_at) if eq.created_at else None
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
    _ensure_equipment_write_access(current_user)
    
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
    _ensure_equipment_write_access(current_user)
    
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
    _ensure_equipment_write_access(current_user)
    
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    
    # 仅无任何引用才允许删除
    reference_reasons = []

    if db.query(EquipmentPackage).filter(EquipmentPackage.main_equipment_id == equipment_id).first():
        reference_reasons.append("被套装作为主设备使用")

    if db.query(EquipmentPackageItem).filter(EquipmentPackageItem.equipment_id == equipment_id).first():
        reference_reasons.append("被套装明细引用")

    if db.query(Inventory).filter(Inventory.equipment_id == equipment_id).first():
        reference_reasons.append("存在库存记录")

    if db.query(EquipmentInstance).filter(EquipmentInstance.equipment_id == equipment_id).first():
        reference_reasons.append("存在设备实例/SN数据")

    if db.query(StockTransactionItem).filter(StockTransactionItem.equipment_id == equipment_id).first():
        reference_reasons.append("存在出入库明细记录")

    if db.query(SNImportRecord).filter(SNImportRecord.equipment_type_id == equipment_id).first():
        reference_reasons.append("存在SN导入记录")

    if reference_reasons:
        raise HTTPException(
            status_code=400,
            detail=f"设备存在引用，无法删除：{'；'.join(reference_reasons)}",
        )
    
    db.delete(equipment)
    db.commit()
    return {"message": "设备型号删除成功"}

# ===== 设备套装管理 =====

def _as_int(value, field_name: str) -> int:
    try:
        return int(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"{field_name} 不合法")


def _normalize_package_items(
    db: Session,
    *,
    main_equipment_id,
    items_data,
    main_equipment_quantity=None,
) -> List[dict]:
    """规范化套装明细：
    - 主设备自动写入明细，数量可配置（默认 1）
    - 明细不允许重复
    - 除主设备外，仅允许添加辅材类设备
    """
    main_id = _as_int(main_equipment_id, "main_equipment_id")
    if not main_id:
        raise HTTPException(status_code=400, detail="主设备不能为空")

    if items_data is None:
        items_data = []
    if not isinstance(items_data, list):
        raise HTTPException(status_code=400, detail="items 格式不正确")

    parsed_items = []
    for idx, raw in enumerate(items_data):
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail=f"items[{idx}] 格式不正确")
        if raw.get("equipment_id") is None:
            raise HTTPException(status_code=400, detail=f"items[{idx}].equipment_id 不能为空")
        equipment_id = _as_int(raw.get("equipment_id"), "equipment_id")
        qty = raw.get("quantity", 1)
        quantity = _as_int(qty, "quantity")
        if quantity <= 0:
            raise HTTPException(status_code=400, detail="数量必须大于 0")
        parsed_items.append(
            {
                "equipment_id": equipment_id,
                "quantity": quantity,
                "is_required": bool(raw.get("is_required", True)),
                "notes": raw.get("notes"),
            }
        )

    seen_ids = set()
    for item in parsed_items:
        equipment_id = item["equipment_id"]
        if equipment_id in seen_ids:
            raise HTTPException(status_code=400, detail="套装明细存在重复设备")
        seen_ids.add(equipment_id)

    all_ids = set(seen_ids)
    all_ids.add(main_id)

    rows = db.query(Equipment.id, Equipment.category).filter(Equipment.id.in_(list(all_ids))).all()
    category_map = {row[0]: row[1] for row in rows}

    missing_ids = [eid for eid in all_ids if eid not in category_map]
    if missing_ids:
        raise HTTPException(status_code=400, detail="套装明细包含不存在的设备")

    if category_map.get(main_id) != EquipmentCategoryEnum.MAIN_DEVICE:
        raise HTTPException(status_code=400, detail="主设备类型不正确")

    for item in parsed_items:
        equipment_id = item["equipment_id"]
        if equipment_id == main_id:
            continue
        if category_map.get(equipment_id) != EquipmentCategoryEnum.AUXILIARY:
            raise HTTPException(status_code=400, detail="套装明细仅允许添加辅材")

    if main_equipment_quantity is not None and str(main_equipment_quantity).strip() != "":
        main_quantity = _as_int(main_equipment_quantity, "main_equipment_quantity")
    else:
        main_quantity = 1
        for item in parsed_items:
            if item["equipment_id"] == main_id:
                main_quantity = int(item["quantity"] or 0)
                break

    if main_quantity <= 0:
        raise HTTPException(status_code=400, detail="主设备数量必须大于 0")

    normalized = [
        {
            "equipment_id": main_id,
            "quantity": int(main_quantity),
            "is_required": True,
            "notes": None,
        }
    ]
    normalized.extend([item for item in parsed_items if item["equipment_id"] != main_id])
    return normalized


@router.get("/packages", response_model=List[dict])
async def get_equipment_packages(
    site_type: Optional[str] = None,
    status: Optional[str] = Query(None, description="状态过滤: active/inactive/discontinued"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取设备套装列表"""
    query = db.query(EquipmentPackage)  # 默认显示全部，可按状态筛选
    
    if site_type:
        query = query.filter(EquipmentPackage.site_type == site_type)
    if status:
        status_value = str(status).strip().lower()
        try:
            status_enum = EquipmentStatusEnum(status_value)
        except ValueError:
            raise HTTPException(status_code=400, detail="status 参数不合法")
        query = query.filter(EquipmentPackage.status == status_enum)
    
    packages = query.offset(skip).limit(limit).all()
    
    result = []
    for package in packages:
        # 获取套装明细
        items = []
        main_equipment_quantity = 1
        for item in package.package_items:
            if int(item.equipment_id) == int(package.main_equipment_id):
                main_equipment_quantity = int(item.quantity or 0) or 1
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
            "main_equipment_quantity": int(main_equipment_quantity),
            "site_type": package.site_type,
            "description": package.description,
            "status": package.status,  # 添加状态字段
            "items": items,
            "created_at": to_utc_iso(package.created_at) if package.created_at else None
        })
    
    return result

@router.post("/packages")
async def create_equipment_package(
    package_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建设备套装"""
    _ensure_package_write_access(current_user)
    
    # 检查套装编码是否重复
    existing = db.query(EquipmentPackage).filter(EquipmentPackage.package_code == package_data["package_code"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="套装编码已存在")
    
    # 创建套装
    main_equipment_id = _as_int(package_data.get("main_equipment_id"), "main_equipment_id")
    normalized_items = _normalize_package_items(
        db,
        main_equipment_id=main_equipment_id,
        items_data=package_data.get("items", []),
        main_equipment_quantity=package_data.get("main_equipment_quantity"),
    )

    package = EquipmentPackage(
        package_code=package_data["package_code"],
        package_name=package_data["package_name"],
        main_equipment_id=main_equipment_id,
        site_type=package_data.get("site_type"),
        description=package_data.get("description"),
        created_by=current_user.id
    )
    
    db.add(package)
    db.flush()  # 获取package.id
    
    # 创建套装明细
    for item_data in normalized_items:
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
    main_equipment_quantity = 1
    for item in package.package_items:
        if int(item.equipment_id) == int(package.main_equipment_id):
            main_equipment_quantity = int(item.quantity or 0) or 1
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
        "main_equipment_quantity": int(main_equipment_quantity),
        "site_type": package.site_type,
        "description": package.description,
        "items": items,
        "created_at": to_utc_iso(package.created_at) if package.created_at else None
    }

@router.put("/packages/{package_id}")
async def update_equipment_package(
    package_id: int,
    package_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新设备套装"""
    _ensure_package_write_access(current_user)
    
    package = db.query(EquipmentPackage).filter(EquipmentPackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="套装不存在")

    need_normalize_items = "items" in package_data or "main_equipment_id" in package_data
    normalized_items = None
    if need_normalize_items:
        items_data = package_data.get("items")
        if items_data is None:
            items_data = [
                {
                    "equipment_id": it.equipment_id,
                    "quantity": it.quantity,
                    "is_required": it.is_required,
                    "notes": it.notes,
                }
                for it in package.package_items
            ]
        main_equipment_id = package_data.get("main_equipment_id", package.main_equipment_id)
        normalized_items = _normalize_package_items(
            db,
            main_equipment_id=main_equipment_id,
            items_data=items_data,
            main_equipment_quantity=package_data.get("main_equipment_quantity"),
        )

    # 更新基本信息
    for key in ["package_name", "main_equipment_id", "site_type", "description", "status"]:
        if key in package_data:
            if key == "main_equipment_id":
                setattr(package, key, _as_int(package_data[key], "main_equipment_id"))
            else:
                setattr(package, key, package_data[key])
    
    # 更新套装明细
    if need_normalize_items:
        # 删除旧的明细
        db.query(EquipmentPackageItem).filter(EquipmentPackageItem.package_id == package_id).delete()
        
        # 添加新的明细
        for item_data in (normalized_items or []):
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
    _ensure_package_delete_access(current_user)
    
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
        main_equipment_quantity = 1
        for item in package.package_items:
            if int(item.equipment_id) == int(package.main_equipment_id):
                main_equipment_quantity = int(item.quantity or 0) or 1
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
            "main_equipment_id": package.main_equipment_id,
            "main_equipment_quantity": int(main_equipment_quantity),
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


@router.get("/instances/search")
async def search_equipment_instance(
    serial_number: str = Query(..., description="设备序列号SN"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """根据 SN 查询单台设备实例的基础信息。

    返回字段与前端设备生命周期视图使用保持一致，便于直接展示。
    """
    sn = (serial_number or "").strip()
    if not sn:
        raise HTTPException(status_code=400, detail="serial_number 不能为空")

    instance = db.query(EquipmentInstance).filter(EquipmentInstance.serial_number == sn).first()
    if not instance:
        raise HTTPException(status_code=404, detail="设备实例不存在")

    equipment = instance.equipment
    issuer = instance.issuer
    warehouse = instance.warehouse

    current_warehouse_id = instance.warehouse_id
    current_warehouse_name = warehouse.warehouse_name if warehouse else None

    stock_in_warehouse_id = None
    stock_in_warehouse_name = None

    stock_in_row = (
        db.query(StockTransaction.warehouse_id, Warehouse.warehouse_name)
        .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
        .join(Warehouse, Warehouse.id == StockTransaction.warehouse_id)
        .filter(
            StockTransactionItem.equipment_instance_id == instance.id,
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_IN,
        )
        .order_by(StockTransaction.operation_time.asc())
        .first()
    )
    if stock_in_row:
        stock_in_warehouse_id, stock_in_warehouse_name = stock_in_row

    last_warehouse_id = current_warehouse_id
    last_warehouse_name = current_warehouse_name

    if last_warehouse_id is None:
        pickup_row = (
            db.query(StockTransaction.warehouse_id, Warehouse.warehouse_name)
            .join(PickupRecord, PickupRecord.transaction_id == StockTransaction.id)
            .join(Warehouse, Warehouse.id == StockTransaction.warehouse_id)
            .filter(PickupRecord.equipment_instance_id == instance.id)
            .order_by(PickupRecord.pickup_time.desc())
            .first()
        )
        if pickup_row:
            last_warehouse_id, last_warehouse_name = pickup_row

    if stock_in_warehouse_id is None:
        stock_in_warehouse_id = current_warehouse_id or last_warehouse_id
        stock_in_warehouse_name = current_warehouse_name or last_warehouse_name

    return {
        "id": instance.id,
        "serial_number": instance.serial_number,
        "barcode": instance.barcode,
        "status": instance.status,
        "vendor": instance.vendor,
        "equipment_id": equipment.id if equipment else None,
        "equipment_name": equipment.equipment_name if equipment else None,
        "equipment_code": equipment.equipment_code if equipment else None,
        "warehouse_id": current_warehouse_id,
        "warehouse_name": current_warehouse_name,
        "stock_in_warehouse_id": stock_in_warehouse_id,
        "stock_in_warehouse_name": stock_in_warehouse_name,
        "last_warehouse_id": last_warehouse_id,
        "last_warehouse_name": last_warehouse_name,
        # issued_date 历史上使用 datetime.now()（本地时间）写入，这里按本地时间换算到 UTC
        "issued_at": to_utc_iso(instance.issued_date, assume_local=True) if instance.issued_date else None,
        "issued_to": issuer.id if issuer else None,
        "issued_to_name": (issuer.full_name or issuer.username) if issuer else None,
        # created_at / updated_at 多数来源于数据库 CURRENT_TIMESTAMP 或 utcnow，视为 UTC
        "created_at": to_utc_iso(instance.created_at) if instance.created_at else None,
        "updated_at": to_utc_iso(instance.updated_at) if instance.updated_at else None,
    }


@router.get("/instances/{serial_number}/lifecycle-events")
async def get_equipment_instance_lifecycle_events(
    serial_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取设备实例生命周期事件列表（用于“设备生命周期追踪”时间线）。

    说明：
    - 事件以 action + operated_at 的形式返回，前端按 action 渲染为不同阶段
    - 兼容保留已有绑定历史与 OMC 首次上线/激活事件
    """
    sn = (serial_number or "").strip()
    if not sn:
        raise HTTPException(status_code=400, detail="serial_number 不能为空")

    # 复用现有搜索接口的数据结构，保证前端展示字段一致
    equipment_info = await search_equipment_instance(serial_number=sn, db=db, current_user=current_user)
    instance_id = equipment_info.get("id")

    events: List[Dict[str, Any]] = []

    def _mk_event(
        *,
        action: str,
        operated_at: str,
        operator_id: Optional[int] = None,
        operator_name: str = "系统",
        notes: Optional[str] = None,
        details: Optional[dict] = None,
        inspection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "id": f"{action}-{uuid.uuid4().hex[:12]}",
            "action": action,
            "site": None,
            "cell_info": {},
            "operator": {"id": operator_id, "name": operator_name},
            "operated_at": operated_at,
            "previous_equipment_sn": None,
            "latitude": None,
            "longitude": None,
            "gps_accuracy": None,
            "notes": notes,
            "inspection_id": inspection_id,
            "details": details or {},
        }

    # 1) 入库/出库（来自 equipment_instances）
    if equipment_info.get("created_at"):
        events.append(
            _mk_event(
                action="stock_in",
                operated_at=str(equipment_info["created_at"]),
                notes="设备已录入系统，完成入库登记",
                details={
                    "设备SN": equipment_info.get("serial_number"),
                    "条码": equipment_info.get("barcode") or "-",
                    "供应商": equipment_info.get("vendor") or "-",
                    "仓库": equipment_info.get("stock_in_warehouse_name")
                    or equipment_info.get("warehouse_name")
                    or equipment_info.get("last_warehouse_name")
                    or "-",
                },
            )
        )

    if equipment_info.get("issued_at"):
        events.append(
            _mk_event(
                action="stock_out",
                operated_at=str(equipment_info["issued_at"]),
                operator_name=equipment_info.get("issued_to_name") or "系统",
                notes="设备已出库",
                details={
                    "领料人": equipment_info.get("issued_to_name") or "-",
                },
            )
        )

    # 2) 绑定历史 + OMC 首次上线/激活（复用既有接口的输出结构）
    try:
        from app.api.inspections import get_equipment_binding_history  # 避免循环依赖

        history_res = await get_equipment_binding_history(equipment_sn=sn, db=db, current_user=current_user)
        raw_history = (history_res or {}).get("history") or []
        if isinstance(raw_history, list):
            events.extend(raw_history)
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] 加载绑定历史失败: {exc}")

    # 3) 检查完成（补齐 inspected 对应事件）
    try:
        row = (
            db.query(InspectionCheckItem, SiteInspection, Site, User)
            .join(SiteInspection, InspectionCheckItem.inspection_id == SiteInspection.id)
            .join(Site, SiteInspection.site_id == Site.id)
            .outerjoin(User, InspectionCheckItem.checked_by == User.id)
            .filter(
                InspectionCheckItem.equipment_sn == sn,
                InspectionCheckItem.status == CheckItemStatusEnum.COMPLETED,
                InspectionCheckItem.checked_at.isnot(None),
            )
            .order_by(InspectionCheckItem.checked_at.desc())
            .first()
        )
        if row:
            item, inspection, site, checker = row
            operated_at = to_utc_iso(item.checked_at)
            if operated_at:
                events.append(
                    _mk_event(
                        action="inspection_completed",
                        operated_at=operated_at,
                        operator_id=getattr(checker, "id", None),
                        operator_name=(getattr(checker, "full_name", None) or getattr(checker, "username", None) or "检查人员"),
                        notes="检查项已完成，设备状态更新为“已检查”",
                        inspection_id=getattr(inspection, "id", None),
                        details={
                            "站点": getattr(site, "site_name", None) or "未知站点",
                            "检查ID": getattr(inspection, "id", None),
                            "检查项": getattr(item, "item_name", None) or "-",
                        },
                    )
                )
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] 附加检查完成事件失败: {exc}")

    # 4) 退库事件（补齐 return_pending_receive 对应事件）
    try:
        if instance_id:
            return_rows = (
                db.query(StockTransaction, Warehouse, User)
                .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
                .join(Warehouse, Warehouse.id == StockTransaction.warehouse_id)
                .join(User, User.id == StockTransaction.operator_id)
                .filter(
                    StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                    StockTransactionItem.equipment_instance_id == instance_id,
                )
                .order_by(StockTransaction.created_at.desc())
                .all()
            )
            for trans, wh, operator in return_rows:
                approval_status = (getattr(trans, "approval_status", None) or "").strip()
                if approval_status == "pending_receive":
                    operated_at = to_utc_iso(getattr(trans, "scan_time", None), assume_local=True)
                    if operated_at:
                        events.append(
                            _mk_event(
                                action="return_requested",
                                operated_at=operated_at,
                                operator_id=getattr(operator, "id", None),
                                operator_name=(getattr(operator, "full_name", None) or getattr(operator, "username", None) or "退库申请人"),
                                notes="退库申请已提交，等待仓库收货确认",
                                details={
                                    "退入仓库": getattr(wh, "warehouse_name", None) or "-",
                                    "退库单号": getattr(trans, "document_number", None) or "-",
                                    "状态": "pending_receive",
                                },
                            )
                        )
                elif approval_status == "received":
                    operated_at = to_utc_iso(getattr(trans, "approved_at", None), assume_local=True) or to_utc_iso(
                        getattr(trans, "updated_at", None), assume_local=True
                    )
                    if operated_at:
                        events.append(
                            _mk_event(
                                action="return_received",
                                operated_at=operated_at,
                                operator_name="仓库",
                                notes="仓库已收货确认，设备已回库",
                                details={
                                    "退入仓库": getattr(wh, "warehouse_name", None) or "-",
                                    "退库单号": getattr(trans, "document_number", None) or "-",
                                    "状态": "received",
                                },
                            )
                        )
                elif approval_status == "rejected":
                    operated_at = to_utc_iso(getattr(trans, "approved_at", None), assume_local=True)
                    if operated_at:
                        events.append(
                            _mk_event(
                                action="return_rejected",
                                operated_at=operated_at,
                                operator_name="仓库",
                                notes="仓库拒收退库申请",
                                details={
                                    "退入仓库": getattr(wh, "warehouse_name", None) or "-",
                                    "退库单号": getattr(trans, "document_number", None) or "-",
                                    "状态": "rejected",
                                    "原因": getattr(trans, "approval_comments", None) or "-",
                                },
                            )
                        )
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] 附加退库事件失败: {exc}")

    # 5) 实例审计事件：撤销入库 / 编辑信息
    try:
        if instance_id:
            audit_rows = (
                db.query(AuditEvent)
                .filter(
                    AuditEvent.resource_type == "equipment_instance",
                    AuditEvent.resource_id == str(instance_id),
                    AuditEvent.action.in_(["void_stock_in", "edit_instance_info", "handover_issued_to"]),
                )
                .order_by(AuditEvent.created_at.desc())
                .all()
            )
            for ev in audit_rows:
                operated_at = to_utc_iso(getattr(ev, "created_at", None))
                if not operated_at:
                    continue
                op_user = getattr(ev, "operator", None)
                op_name = getattr(op_user, "full_name", None) or getattr(op_user, "username", None) or "系统"
                if ev.action == "void_stock_in":
                    events.append(
                        _mk_event(
                            action="void_stock_in",
                            operated_at=operated_at,
                            operator_id=getattr(op_user, "id", None),
                            operator_name=op_name,
                            notes="撤销入库（释放 SN，保留追溯记录）",
                            details=getattr(ev, "details", None) or {},
                        )
                    )
                elif ev.action == "edit_instance_info":
                    events.append(
                        _mk_event(
                            action="edit_instance_info",
                            operated_at=operated_at,
                            operator_id=getattr(op_user, "id", None),
                            operator_name=op_name,
                            notes="编辑设备实例信息",
                            details=getattr(ev, "details", None) or {},
                        )
                    )
                elif ev.action == "handover_issued_to":
                    details = getattr(ev, "details", None) or {}
                    to_user_name = None
                    try:
                        to_user_id = details.get("to_issued_to")
                        if to_user_id:
                            u = db.query(User).filter(User.id == int(to_user_id)).first()
                            if u:
                                to_user_name = u.full_name or u.username
                    except Exception:
                        to_user_name = None

                    note = "设备归属交接"
                    if to_user_name:
                        note = f"设备归属交接给 {to_user_name}"

                    events.append(
                        _mk_event(
                            action="handover_issued_to",
                            operated_at=operated_at,
                            operator_id=getattr(op_user, "id", None),
                            operator_name=op_name,
                            notes=note,
                            details=details,
                        )
                    )
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] 附加审计事件失败: {exc}")

    # 6) damaged(损坏/报损) 的兜底事件：若实例已处于 damaged 状态，则用 updated_at 标记一次
    try:
        instance = db.query(EquipmentInstance).filter(EquipmentInstance.serial_number == sn).first()
        if instance and getattr(instance, "status", None) == InventoryStatusEnum.DAMAGED and getattr(instance, "updated_at", None):
            operated_at = to_utc_iso(getattr(instance, "updated_at", None))
            if operated_at:
                events.append(
                    _mk_event(
                        action="damaged_marked",
                        operated_at=operated_at,
                        notes="设备标记为“损坏/报损”",
                        details={"当前状态": "damaged"},
                    )
                )
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] 附加报损事件失败: {exc}")

    # 按时间倒序，确保时间线顺序正确
    events.sort(key=lambda x: x.get("operated_at") or "", reverse=True)

    return {"equipment": equipment_info, "events": events}
