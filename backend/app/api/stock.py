from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func, case
from typing import List, Optional, Dict
from pydantic import BaseModel
import uuid
from datetime import datetime

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.equipment import (
    Equipment, 
    EquipmentPackage,
    EquipmentInstance,
    Warehouse,
    Inventory,
    StockTransaction,
    StockTransactionItem,
    PickupRecord,
    SNImportRecord,
    SNImportDetail,
    TransactionTypeEnum,
    InventoryStatusEnum,
    EquipmentStatusEnum
)
from app.models.work_order import AuditEvent
from app.models.inspection import InspectionCheckItem, InspectionPhoto, SiteInspection, InspectionStatusEnum, CheckItemStatusEnum
from app.utils.timezone import to_utc_iso

router = APIRouter()


def _ensure_stock_operator(current_user: User) -> None:
    if current_user.role not in ["admin", "warehouse_manager", "manager"]:
        raise HTTPException(status_code=403, detail="权限不足")

def _ensure_warehouse_operator(current_user: User) -> None:
    # 仓库侧操作：仅仓管/管理员（manager 在 get_current_user 中已被视为 admin）
    if current_user.role not in ["admin", "warehouse_manager"]:
        raise HTTPException(status_code=403, detail="权限不足")


def _get_managed_warehouse_ids(db: Session, current_user: User) -> Optional[set]:
    """返回当前用户可管理的仓库ID集合；管理员返回 None 表示全部仓库。"""
    if current_user.role == "admin":
        return None
    ids = db.query(Warehouse.id).filter(Warehouse.manager_id == current_user.id).all()
    return {row[0] for row in ids}


def _add_audit_event(
    db: Session,
    *,
    resource_type: str,
    resource_id: str,
    action: str,
    operator_id: int,
    comments: Optional[str] = None,
    details: Optional[dict] = None,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
) -> None:
    db.add(
        AuditEvent(
            id=uuid.uuid4().hex,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            operator_id=operator_id,
            comments=comments,
            details=details,
        )
    )


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


# Pydantic模型
class SNBatchCheckRequest(BaseModel):
    sn_list: List[str]

# ===== 库存管理 =====

@router.get("/inventory")
async def get_inventory_list(
    warehouse_id: Optional[int] = None,
    equipment_id: Optional[int] = None,
    low_stock_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取库存列表"""
    query = db.query(Inventory).join(Equipment).join(Warehouse)
    
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    if equipment_id:
        query = query.filter(Inventory.equipment_id == equipment_id)
    if low_stock_only:
        query = query.filter(Inventory.current_stock <= Inventory.min_stock)
    
    inventory_list = query.all()
    
    result = []
    for inv in inventory_list:
        result.append({
            "id": inv.id,
            "equipment_id": inv.equipment_id,
            "warehouse_name": inv.warehouse.warehouse_name,
            "warehouse_code": inv.warehouse.warehouse_code,
            "equipment_name": inv.equipment.equipment_name,
            "equipment_code": inv.equipment.equipment_code,
            "category": inv.equipment.category,
            "unit": inv.equipment.unit,
            "current_stock": inv.current_stock,
            "available_stock": inv.available_stock,
            "reserved_stock": inv.reserved_stock,
            "allocated_stock": inv.allocated_stock,
            "min_stock": inv.min_stock,
            "max_stock": inv.max_stock,
            "is_low_stock": inv.current_stock <= inv.min_stock,
            # 库存更新时间来自数据库 CURRENT_TIMESTAMP，按 UTC 输出
            "last_updated_at": to_utc_iso(inv.last_updated_at) if inv.last_updated_at else None
        })
    
    return {"inventory": result}

@router.get("/inventory/dashboard")
async def get_inventory_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """库存看板统计"""
    # 总体统计
    total_items = db.query(func.count(Inventory.id)).scalar()
    low_stock_items = db.query(func.count(Inventory.id)).filter(
        Inventory.current_stock <= Inventory.min_stock
    ).scalar()
    
    # 主设备库存总量
    main_device_total_stock = db.query(func.sum(Inventory.current_stock)).join(Equipment).filter(
        Equipment.category == "main_device"
    ).scalar() or 0
    
    # 主设备类型数量
    main_device_count = db.query(func.count(Inventory.id)).join(Equipment).filter(
        Equipment.category == "main_device"
    ).scalar()
    
    # 辅材库存
    auxiliaries = db.query(Inventory).join(Equipment).filter(
        Equipment.category == "auxiliary"
    ).all()
    
    # 最近出入库
    recent_transactions = db.query(StockTransaction).order_by(
        desc(StockTransaction.operation_time)
    ).limit(10).all()
    
    transactions_data = []
    for trans in recent_transactions:
        transactions_data.append({
            "id": trans.id,
            "type": trans.transaction_type,
            "document_number": trans.document_number,
            "operator_name": trans.operator.full_name if trans.operator else None,
            # 出入库操作时间采用数据库时间，按 UTC 输出
            "operation_time": to_utc_iso(trans.operation_time) if trans.operation_time else None,
            "total_quantity": trans.total_quantity
        })
    
    return {
        "summary": {
            "total_items": total_items,
            "low_stock_items": low_stock_items,
            "main_device_count": main_device_count,
            "main_device_total_stock": main_device_total_stock,
            "auxiliary_count": len(auxiliaries)
        },
        "recent_transactions": transactions_data
    }

# ===== 扫码出库 =====

@router.post("/scan-checkout")
async def scan_equipment_checkout(
    scan_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """扫码出库 - 核心功能"""
    barcode = scan_data.get("barcode")
    parsed_barcode = scan_data.get("parsed_barcode")  # 解析后的条码数据
    work_order_id = scan_data.get("work_order_id")  # 可选的关联工单
    gps_location = scan_data.get("gps_location")
    warehouse_id = scan_data.get("warehouse_id") or 1

    if not barcode:
        raise HTTPException(status_code=400, detail="条码不能为空")

    # 校验仓库存在且启用
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id,
        Warehouse.status == EquipmentStatusEnum.ACTIVE,
    ).first()
    if not warehouse:
        raise HTTPException(status_code=400, detail="仓库不存在或已停用")
    
    # 提取SN和MAC地址信息
    serial_number = None
    mac1 = None
    mac2 = None
    
    if parsed_barcode and parsed_barcode.get("success"):
        serial_number = parsed_barcode.get("sn")
        mac1 = parsed_barcode.get("mac1")
        mac2 = parsed_barcode.get("mac2")
    
    # 使用SN查询设备，如果没有SN则使用原始条码
    search_code = serial_number if serial_number else barcode
    
    # 1. 通过条码查找设备
    equipment = None
    equipment_instance = None
    
    # 首先尝试通过SN查找设备实例
    if serial_number:
        equipment_instance = db.query(EquipmentInstance).filter(
            EquipmentInstance.serial_number == serial_number
        ).first()
        
        if equipment_instance:
            equipment = equipment_instance.equipment

    # 防重复：若已存在未归还的领料记录（当前用户）则返回幂等结果
    if serial_number:
        existing_pickup = db.query(PickupRecord).filter(
            and_(
                PickupRecord.serial_number == serial_number,
                PickupRecord.picker_id == current_user.id,
                PickupRecord.is_returned == False
            )
        ).order_by(desc(PickupRecord.pickup_time)).first()

        if existing_pickup:
            return {
                "action": "already_picked",
                "message": "该设备已完成领料，不可重复领料",
                "transaction_id": existing_pickup.transaction_id,
                "pickup_record_id": existing_pickup.id,
                "serial_number": serial_number,
                "picked_at": to_utc_iso(existing_pickup.pickup_time, assume_local=True) if existing_pickup.pickup_time else None
            }

    # 若设备实例已被他人领料，则禁止重复领料
    if equipment_instance and equipment_instance.issued_to and equipment_instance.issued_to != current_user.id:
        raise HTTPException(status_code=403, detail="设备已被其他用户领料，无法重复领料")

    # 若设备实例存在且仍在仓库中，则要求与所选仓库一致
    if equipment_instance and equipment_instance.warehouse_id is not None and equipment_instance.warehouse_id != warehouse_id:
        raise HTTPException(status_code=400, detail="设备不在所选仓库，无法出库")
    
    # 如果没找到设备实例，尝试通过条码前缀匹配设备型号
    if not equipment:
        equipment_list = db.query(Equipment).filter(Equipment.barcode_prefix.isnot(None)).all()
        for eq in equipment_list:
            if eq.barcode_prefix and search_code.startswith(eq.barcode_prefix):
                equipment = eq
                break
    
    # 如果还没找到，尝试直接匹配设备编码
    if not equipment:
        equipment = db.query(Equipment).filter(Equipment.equipment_code == search_code).first()
    
    if not equipment:
        raise HTTPException(status_code=404, detail="未识别的设备条码")
    
    # 2. 查找包含此设备的套装
    packages = db.query(EquipmentPackage).filter(
        EquipmentPackage.main_equipment_id == equipment.id,
        EquipmentPackage.status == EquipmentStatusEnum.ACTIVE
    ).all()
    
    if not packages:
        raise HTTPException(status_code=404, detail="该设备未配置套装")
    
    # 如果有多个套装，返回供选择
    if len(packages) > 1:
        package_options = []
        for pkg in packages:
            package_options.append({
                "id": pkg.id,
                "package_code": pkg.package_code,
                "package_name": pkg.package_name,
                "site_type": pkg.site_type
            })
        return {
            "action": "select_package",
            "equipment": {
                "code": equipment.equipment_code,
                "name": equipment.equipment_name
            },
            "available_packages": package_options
        }
    
    # 3. 使用第一个套装进行出库
    package = packages[0]

    # 3.1 生成出库明细（兼容历史套装：若明细缺主设备，则运行时补齐）
    checkout_requirements = []
    has_main_item = False
    for item in package.package_items:
        equipment_id = int(item.equipment_id)
        qty = int(item.quantity or 0)
        equipment_instance_id = None
        if equipment_id == package.main_equipment_id:
            has_main_item = True
            qty = 1  # 主设备数量固定为 1
            if equipment_instance and int(getattr(equipment_instance, "equipment_id", 0) or 0) == equipment_id:
                equipment_instance_id = equipment_instance.id
        if qty <= 0:
            continue
        checkout_requirements.append(
            {
                "equipment_id": equipment_id,
                "quantity": qty,
                "equipment_name": item.equipment.equipment_name if item.equipment else None,
                "equipment_code": item.equipment.equipment_code if item.equipment else None,
                "unit": item.equipment.unit if item.equipment else None,
                "equipment_instance_id": equipment_instance_id,
            }
        )

    if not has_main_item:
        checkout_requirements.insert(
            0,
            {
                "equipment_id": int(package.main_equipment_id),
                "quantity": 1,
                "equipment_name": equipment.equipment_name,
                "equipment_code": equipment.equipment_code,
                "unit": equipment.unit,
                "equipment_instance_id": equipment_instance.id if equipment_instance else None,
            },
        )
    
    # 4. 检查库存是否足够
    shortage_items = []
    for item in checkout_requirements:
        inventory = db.query(Inventory).filter(
            and_(
                Inventory.warehouse_id == warehouse_id,
                Inventory.equipment_id == item["equipment_id"],
            )
        ).first()

        required_qty = int(item["quantity"] or 0)
        if (
            not inventory
            or int(inventory.available_stock or 0) < required_qty
            or int(inventory.current_stock or 0) < required_qty
        ):
            shortage_items.append({
                "equipment_name": item.get("equipment_name") or str(item["equipment_id"]),
                "required": required_qty,
                "available": int(inventory.available_stock or 0) if inventory else 0,
                "current_stock": int(inventory.current_stock or 0) if inventory else 0,
            })
    
    if shortage_items:
        return {
            "action": "insufficient_stock",
            "shortage_items": shortage_items
        }
    
    # 5. 执行出库操作
    transaction_id = str(uuid.uuid4())
    document_number = f"OUT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_user.id}"

    transaction_scan_location = {}
    if isinstance(gps_location, dict):
        transaction_scan_location.update(gps_location)
    transaction_scan_location["_stock_flow_version"] = 2
    
    # 创建出库记录
    transaction = StockTransaction(
        id=transaction_id,
        transaction_type=TransactionTypeEnum.STOCK_OUT,
        warehouse_id=warehouse_id,
        work_order_id=work_order_id,
        package_id=package.id,
        operator_id=current_user.id,
        scan_barcode=barcode,
        # 扫描时间使用服务器本地时间记录
        scan_time=datetime.now(),
        scan_location=transaction_scan_location,
        document_number=document_number,
        total_quantity=sum([int(item["quantity"] or 0) for item in checkout_requirements]),
        notes=f"扫码出库 - {package.package_name}"
    )
    db.add(transaction)
    
    # 创建明细和更新库存
    checkout_items = []
    for item in checkout_requirements:
        # 创建出库明细
        transaction_item = StockTransactionItem(
            transaction_id=transaction_id,
            equipment_instance_id=item.get("equipment_instance_id"),
            equipment_id=item["equipment_id"],
            quantity=int(item["quantity"] or 0),
        )
        db.add(transaction_item)
        
        # 更新库存
        inventory = db.query(Inventory).filter(
            Inventory.warehouse_id == warehouse_id,
            Inventory.equipment_id == item["equipment_id"]
        ).first()
        
        if inventory:
            qty = int(item["quantity"] or 0)
            inventory.current_stock -= qty
            inventory.available_stock -= qty
            inventory.allocated_stock += qty
            inventory.last_updated_by = current_user.id
        else:
            raise HTTPException(status_code=400, detail="库存更新失败：未找到库存记录")
        
        checkout_items.append({
            "equipment_name": item.get("equipment_name"),
            "equipment_code": item.get("equipment_code"),
            "quantity": int(item["quantity"] or 0),
            "unit": item.get("unit")
        })
    
    # 创建领料记录（直接设置为已确认状态）
    pickup_record = PickupRecord(
        id=str(uuid.uuid4()),
        transaction_id=transaction_id,
        work_order_id=work_order_id or f"MANUAL-{current_user.id}",  # 使用work_order_id
        package_id=package.id,
        picker_id=current_user.id,
        main_device_barcode=barcode,
        serial_number=serial_number,  # 记录SN
        mac_address_1=mac1,  # 记录MAC1
        mac_address_2=mac2,  # 记录MAC2
        equipment_instance_id=equipment_instance.id if equipment_instance else None,  # 关联设备实例
        scan_location=gps_location,
        is_confirmed=True,  # 直接设置为已确认
        # 确认时间使用服务器本地时间记录
        confirmed_at=datetime.now(),  # 设置确认时间
        confirmation_notes="扫码领料自动确认"  # 添加确认备注
    )
    db.add(pickup_record)

    # 若找到了具体设备实例，则同步实例的出库状态与领料人
    if equipment_instance:
        equipment_instance.status = InventoryStatusEnum.ISSUED
        equipment_instance.issued_to = current_user.id
        equipment_instance.issued_date = datetime.now()
        equipment_instance.warehouse_id = None  # 出库后不再占用仓库库位
        equipment_instance.updated_at = datetime.now()

    db.commit()
    
    return {
        "action": "checkout_success",
        "transaction_id": transaction_id,
        "document_number": document_number,
        "package": {
            "code": package.package_code,
            "name": package.package_name
        },
        "checkout_items": checkout_items,
        # 返回给前端时统一按 UTC 输出
        "pickup_time": to_utc_iso(datetime.now(), assume_local=True)
    }

@router.post("/confirm-pickup")
async def confirm_equipment_pickup(
    pickup_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """确认领料"""
    transaction_id = pickup_data.get("transaction_id")
    confirmation_notes = pickup_data.get("notes", "")
    
    if not transaction_id:
        raise HTTPException(status_code=400, detail="缺少出库单号")
    
    # 查找领料记录
    pickup_record = db.query(PickupRecord).filter(
        and_(
            PickupRecord.transaction_id == transaction_id,
            PickupRecord.picker_id == current_user.id
        )
    ).first()
    
    if not pickup_record:
        raise HTTPException(status_code=404, detail="领料记录不存在")
    
    if pickup_record.is_confirmed:
        raise HTTPException(status_code=400, detail="已确认领料，不能重复操作")
    
    # 确认领料
    pickup_record.is_confirmed = True
    pickup_record.confirmed_at = datetime.now()
    pickup_record.confirmation_notes = confirmation_notes
    
    db.commit()
    
    return {"message": "领料确认成功"}

@router.get("/my-pickups")
async def get_my_pickup_records(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    q: Optional[str] = None,
    pickup_group: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取我的领料记录"""
    allowed_groups = {"picked", "pending_receive", "installed", "returned"}
    if pickup_group and pickup_group not in allowed_groups:
        raise HTTPException(status_code=400, detail="pickup_group 参数不合法")

    try:
        page = int(page or 1)
    except Exception:
        page = 1
    page = max(page, 1)

    try:
        page_size = int(page_size or 20)
    except Exception:
        page_size = 20
    page_size = max(1, min(page_size, 100))

    query = (
        db.query(PickupRecord)
        .options(
            joinedload(PickupRecord.package),
            joinedload(PickupRecord.equipment_instance).joinedload(EquipmentInstance.warehouse),
        )
        .filter(PickupRecord.picker_id == current_user.id)
    )

    dt_start = _parse_iso_datetime(start_date)
    dt_end = _parse_iso_datetime(end_date)
    if dt_start:
        query = query.filter(PickupRecord.pickup_time >= dt_start)
    if dt_end:
        query = query.filter(PickupRecord.pickup_time <= dt_end)

    search = (q or "").strip()
    if search:
        # SN/条码：精确/前缀优先；套装名：模糊
        like_prefix = f"{search}%"
        like_contains = f"%{search}%"
        query = query.join(PickupRecord.package).filter(
            or_(
                PickupRecord.serial_number == search,
                PickupRecord.main_device_barcode == search,
                PickupRecord.serial_number.like(like_prefix),
                PickupRecord.main_device_barcode.like(like_prefix),
                EquipmentPackage.package_name.like(like_contains),
            )
        )

    allow_unbind_status = {
        InspectionStatusEnum.DRAFT,
        InspectionStatusEnum.IN_PROGRESS,
        InspectionStatusEnum.REJECTED,
    }
    lock_status = {
        InspectionStatusEnum.SUBMITTED,
        InspectionStatusEnum.UNDER_REVIEW,
        InspectionStatusEnum.APPROVED,
        InspectionStatusEnum.COMPLETED,
    }

    # ===== 相关状态（用于分组/排序）=====
    return_pending_exists = db.query(StockTransaction.id).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == PickupRecord.transaction_id,
        StockTransaction.approval_status == "pending_receive",
    ).exists()
    return_received_exists = db.query(StockTransaction.id).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == PickupRecord.transaction_id,
        StockTransaction.approval_status == "received",
    ).exists()
    return_reject_or_cancel_exists = db.query(StockTransaction.id).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == PickupRecord.transaction_id,
        StockTransaction.approval_status.in_(["rejected", "canceled"]),
    ).exists()

    device_level_cond = and_(
        InspectionCheckItem.sector_id.isnot(None),
        InspectionCheckItem.band.isnot(None),
        or_(
            InspectionCheckItem.cell_id.is_(None),
            InspectionCheckItem.cell_id
            == (InspectionCheckItem.sector_id + "_" + InspectionCheckItem.band),
        ),
    )

    need_unbind_exists = db.query(InspectionCheckItem.id).join(
        SiteInspection, InspectionCheckItem.inspection_id == SiteInspection.id
    ).filter(
        InspectionCheckItem.equipment_sn == PickupRecord.serial_number,
        device_level_cond,
        SiteInspection.inspector_id == current_user.id,
        SiteInspection.status.in_(list(allow_unbind_status)),
    ).exists()

    installed_locked_exists = db.query(InspectionCheckItem.id).join(
        SiteInspection, InspectionCheckItem.inspection_id == SiteInspection.id
    ).filter(
        InspectionCheckItem.equipment_sn == PickupRecord.serial_number,
        device_level_cond,
        SiteInspection.status.in_(list(lock_status)),
    ).exists()

    # ===== 分组数量（用于前端 Tab 展示；随搜索条件变化）=====
    returned_cond = or_(PickupRecord.is_returned == True, return_received_exists)
    pending_receive_cond = and_(
        PickupRecord.is_returned == False,
        ~return_received_exists,
        return_pending_exists,
    )
    installed_cond = and_(
        PickupRecord.is_returned == False,
        ~return_received_exists,
        ~return_pending_exists,
        installed_locked_exists,
    )
    picked_cond = and_(
        PickupRecord.is_returned == False,
        ~return_received_exists,
        ~return_pending_exists,
        ~installed_locked_exists,
    )

    counts_row = (
        query.order_by(None)
        .with_entities(
            func.sum(case((picked_cond, 1), else_=0)).label("picked"),
            func.sum(case((pending_receive_cond, 1), else_=0)).label("pending_receive"),
            func.sum(case((installed_cond, 1), else_=0)).label("installed"),
            func.sum(case((returned_cond, 1), else_=0)).label("returned"),
        )
        .one()
    )
    group_counts = {
        "picked": int(getattr(counts_row, "picked", 0) or 0),
        "pending_receive": int(getattr(counts_row, "pending_receive", 0) or 0),
        "installed": int(getattr(counts_row, "installed", 0) or 0),
        "returned": int(getattr(counts_row, "returned", 0) or 0),
    }

    # ===== 分组筛选 =====
    if pickup_group == "returned":
        query = query.filter(returned_cond)
        query = query.order_by(desc(PickupRecord.returned_at), desc(PickupRecord.pickup_time))
    elif pickup_group == "pending_receive":
        query = query.filter(pending_receive_cond)
        query = query.order_by(desc(PickupRecord.pickup_time))
    elif pickup_group == "installed":
        query = query.filter(
            installed_cond,
        ).order_by(desc(PickupRecord.pickup_time))
    elif pickup_group == "picked":
        query = query.filter(picked_cond)
        priority = case(
            (return_reject_or_cancel_exists, 2),
            (need_unbind_exists, 1),
            else_=0,
        )
        query = query.order_by(desc(priority), desc(PickupRecord.pickup_time))
    else:
        query = query.order_by(desc(PickupRecord.pickup_time))

    total = query.order_by(None).count()
    offset = (page - 1) * page_size
    records = query.offset(offset).limit(page_size).all()
    has_more = offset + len(records) < total

    # 退库单（方案A）信息：按出库 transaction_id 聚合取最新一条，用于展示“待收货/已收货/拒收/取消”等状态
    related_ids = [r.transaction_id for r in records if r.transaction_id]
    return_trans_map: Dict[str, StockTransaction] = {}
    if related_ids:
        try:
            return_trans = db.query(StockTransaction).filter(
                StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                StockTransaction.related_transaction_id.in_(related_ids),
            ).order_by(desc(StockTransaction.created_at)).all()
            for rt in return_trans:
                key = getattr(rt, "related_transaction_id", None)
                if key and key not in return_trans_map:
                    return_trans_map[key] = rt
        except Exception:
            # 兼容老库/字段缺失等场景：忽略退库信息
            return_trans_map = {}
    
    result = []
    # 仅针对当前页的 SN 聚合检查绑定状态（用于前端分组与标识）
    sns = []
    for r in records:
        sn = (r.serial_number or r.main_device_barcode or "").strip()
        if sn:
            sns.append(sn)
    sns = list({sn for sn in sns if sn})

    need_unbind_sns = set()
    installed_locked_sns = set()
    if sns:
        try:
            installed_locked_rows = (
                db.query(InspectionCheckItem.equipment_sn)
                .join(SiteInspection, InspectionCheckItem.inspection_id == SiteInspection.id)
                .filter(
                    InspectionCheckItem.equipment_sn.in_(sns),
                    device_level_cond,
                    SiteInspection.status.in_(list(lock_status)),
                )
                .distinct()
                .all()
            )
            installed_locked_sns = {row[0] for row in installed_locked_rows if row and row[0]}

            need_unbind_rows = (
                db.query(InspectionCheckItem.equipment_sn)
                .join(SiteInspection, InspectionCheckItem.inspection_id == SiteInspection.id)
                .filter(
                    InspectionCheckItem.equipment_sn.in_(sns),
                    device_level_cond,
                    SiteInspection.inspector_id == current_user.id,
                    SiteInspection.status.in_(list(allow_unbind_status)),
                )
                .distinct()
                .all()
            )
            need_unbind_sns = {row[0] for row in need_unbind_rows if row and row[0]}
        except Exception:
            installed_locked_sns = set()
            need_unbind_sns = set()

    for record in records:
        sn_for_state = (record.serial_number or record.main_device_barcode or "").strip()
        binding_state = "none"
        if sn_for_state and sn_for_state in installed_locked_sns:
            binding_state = "installed_locked"
        elif sn_for_state and sn_for_state in need_unbind_sns:
            binding_state = "need_unbind"

        latest_return = return_trans_map.get(record.transaction_id) if record.transaction_id else None
        latest_return_status = latest_return.approval_status if latest_return else None
        pickup_group_value = "picked"
        if record.is_returned or latest_return_status == "received":
            pickup_group_value = "returned"
        elif latest_return_status == "pending_receive":
            pickup_group_value = "pending_receive"
        elif binding_state == "installed_locked":
            pickup_group_value = "installed"

        result.append({
            "id": record.id,
            "transaction_id": record.transaction_id,
            "package_name": record.package.package_name if record.package else None,
            "main_device_barcode": record.main_device_barcode,
            "serial_number": record.serial_number,
            "mac_address_1": record.mac_address_1,
            "mac_address_2": record.mac_address_2,
            "equipment_instance": {
                "id": record.equipment_instance.id if record.equipment_instance else None,
                "status": record.equipment_instance.status if record.equipment_instance else None,
                "warehouse_name": record.equipment_instance.warehouse.warehouse_name if record.equipment_instance and record.equipment_instance.warehouse else None
            } if record.equipment_instance else None,
            # pickup_time 使用数据库时间（默认 CURRENT_TIMESTAMP），视为 UTC
            "pickup_time": to_utc_iso(record.pickup_time) if record.pickup_time else None,
            "is_confirmed": record.is_confirmed,
            "is_returned": record.is_returned,
            "return_status": latest_return_status,
            "return_document_number": latest_return.document_number if latest_return else None,
            "return_warehouse_id": latest_return.warehouse_id if latest_return else None,
            "return_warehouse_name": (
                latest_return.warehouse.warehouse_name
                if latest_return and latest_return.warehouse
                else None
            ),
            "return_reject_reason": (
                latest_return.approval_comments
                if latest_return and latest_return.approval_status == "rejected"
                else None
            ),
            # returned_at / confirmed_at 使用 datetime.now() 写入，按本地->UTC 输出
            "returned_at": to_utc_iso(record.returned_at, assume_local=True) if record.returned_at else None,
            "confirmed_at": to_utc_iso(record.confirmed_at, assume_local=True) if record.confirmed_at else None,
            "work_order_id": record.work_order_id,
            "pickup_group": pickup_group_value,
            "binding_state": binding_state,
        })
    
    return {
        "pickup_records": result,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_more": has_more,
        "group_counts": group_counts,
    }

# ===== 退库（方案A：申请/收货）=====

def _extract_sn_from_scan(barcode: str, parsed_barcode: Optional[dict]) -> str:
    if parsed_barcode and isinstance(parsed_barcode, dict) and parsed_barcode.get("success"):
        sn = (parsed_barcode.get("sn") or "").strip()
        if sn:
            return sn
    return (barcode or "").strip()


def _is_device_level_check_item(item: InspectionCheckItem) -> bool:
    if not item or not item.sector_id or not item.band:
        return False
    key = f"{item.sector_id}_{item.band}"
    # 防御：若 cell_id 缺失，按“设备级”处理（避免误放开绑定要求）
    if not item.cell_id:
        return True
    return str(item.cell_id) == key


def _get_active_pickup_by_sn(
    db: Session,
    *,
    sn: str,
    current_user: User,
) -> Optional[PickupRecord]:
    q = db.query(PickupRecord).filter(
        PickupRecord.picker_id == current_user.id,
        PickupRecord.is_returned == False,
        or_(PickupRecord.serial_number == sn, PickupRecord.main_device_barcode == sn),
    )
    return q.order_by(desc(PickupRecord.pickup_time)).first()


def _get_blocking_bindings(
    db: Session,
    *,
    sn: str,
    current_user: User,
) -> Dict[str, list]:
    """返回两类绑定：
    - need_unbind: 当前用户且检查状态允许解绑（draft/in_progress/rejected）的设备级绑定
    - blocked: 不能解绑或不属于当前用户的绑定
    """
    q = (
        db.query(InspectionCheckItem)
        .join(SiteInspection, InspectionCheckItem.inspection_id == SiteInspection.id)
        .options(
            joinedload(InspectionCheckItem.inspection).joinedload(SiteInspection.work_order),
            joinedload(InspectionCheckItem.inspection).joinedload(SiteInspection.site),
        )
        .filter(InspectionCheckItem.equipment_sn == sn)
    )
    items: List[InspectionCheckItem] = q.all()

    allow_unbind_status = {
        InspectionStatusEnum.DRAFT,
        InspectionStatusEnum.IN_PROGRESS,
        InspectionStatusEnum.REJECTED,
    }
    block_status = {
        InspectionStatusEnum.SUBMITTED,
        InspectionStatusEnum.UNDER_REVIEW,
        InspectionStatusEnum.APPROVED,
        InspectionStatusEnum.COMPLETED,
    }

    need_unbind = []
    blocked = []

    for it in items:
        if not _is_device_level_check_item(it):
            continue

        insp: SiteInspection = it.inspection
        insp_status = insp.status if hasattr(insp, "status") else None
        work_order = getattr(insp, "work_order", None) if insp else None
        site = getattr(insp, "site", None) if insp else None

        info = {
            "inspection_id": insp.id if insp else None,
            "inspection_status": getattr(insp_status, "value", insp_status),
            "sector_id": it.sector_id,
            "band": it.band,
            "work_order_id": getattr(insp, "work_order_id", None) if insp else None,
            "work_order_title": getattr(work_order, "title", None) if work_order else None,
            "site_id": getattr(insp, "site_id", None) if insp else None,
            "site_name": getattr(site, "site_name", None) if site else None,
        }

        # 不属于当前用户的检查记录：一律阻断（需人工处理）
        if insp and insp.inspector_id != current_user.id:
            info["reason_code"] = "other_inspector"
            info["reason"] = "设备已绑定到其他检查记录，无法自动解绑"
            blocked.append(info)
            continue

        if insp_status in allow_unbind_status:
            need_unbind.append(info)
            continue

        if insp_status in block_status:
            info["reason_code"] = "inspection_locked"
            info["reason"] = "检查已提交/审核中/已完成，禁止解绑"
            blocked.append(info)
            continue

        # 未知状态：保守阻断
        info["reason_code"] = "status_not_supported"
        info["reason"] = "检查状态不支持解绑"
        blocked.append(info)

    return {"need_unbind": need_unbind, "blocked": blocked}


def _clear_check_item_review_fields(check_item: InspectionCheckItem, now: datetime) -> None:
    check_item.review_status = None
    check_item.review_comments = None
    check_item.reviewed_by = None
    check_item.reviewed_at = None
    check_item.updated_at = now


def _safe_remove_upload_file(file_path: Optional[str]) -> None:
    """仅删除 uploads/ 下的文件，避免误删系统文件。"""
    import os

    if not file_path:
        return

    p = str(file_path).strip()
    if not p:
        return

    # 兼容 "./uploads/..."
    if p.startswith("./"):
        p = p[2:]

    if not p.startswith("uploads/"):
        return

    try:
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        return

    # 若为后端生成的水印图，尝试一并删除原图
    if p.endswith("_watermarked.jpg"):
        base = p[: -len("_watermarked.jpg")]
        for ext in (".jpg", ".jpeg", ".png"):
            orig = f"{base}{ext}"
            try:
                if os.path.exists(orig):
                    os.remove(orig)
            except Exception:
                continue


@router.post("/scan-return/unbind")
async def scan_return_unbind(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """一键解绑：仅解绑设备级检查项；允许 draft/in_progress/rejected，且必须属于当前用户。

    同时清空检查项填写内容，并删除对应检查照片（含物理文件）。
    """
    sn = (payload.get("sn") or "").strip()
    if not sn:
        raise HTTPException(status_code=400, detail="缺少SN")

    allow_unbind_status = {
        InspectionStatusEnum.DRAFT,
        InspectionStatusEnum.IN_PROGRESS,
        InspectionStatusEnum.REJECTED,
    }

    q = (
        db.query(InspectionCheckItem)
        .join(SiteInspection, InspectionCheckItem.inspection_id == SiteInspection.id)
        .filter(
            InspectionCheckItem.equipment_sn == sn,
            SiteInspection.inspector_id == current_user.id,
            SiteInspection.status.in_(list(allow_unbind_status)),
        )
    )
    items: List[InspectionCheckItem] = q.all()

    device_items = [it for it in items if _is_device_level_check_item(it)]
    if not device_items:
        return {"message": "无可解绑的设备级检查项", "unbind_count": 0}

    now = datetime.utcnow()

    # 删除照片（先删文件再删DB记录）
    check_item_ids = [it.id for it in device_items]
    photos = db.query(InspectionPhoto).filter(InspectionPhoto.check_item_id.in_(check_item_ids)).all()
    for photo in photos:
        _safe_remove_upload_file(photo.file_path)
        db.delete(photo)

    # 清理检查项内容并解绑
    for it in device_items:
        it.equipment_sn = None
        it.data_value = None
        it.validation_result = None
        it.status = CheckItemStatusEnum.PENDING
        it.checked_by = None
        it.checked_at = None
        _clear_check_item_review_fields(it, now)

    # 设备实例状态回退：pending_inspection/inspected -> issued
    equipment_instance = db.query(EquipmentInstance).filter(EquipmentInstance.serial_number == sn).first()
    if equipment_instance and equipment_instance.status in {
        InventoryStatusEnum.PENDING_INSPECTION,
        InventoryStatusEnum.INSPECTED,
    }:
        equipment_instance.status = InventoryStatusEnum.ISSUED
        equipment_instance.updated_at = now

    db.commit()

    return {"message": "解绑成功", "unbind_count": len(device_items), "deleted_photos": len(photos)}


@router.post("/scan-return/preview")
async def scan_return_preview(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """扫码退库预览：定位活动领料记录（整单），并检查是否存在需解绑的设备级检查绑定。"""
    barcode = payload.get("barcode") or ""
    parsed_barcode = payload.get("parsed_barcode")
    gps_location = payload.get("gps_location")

    sn = _extract_sn_from_scan(barcode, parsed_barcode)
    if not sn:
        raise HTTPException(status_code=400, detail="条码不能为空")

    pickup_record = _get_active_pickup_by_sn(db, sn=sn, current_user=current_user)
    if not pickup_record:
        return {"action": "no_active_pickup", "message": "未找到可退库的领料记录"}

    out_trans = db.query(StockTransaction).filter(StockTransaction.id == pickup_record.transaction_id).first()
    if not out_trans:
        raise HTTPException(status_code=404, detail="出库单不存在")

    existing_return = db.query(StockTransaction).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == out_trans.id,
        StockTransaction.approval_status.in_(["pending_receive", "received"]),
    ).order_by(desc(StockTransaction.created_at)).first()
    if existing_return:
        return {
            "action": "already_requested",
            "message": "已存在退库单，无法重复申请",
            "return_transaction_id": existing_return.id,
            "return_document_number": existing_return.document_number,
            "return_status": existing_return.approval_status,
        }

    bindings = _get_blocking_bindings(db, sn=sn, current_user=current_user)
    if bindings["blocked"]:
        return {
            "action": "unbind_blocked",
            "message": "存在不可解绑的检查绑定，无法发起退库",
            "blocked_bindings": bindings["blocked"],
        }
    if bindings["need_unbind"]:
        return {
            "action": "need_unbind",
            "message": "存在设备级检查绑定，需先解绑并清理检查内容",
            "need_unbind": bindings["need_unbind"],
        }

    items = []
    for item in out_trans.transaction_items:
        items.append(
            {
                "item_id": item.id,
                "equipment_id": item.equipment_id,
                "equipment_name": item.equipment.equipment_name if item.equipment else None,
                "equipment_code": item.equipment.equipment_code if item.equipment else None,
                "equipment_category": item.equipment.category if item.equipment else None,
                "quantity": item.quantity,
                "unit": item.equipment.unit if item.equipment else None,
            }
        )

    return {
        "action": "preview_ok",
        "sn": sn,
        "pickup_record_id": pickup_record.id,
        "out_transaction_id": out_trans.id,
        "out_document_number": out_trans.document_number,
        "out_warehouse_id": out_trans.warehouse_id,
        "items": items,
        "gps_location": gps_location,
    }


@router.post("/scan-return/request")
async def scan_return_request(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """扫码退库申请（待收货）：创建退库单，但不回滚库存；必须先解绑设备级检查项。"""
    barcode = payload.get("barcode") or ""
    parsed_barcode = payload.get("parsed_barcode")
    gps_location = payload.get("gps_location")
    return_warehouse_id = payload.get("return_warehouse_id")
    notes = (payload.get("notes") or "").strip()

    sn = _extract_sn_from_scan(barcode, parsed_barcode)
    if not sn:
        raise HTTPException(status_code=400, detail="条码不能为空")

    if not return_warehouse_id:
        raise HTTPException(status_code=400, detail="请选择退入仓库")

    return_wh = db.query(Warehouse).filter(
        Warehouse.id == return_warehouse_id,
        Warehouse.status == EquipmentStatusEnum.ACTIVE,
    ).first()
    if not return_wh:
        raise HTTPException(status_code=400, detail="退入仓库不存在或已停用")

    pickup_record = _get_active_pickup_by_sn(db, sn=sn, current_user=current_user)
    if not pickup_record:
        raise HTTPException(status_code=404, detail="未找到可退库的领料记录")

    out_trans = db.query(StockTransaction).filter(StockTransaction.id == pickup_record.transaction_id).first()
    if not out_trans:
        raise HTTPException(status_code=404, detail="出库单不存在")

    # 检查是否已有活动退库单
    existing_return = db.query(StockTransaction).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == out_trans.id,
        StockTransaction.approval_status.in_(["pending_receive", "received"]),
    ).order_by(desc(StockTransaction.created_at)).first()
    if existing_return:
        raise HTTPException(status_code=400, detail="已存在退库单，无法重复申请")

    bindings = _get_blocking_bindings(db, sn=sn, current_user=current_user)
    if bindings["blocked"]:
        raise HTTPException(status_code=400, detail="存在不可解绑的检查绑定，无法发起退库")
    if bindings["need_unbind"]:
        raise HTTPException(status_code=400, detail="存在设备级检查绑定，需先解绑并清理检查内容")

    return_transaction_id = str(uuid.uuid4())
    document_number = f"RET-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_user.id}"

    return_trans = StockTransaction(
        id=return_transaction_id,
        transaction_type=TransactionTypeEnum.RETURN,
        warehouse_id=return_warehouse_id,
        operator_id=current_user.id,
        scan_barcode=sn,
        scan_time=datetime.now(),
        scan_location=gps_location,
        document_number=document_number,
        total_quantity=out_trans.total_quantity,
        notes=notes or f"扫码退库申请 - {sn}",
        approval_status="pending_receive",
        related_transaction_id=out_trans.id,
    )
    db.add(return_trans)

    # 复制出库明细（整单退）
    for item in out_trans.transaction_items:
        db.add(
            StockTransactionItem(
                transaction_id=return_transaction_id,
                equipment_instance_id=item.equipment_instance_id,
                equipment_id=item.equipment_id,
                quantity=item.quantity,
                batch_number=item.batch_number,
                vendor=getattr(item, "vendor", None),
                item_notes=getattr(item, "item_notes", None),
            )
        )

    db.commit()

    return {
        "action": "requested",
        "message": "退库申请已提交，等待仓库收货确认",
        "sn": sn,
        "return_transaction_id": return_transaction_id,
        "return_document_number": document_number,
        "return_status": "pending_receive",
        "return_warehouse_id": return_warehouse_id,
        "return_warehouse_name": return_wh.warehouse_name,
    }


@router.post("/scan-return/cancel")
async def scan_return_cancel(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return_transaction_id = payload.get("return_transaction_id")
    reason = (payload.get("reason") or "").strip()

    if not return_transaction_id:
        raise HTTPException(status_code=400, detail="缺少退库单号")

    trans = db.query(StockTransaction).filter(StockTransaction.id == return_transaction_id).first()
    if not trans or trans.transaction_type != TransactionTypeEnum.RETURN:
        raise HTTPException(status_code=404, detail="退库单不存在")
    if trans.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限取消该退库单")
    if trans.approval_status != "pending_receive":
        raise HTTPException(status_code=400, detail="当前状态不可取消")

    trans.approval_status = "canceled"
    if reason:
        trans.approval_comments = reason
    db.commit()

    return {"message": "已取消退库申请", "return_transaction_id": trans.id, "return_status": trans.approval_status}


@router.post("/scan-return/receive")
async def scan_return_receive(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """仓库收货确认：整单回滚库存 + 主设备实例回库 + 标记领料已归还。"""
    _ensure_warehouse_operator(current_user)

    return_transaction_id = payload.get("return_transaction_id")
    sn_input = (payload.get("sn_input") or "").strip()
    receive_notes = (payload.get("receive_notes") or "").strip()

    if not return_transaction_id:
        raise HTTPException(status_code=400, detail="缺少退库单号")
    if not sn_input:
        raise HTTPException(status_code=400, detail="请填写SN用于核验")

    return_trans = db.query(StockTransaction).filter(StockTransaction.id == return_transaction_id).first()
    if not return_trans or return_trans.transaction_type != TransactionTypeEnum.RETURN:
        raise HTTPException(status_code=404, detail="退库单不存在")
    if return_trans.approval_status != "pending_receive":
        raise HTTPException(status_code=400, detail="退库单状态不可收货确认")

    managed_ids = _get_managed_warehouse_ids(db, current_user)
    if managed_ids is not None and return_trans.warehouse_id not in managed_ids:
        raise HTTPException(status_code=403, detail="无权限处理该仓库的退库单")

    if (return_trans.scan_barcode or "").strip() != sn_input:
        raise HTTPException(status_code=400, detail="SN核验失败，无法收货确认")

    out_trans_id = getattr(return_trans, "related_transaction_id", None)
    if not out_trans_id:
        raise HTTPException(status_code=400, detail="缺少关联出库单，无法收货")

    out_trans = db.query(StockTransaction).filter(StockTransaction.id == out_trans_id).first()
    if not out_trans:
        raise HTTPException(status_code=404, detail="关联出库单不存在")

    out_loc = out_trans.scan_location if isinstance(out_trans.scan_location, dict) else {}
    try:
        stock_flow_version = int(out_loc.get("_stock_flow_version", 0) or 0)
    except Exception:
        stock_flow_version = 0
    is_flow_v2 = stock_flow_version == 2

    source_warehouse_id = out_trans.warehouse_id
    target_warehouse_id = return_trans.warehouse_id

    now = datetime.now()

    # 库存回滚（整单）
    for item in return_trans.transaction_items:
        equipment_id = item.equipment_id
        qty = int(item.quantity or 0)
        if qty <= 0:
            continue

        if source_warehouse_id == target_warehouse_id:
            inv = db.query(Inventory).filter(
                and_(Inventory.warehouse_id == source_warehouse_id, Inventory.equipment_id == equipment_id)
            ).first()
            if not inv or inv.allocated_stock < qty:
                raise HTTPException(status_code=400, detail="库存回滚失败：已分配库存不足")
            inv.allocated_stock -= qty
            inv.available_stock += qty
            if is_flow_v2:
                inv.current_stock += qty
            inv.last_updated_by = current_user.id
        else:
            inv_src = db.query(Inventory).filter(
                and_(Inventory.warehouse_id == source_warehouse_id, Inventory.equipment_id == equipment_id)
            ).first()
            if is_flow_v2:
                if not inv_src or inv_src.allocated_stock < qty:
                    raise HTTPException(status_code=400, detail="库存回滚失败：源仓已分配库存不足")
                inv_src.allocated_stock -= qty
            else:
                if not inv_src or inv_src.allocated_stock < qty or inv_src.current_stock < qty:
                    raise HTTPException(status_code=400, detail="库存回滚失败：源仓库存不足")
                inv_src.allocated_stock -= qty
                inv_src.current_stock -= qty
            inv_src.last_updated_by = current_user.id

            inv_tgt = db.query(Inventory).filter(
                and_(Inventory.warehouse_id == target_warehouse_id, Inventory.equipment_id == equipment_id)
            ).first()
            if not inv_tgt:
                inv_tgt = Inventory(
                    warehouse_id=target_warehouse_id,
                    equipment_id=equipment_id,
                    current_stock=0,
                    available_stock=0,
                    reserved_stock=0,
                    allocated_stock=0,
                    last_updated_by=current_user.id,
                )
                db.add(inv_tgt)
                db.flush()
            inv_tgt.current_stock += qty
            inv_tgt.available_stock += qty
            inv_tgt.last_updated_by = current_user.id

    # 主设备实例回库
    equipment_instance = db.query(EquipmentInstance).filter(EquipmentInstance.serial_number == sn_input).first()
    if equipment_instance:
        equipment_instance.status = InventoryStatusEnum.IN_STOCK
        equipment_instance.issued_to = None
        equipment_instance.issued_date = None
        equipment_instance.warehouse_id = target_warehouse_id
        equipment_instance.updated_at = now

    # 标记领料记录已归还（仅收货确认后）
    pickup_record = db.query(PickupRecord).filter(
        PickupRecord.transaction_id == out_trans.id,
        PickupRecord.picker_id == return_trans.operator_id,
        PickupRecord.is_returned == False,
    ).order_by(desc(PickupRecord.pickup_time)).first()
    if pickup_record:
        pickup_record.is_returned = True
        pickup_record.returned_at = now
        pickup_record.return_notes = receive_notes or "仓库已收货确认"

    return_trans.approval_status = "received"
    return_trans.approved_by = current_user.id
    return_trans.approved_at = now
    return_trans.approval_comments = receive_notes
    db.commit()

    return {
        "message": "收货确认成功",
        "return_transaction_id": return_trans.id,
        "return_status": return_trans.approval_status,
    }


@router.post("/scan-return/reject")
async def scan_return_reject(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """仓库拒收：不回滚库存，仅更新退库单状态与原因。"""
    _ensure_warehouse_operator(current_user)

    return_transaction_id = payload.get("return_transaction_id")
    reason = (payload.get("reason") or "").strip()
    if not return_transaction_id:
        raise HTTPException(status_code=400, detail="缺少退库单号")
    if not reason:
        raise HTTPException(status_code=400, detail="请填写拒收原因")

    return_trans = db.query(StockTransaction).filter(StockTransaction.id == return_transaction_id).first()
    if not return_trans or return_trans.transaction_type != TransactionTypeEnum.RETURN:
        raise HTTPException(status_code=404, detail="退库单不存在")
    if return_trans.approval_status != "pending_receive":
        raise HTTPException(status_code=400, detail="退库单状态不可拒收")

    managed_ids = _get_managed_warehouse_ids(db, current_user)
    if managed_ids is not None and return_trans.warehouse_id not in managed_ids:
        raise HTTPException(status_code=403, detail="无权限处理该仓库的退库单")

    now = datetime.now()
    return_trans.approval_status = "rejected"
    return_trans.approved_by = current_user.id
    return_trans.approved_at = now
    return_trans.approval_comments = reason
    db.commit()

    return {
        "message": "已拒收退库申请",
        "return_transaction_id": return_trans.id,
        "return_status": return_trans.approval_status,
    }


@router.get("/return-requests")
async def list_return_requests(
    status_filter: str = "pending_receive",
    warehouse_ids: Optional[str] = None,
    warehouse_id: Optional[int] = None,
    sn: Optional[str] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """退库收货工作台列表：仅仓库侧可用，默认只返回待收货退库单。"""
    _ensure_warehouse_operator(current_user)

    managed_ids = _get_managed_warehouse_ids(db, current_user)

    query = (
        db.query(StockTransaction)
        .join(Warehouse, StockTransaction.warehouse_id == Warehouse.id)
        .join(User, StockTransaction.operator_id == User.id)
        .filter(StockTransaction.transaction_type == TransactionTypeEnum.RETURN)
    )

    if status_filter and status_filter != "all":
        query = query.filter(StockTransaction.approval_status == status_filter)

    if warehouse_id:
        query = query.filter(StockTransaction.warehouse_id == warehouse_id)

    parsed_ids: List[int] = []
    if warehouse_ids:
        for part in str(warehouse_ids).split(","):
            p = part.strip()
            if not p:
                continue
            try:
                parsed_ids.append(int(p))
            except ValueError:
                continue
    if parsed_ids:
        query = query.filter(StockTransaction.warehouse_id.in_(parsed_ids))

    if managed_ids is not None:
        query = query.filter(StockTransaction.warehouse_id.in_(list(managed_ids)))

    if sn:
        query = query.filter(StockTransaction.scan_barcode == sn.strip())

    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                StockTransaction.document_number.like(kw),
                StockTransaction.scan_barcode.like(kw),
                StockTransaction.notes.like(kw),
                StockTransaction.approval_comments.like(kw),
                Warehouse.warehouse_name.like(kw),
                User.full_name.like(kw),
                User.username.like(kw),
            )
        )

    total = query.count()
    records = query.order_by(desc(StockTransaction.created_at)).offset(skip).limit(limit).all()

    related_ids = [getattr(t, "related_transaction_id", None) for t in records if getattr(t, "related_transaction_id", None)]
    out_map: Dict[str, StockTransaction] = {}
    if related_ids:
        outs = db.query(StockTransaction).filter(StockTransaction.id.in_(related_ids)).all()
        out_map = {t.id: t for t in outs}

    result = []
    for trans in records:
        out_trans = out_map.get(getattr(trans, "related_transaction_id", None))

        items = []
        for item in trans.transaction_items:
            items.append(
                {
                    "item_id": item.id,
                    "equipment_id": item.equipment_id,
                    "equipment_name": item.equipment.equipment_name if item.equipment else None,
                    "equipment_code": item.equipment.equipment_code if item.equipment else None,
                    "equipment_category": item.equipment.category if item.equipment else None,
                    "quantity": item.quantity,
                    "unit": item.equipment.unit if item.equipment else None,
                }
            )

        result.append(
            {
                "id": trans.id,
                "document_number": trans.document_number,
                "status": trans.approval_status,
                "reject_reason": trans.approval_comments,
                "warehouse_id": trans.warehouse_id,
                "warehouse_name": trans.warehouse.warehouse_name if trans.warehouse else None,
                "operator_id": trans.operator_id,
                "operator_name": trans.operator.full_name if trans.operator else None,
                "created_at": to_utc_iso(trans.created_at) if trans.created_at else None,
                "operation_time": to_utc_iso(trans.operation_time) if trans.operation_time else None,
                "scan_barcode": trans.scan_barcode,
                "notes": trans.notes,
                "related_transaction_id": getattr(trans, "related_transaction_id", None),
                "out_document_number": out_trans.document_number if out_trans else None,
                "out_warehouse_id": out_trans.warehouse_id if out_trans else None,
                "out_warehouse_name": out_trans.warehouse.warehouse_name if out_trans and out_trans.warehouse else None,
                "items": items,
            }
        )

    return {"records": result, "total": total}


# ===== 归还管理（兼容旧接口：改为提交退库申请）=====

@router.post("/return-pickup")
async def return_equipment_pickup(
    return_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """兼容旧“归还”接口：改为提交退库申请（待仓库收货确认）。

    说明：为避免“在家退库导致仓库不感知”的风险，本接口不再直接回滚库存/回库设备，
    只创建一条 transaction_type=return 的退库单，状态为 pending_receive。
    """
    pickup_record_id: Optional[str] = return_data.get("pickup_record_id")
    serial_number: Optional[str] = return_data.get("serial_number")
    warehouse_id: Optional[int] = return_data.get("warehouse_id")
    notes: str = return_data.get("notes", "")

    if not pickup_record_id and not serial_number:
        raise HTTPException(status_code=400, detail="缺少 pickup_record_id 或 serial_number")

    # 查找活动领料记录（当前用户）
    query = db.query(PickupRecord).filter(
        PickupRecord.picker_id == current_user.id,
        PickupRecord.is_returned == False
    )
    if pickup_record_id:
        query = query.filter(PickupRecord.id == pickup_record_id)
    elif serial_number:
        query = query.filter(PickupRecord.serial_number == serial_number)

    pickup_record = query.order_by(desc(PickupRecord.pickup_time)).first()
    if not pickup_record:
        raise HTTPException(status_code=404, detail="未找到活动的领料记录")

    sn = (pickup_record.serial_number or serial_number or "").strip()
    if not sn:
        raise HTTPException(status_code=400, detail="缺少序列号(SN)，无法发起退库")

    out_trans = db.query(StockTransaction).filter(StockTransaction.id == pickup_record.transaction_id).first()
    if not out_trans:
        raise HTTPException(status_code=404, detail="出库单不存在")

    # 退入仓库：优先用传入值；未传则按原出库仓库（兼容旧客户端）
    return_warehouse_id = warehouse_id or out_trans.warehouse_id
    return_wh = db.query(Warehouse).filter(
        Warehouse.id == return_warehouse_id,
        Warehouse.status == EquipmentStatusEnum.ACTIVE,
    ).first()
    if not return_wh:
        raise HTTPException(status_code=400, detail="退入仓库不存在或已停用")

    existing_return = db.query(StockTransaction).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == out_trans.id,
        StockTransaction.approval_status.in_(["pending_receive", "received"]),
    ).order_by(desc(StockTransaction.created_at)).first()
    if existing_return:
        raise HTTPException(status_code=400, detail="已存在退库单，无法重复申请")

    bindings = _get_blocking_bindings(db, sn=sn, current_user=current_user)
    if bindings["blocked"]:
        raise HTTPException(status_code=400, detail="存在不可解绑的检查绑定，无法发起退库")
    if bindings["need_unbind"]:
        raise HTTPException(status_code=400, detail="存在设备级检查绑定，需先解绑并清理检查内容")

    return_transaction_id = str(uuid.uuid4())
    document_number = f"RET-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_user.id}"

    return_trans = StockTransaction(
        id=return_transaction_id,
        transaction_type=TransactionTypeEnum.RETURN,
        warehouse_id=return_warehouse_id,
        operator_id=current_user.id,
        scan_barcode=sn,
        scan_time=datetime.now(),
        scan_location=return_data.get("gps_location"),
        document_number=document_number,
        total_quantity=out_trans.total_quantity,
        notes=(notes or "").strip() or f"扫码退库申请 - {sn}",
        approval_status="pending_receive",
        related_transaction_id=out_trans.id,
    )
    db.add(return_trans)

    for item in out_trans.transaction_items:
        db.add(
            StockTransactionItem(
                transaction_id=return_transaction_id,
                equipment_instance_id=item.equipment_instance_id,
                equipment_id=item.equipment_id,
                quantity=item.quantity,
                batch_number=item.batch_number,
                vendor=getattr(item, "vendor", None),
                item_notes=getattr(item, "item_notes", None),
            )
        )

    db.commit()

    return {
        "message": "退库申请已提交，等待仓库收货确认",
        "sn": sn,
        "pickup_record_id": pickup_record.id,
        "out_transaction_id": out_trans.id,
        "return_transaction_id": return_transaction_id,
        "return_document_number": document_number,
        "return_status": "pending_receive",
        "return_warehouse_id": return_warehouse_id,
        "return_warehouse_name": return_wh.warehouse_name,
    }

# ===== 入库管理 =====

@router.post("/stock-in")
async def create_stock_in(
    stock_in_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建入库单"""
    _ensure_stock_operator(current_user)
    
    warehouse_id = stock_in_data.get("warehouse_id", 1)  # 默认仓库
    items = stock_in_data.get("items", [])
    
    if not items:
        raise HTTPException(status_code=400, detail="入库明细不能为空")
    
    # 验证主设备必须填写SN
    for item_data in items:
        equipment_id = item_data["equipment_id"]
        equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not equipment:
            raise HTTPException(status_code=404, detail=f"设备ID {equipment_id} 不存在")
        
        # 主设备必须填写SN
        if equipment.category == "main_device":
            serial_number = item_data.get("serial_number", "").strip()
            if not serial_number:
                raise HTTPException(
                    status_code=400, 
                    detail=f"主设备 {equipment.equipment_name} 必须填写序列号(SN)"
                )
            
            # 检查SN是否已存在
            existing_instance = db.query(EquipmentInstance).filter(
                EquipmentInstance.serial_number == serial_number
            ).first()
            if existing_instance:
                raise HTTPException(
                    status_code=400,
                    detail=f"序列号 {serial_number} 已存在"
                )
    
    # 创建入库记录
    transaction_id = str(uuid.uuid4())
    document_number = f"IN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_user.id}"
    
    transaction = StockTransaction(
        id=transaction_id,
        transaction_type=TransactionTypeEnum.STOCK_IN,
        warehouse_id=warehouse_id,
        operator_id=current_user.id,
        document_number=document_number,
        total_quantity=sum([item["quantity"] for item in items]),
        notes=stock_in_data.get("notes", "")
    )
    db.add(transaction)
    
    # 处理入库明细
    for item_data in items:
        equipment_id = item_data["equipment_id"]
        quantity = item_data["quantity"]
        batch_number = item_data.get("batch_number")
        serial_number = item_data.get("serial_number", "").strip()
        
        equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()

        # 主设备：创建设备实例，并与出入库明细关联
        equipment_instance_id = None
        if equipment.category == "main_device":
            equipment_instance_id = str(uuid.uuid4())
            equipment_instance = EquipmentInstance(
                id=equipment_instance_id,
                equipment_id=equipment_id,
                barcode=serial_number,  # 使用SN作为条码
                serial_number=serial_number,
                batch_number=batch_number,
                warehouse_id=warehouse_id,
                status=InventoryStatusEnum.IN_STOCK,
                received_date=datetime.now(),
                received_by=current_user.id
            )
            db.add(equipment_instance)

        # 创建入库明细
        transaction_item = StockTransactionItem(
            transaction_id=transaction_id,
            equipment_id=equipment_id,
            quantity=quantity,
            batch_number=batch_number,
            equipment_instance_id=equipment_instance_id,
        )
        db.add(transaction_item)
        
        # 更新库存统计
        inventory = db.query(Inventory).filter(
            and_(
                Inventory.warehouse_id == warehouse_id,
                Inventory.equipment_id == equipment_id
            )
        ).first()
        
        if inventory:
            inventory.current_stock += quantity
            inventory.available_stock += quantity
            inventory.last_updated_by = current_user.id
        else:
            # 创建新的库存记录
            new_inventory = Inventory(
                warehouse_id=warehouse_id,
                equipment_id=equipment_id,
                current_stock=quantity,
                available_stock=quantity,
                last_updated_by=current_user.id,
            )
            db.add(new_inventory)
            db.flush()
    
    db.commit()
    
    return {
        "message": "入库成功",
        "transaction_id": transaction_id,
        "document_number": document_number
    }

# ===== 出入库记录查询 =====

@router.get("/transactions")
async def get_stock_transactions(
    transaction_type: Optional[str] = None,
    warehouse_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取出入库记录"""
    query = db.query(StockTransaction)
    
    if transaction_type:
        query = query.filter(StockTransaction.transaction_type == transaction_type)
    if warehouse_id:
        query = query.filter(StockTransaction.warehouse_id == warehouse_id)
    if start_date:
        query = query.filter(
            StockTransaction.operation_time >= datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        )
    if end_date:
        query = query.filter(
            StockTransaction.operation_time <= datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        )
    
    # 非管理员只能查看自己的记录
    if current_user.role not in ["admin", "warehouse_manager", "manager"]:
        query = query.filter(StockTransaction.operator_id == current_user.id)
    
    transactions = query.order_by(desc(StockTransaction.operation_time)).offset(skip).limit(limit).all()
    
    result = []
    for trans in transactions:
        # 获取明细
        items = []
        for item in trans.transaction_items:
            instance = item.equipment_instance
            instance_is_voided = bool(getattr(instance, "is_voided", False)) if instance else False
            serial_number = None
            if instance:
                if instance_is_voided and getattr(instance, "original_serial_number", None):
                    serial_number = instance.original_serial_number
                else:
                    serial_number = instance.serial_number
            items.append({
                "item_id": item.id,
                "equipment_id": item.equipment_id,
                "equipment_instance_id": item.equipment_instance_id,
                "equipment_name": item.equipment.equipment_name,
                "equipment_code": item.equipment.equipment_code,
                "equipment_category": item.equipment.category,
                "quantity": item.quantity,
                "unit": item.equipment.unit,
                "serial_number": serial_number,
                "instance_is_voided": instance_is_voided,
                "batch_number": item.batch_number,
                "vendor": item.vendor,
                "item_notes": item.item_notes,
            })
        
        result.append({
            "id": trans.id,
            "document_number": trans.document_number,
            "transaction_type": trans.transaction_type,
            "warehouse_id": trans.warehouse_id,
            "warehouse_name": trans.warehouse.warehouse_name if trans.warehouse else None,
            "operator_name": trans.operator.full_name if trans.operator else None,
            "operation_time": to_utc_iso(trans.operation_time) if trans.operation_time else None,
            "total_quantity": trans.total_quantity,
            "approval_status": trans.approval_status,
            "approval_comments": trans.approval_comments,
            "approved_by": trans.approved_by,
            "approved_at": to_utc_iso(trans.approved_at, assume_local=True) if trans.approved_at else None,
            "scan_barcode": trans.scan_barcode,
            "notes": trans.notes,
            "related_transaction_id": getattr(trans, "related_transaction_id", None),
            "items": items,
            "task_id": None,
            "package_name": trans.package.package_name if trans.package else None
        })
    
    return {"transactions": result, "total": len(result)}

# ===== 仓库管理 =====

@router.get("/warehouses")
async def get_warehouses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取仓库列表"""
    warehouses = db.query(Warehouse).filter(Warehouse.status == EquipmentStatusEnum.ACTIVE).all()
    
    result = []
    for warehouse in warehouses:
        result.append({
            "id": warehouse.id,
            "warehouse_code": warehouse.warehouse_code,
            "warehouse_name": warehouse.warehouse_name,
            "address": warehouse.address,
            "contact_person": warehouse.contact_person,
            "contact_phone": warehouse.contact_phone,
            "manager_id": warehouse.manager_id,
            "manager_name": warehouse.manager.full_name if warehouse.manager else None
        })
    
    return {"warehouses": result}

@router.post("/warehouses")
async def create_warehouse(
    warehouse_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建仓库"""
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
    # 检查仓库编码是否重复
    existing = db.query(Warehouse).filter(Warehouse.warehouse_code == warehouse_data["warehouse_code"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="仓库编码已存在")
    
    warehouse = Warehouse(
        warehouse_code=warehouse_data["warehouse_code"],
        warehouse_name=warehouse_data["warehouse_name"],
        address=warehouse_data.get("address"),
        contact_person=warehouse_data.get("contact_person"),
        contact_phone=warehouse_data.get("contact_phone"),
        manager_id=warehouse_data.get("manager_id")
    )
    
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    
    return {"message": "仓库创建成功", "warehouse_id": warehouse.id}

@router.put("/warehouses/{warehouse_id}")
async def update_warehouse(
    warehouse_id: int,
    warehouse_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新仓库信息"""
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not warehouse:
        raise HTTPException(status_code=404, detail="仓库不存在")
    
    # 如果修改编码，需要检查唯一性
    new_code = warehouse_data.get("warehouse_code")
    if new_code and new_code != warehouse.warehouse_code:
        existing = db.query(Warehouse).filter(Warehouse.warehouse_code == new_code).first()
        if existing:
            raise HTTPException(status_code=400, detail="仓库编码已存在")
        warehouse.warehouse_code = new_code
    
    if "warehouse_name" in warehouse_data:
        warehouse.warehouse_name = warehouse_data["warehouse_name"]
    if "address" in warehouse_data:
        warehouse.address = warehouse_data["address"]
    if "contact_person" in warehouse_data:
        warehouse.contact_person = warehouse_data["contact_person"]
    if "contact_phone" in warehouse_data:
        warehouse.contact_phone = warehouse_data["contact_phone"]
    if "manager_id" in warehouse_data:
        warehouse.manager_id = warehouse_data["manager_id"]
    
    db.commit()
    db.refresh(warehouse)
    
    return {
        "message": "仓库更新成功",
        "warehouse_id": warehouse.id
    }

# ===== SN批量导入管理 =====

@router.post("/import-sn")
async def import_sn_batch(
    file_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量导入SN

    功能：
    - 为每个 SN 创建设备实例 EquipmentInstance
    - 更新/创建 Inventory 库存记录（按 warehouse_id + equipment_type_id 聚合）
    - 生成 SNImportRecord + SNImportDetail 记录导入结果
    - 生成一条 StockTransaction(stock_in) + StockTransactionItem 作为正式入库记录
    """
    import pandas as pd
    import io
    import base64
    from datetime import datetime
    
    _ensure_stock_operator(current_user)
    
    try:
        # 解析上传的文件数据
        file_content = base64.b64decode(file_data["file_content"])
        file_name = file_data["file_name"]
        equipment_type_id = file_data["equipment_type_id"]
        warehouse_id = file_data["warehouse_id"]
        
        # 读取Excel文件
        excel_data = pd.read_excel(io.BytesIO(file_content))
        
        # 创建导入记录
        import_record_id = str(uuid.uuid4())
        import_record = SNImportRecord(
            id=import_record_id,
            file_name=file_name,
            equipment_type_id=equipment_type_id,
            warehouse_id=warehouse_id,
            total_count=len(excel_data),
            import_by=current_user.id,
            status="processing"
        )
        db.add(import_record)
        db.flush()
        
        success_count = 0
        failed_count = 0
        duplicate_count = 0
        import_details = []

        # 用于后续一次性生成出入库记录
        total_import_quantity = 0

        # 逐行处理数据
        for index, row in excel_data.iterrows():
            line_number = index + 2  # Excel行号从2开始（除去表头）

            try:
                # 确保上一轮新增的库存记录已写入数据库，避免 autoflush=False 导致查询不到，产生重复 Inventory
                db.flush()

                serial_number = str(row.get('SN序列号', '')).strip()
                if not serial_number or serial_number == 'nan':
                    raise ValueError("SN序列号不能为空")
                
                # 检查SN是否已存在
                existing = db.query(EquipmentInstance).filter(
                    EquipmentInstance.serial_number == serial_number
                ).first()
                
                if existing:
                    duplicate_count += 1
                    import_detail = SNImportDetail(
                        import_record_id=import_record_id,
                        line_number=line_number,
                        serial_number=serial_number,
                        import_status="duplicate",
                        error_message=f"SN {serial_number} 已存在"
                    )
                    db.add(import_detail)
                    continue
                
                # 解析其他字段（简化版）
                mac_address = str(row.get('MAC地址', '')).strip() if pd.notna(row.get('MAC地址')) else None
                vendor = str(row.get('供应商', '')).strip() if pd.notna(row.get('供应商')) else None
                batch_number = str(row.get('批次号', '')).strip() if pd.notna(row.get('批次号')) else None
                notes = str(row.get('备注', '')).strip() if pd.notna(row.get('备注')) else None
                
                # 处理日期字段
                manufacture_date = None
                warranty_start_date = None
                warranty_end_date = None
                
                if pd.notna(row.get('生产日期')):
                    manufacture_date = pd.to_datetime(row.get('生产日期')).date()
                if pd.notna(row.get('保修开始日期')):
                    warranty_start_date = pd.to_datetime(row.get('保修开始日期')).date()
                if pd.notna(row.get('保修截止日期')):
                    warranty_end_date = pd.to_datetime(row.get('保修截止日期')).date()
                
                # 创建设备实例（简化版）
                equipment_instance_id = str(uuid.uuid4())
                equipment_instance = EquipmentInstance(
                    id=equipment_instance_id,
                    equipment_id=equipment_type_id,
                    barcode=serial_number,  # 使用SN作为条码
                    serial_number=serial_number,
                    batch_number=batch_number,
                    mac_address=mac_address,
                    manufacture_date=manufacture_date,
                    warranty_start_date=warranty_start_date,
                    warranty_end_date=warranty_end_date,
                    vendor=vendor,
                    warehouse_id=warehouse_id,
                    status=InventoryStatusEnum.IN_STOCK
                )
                db.add(equipment_instance)
                
                # 创建导入明细（简化版）
                import_detail = SNImportDetail(
                    import_record_id=import_record_id,
                    line_number=line_number,
                    serial_number=serial_number,
                    mac_address=mac_address,
                    manufacture_date=manufacture_date,
                    warranty_start_date=warranty_start_date,
                    warranty_end_date=warranty_end_date,
                    vendor=vendor,
                    batch_number=batch_number,
                    import_status="success",
                    equipment_instance_id=equipment_instance_id
                )
                db.add(import_detail)
                
                success_count += 1
                total_import_quantity += 1

                # 更新库存统计（确保同一仓库+设备只有一条库存记录）
                inventories = db.query(Inventory).filter(
                    and_(
                        Inventory.warehouse_id == warehouse_id,
                        Inventory.equipment_id == equipment_type_id
                    )
                ).all()

                if inventories:
                    # 将多条记录合并到第一条，避免产生重复 Inventory
                    main_inv = inventories[0]
                    if len(inventories) > 1:
                        for extra in inventories[1:]:
                            main_inv.current_stock = (main_inv.current_stock or 0) + (extra.current_stock or 0)
                            main_inv.available_stock = (main_inv.available_stock or 0) + (extra.available_stock or 0)
                            main_inv.reserved_stock = (main_inv.reserved_stock or 0) + (extra.reserved_stock or 0)
                            main_inv.allocated_stock = (main_inv.allocated_stock or 0) + (extra.allocated_stock or 0)
                            db.delete(extra)
                    # 然后再加上本次导入的 1 台
                    main_inv.current_stock = (main_inv.current_stock or 0) + 1
                    main_inv.available_stock = (main_inv.available_stock or 0) + 1
                    main_inv.last_updated_by = current_user.id
                else:
                    new_inventory = Inventory(
                        warehouse_id=warehouse_id,
                        equipment_id=equipment_type_id,
                        current_stock=1,
                        available_stock=1,
                        last_updated_by=current_user.id
                    )
                    db.add(new_inventory)
                    db.flush()  # 立即落库，后续循环能命中，避免重复新增
                    
            except Exception as e:
                failed_count += 1
                import_detail = SNImportDetail(
                    import_record_id=import_record_id,
                    line_number=line_number,
                    serial_number=serial_number if 'serial_number' in locals() else '',
                    import_status="failed",
                    error_message=str(e)
                )
                db.add(import_detail)
        
        # 更新导入记录统计
        import_record.success_count = success_count
        import_record.failed_count = failed_count
        import_record.duplicate_count = duplicate_count
        import_record.status = "completed"

        # 如果有成功导入的 SN，生成正式入库记录（出入库记录）
        if success_count > 0:
            transaction_id = str(uuid.uuid4())
            document_number = f"SNIN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_user.id}"

            stock_in_trans = StockTransaction(
                id=transaction_id,
                transaction_type=TransactionTypeEnum.STOCK_IN,
                warehouse_id=warehouse_id,
                operator_id=current_user.id,
                document_number=document_number,
                total_quantity=total_import_quantity,
                notes=f"SN批量导入 - {file_name}",
            )
            db.add(stock_in_trans)

            trans_item = StockTransactionItem(
                transaction_id=transaction_id,
                equipment_id=equipment_type_id,
                quantity=total_import_quantity,
            )
            db.add(trans_item)

        db.commit()
        
        return {
            "message": "导入完成",
            "import_record_id": import_record_id,
            "total_count": len(excel_data),
            "success_count": success_count,
            "failed_count": failed_count,
            "duplicate_count": duplicate_count
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"导入失败: {str(e)}")

@router.get("/import-template")
async def download_import_template():
    """下载SN导入模板"""
    import pandas as pd
    import io
    from fastapi.responses import StreamingResponse
    
    # 创建简化版模板数据
    template_data = {
        'SN序列号': [
            '1203000079204TP1265',
            '120200080724CJD0091', 
            '1122000007256CB0015'
        ],
        'MAC地址': [
            'AA:BB:CC:DD:EE:01',
            'BB:CC:DD:EE:FF:02',
            ''
        ],
        '生产日期': [
            '2024-01-15',
            '2024-02-20',
            '2024-03-10'
        ],
        '保修开始日期': [
            '2024-01-15',
            '2024-02-20',
            '2024-03-10'
        ],
        '保修截止日期': [
            '2025-01-15',
            '2025-02-20',
            '2025-03-10'
        ],
        '供应商': [
            '华为',
            '中兴',
            '大唐'
        ],
        '批次号': [
            'BATCH2024001',
            'BATCH2024002',
            'BATCH2024003'
        ],
        '备注': ['', '', '']
    }
    
    df = pd.DataFrame(template_data)
    
    # 创建Excel文件
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='SN导入模板')
        
        # 获取工作表并设置列宽
        worksheet = writer.sheets['SN导入模板']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''SN%E5%AF%BC%E5%85%A5%E6%A8%A1%E6%9D%BF.xlsx"}
    )

@router.get("/import-history")
async def get_import_history(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取导入历史记录"""
    records = db.query(SNImportRecord).order_by(
        desc(SNImportRecord.import_date)
    ).offset(skip).limit(limit).all()
    
    result = []
    for record in records:
        result.append({
            "id": record.id,
            "file_name": record.file_name,
            "import_date": to_utc_iso(record.import_date) if record.import_date else None,
            "equipment_type_name": record.equipment_type.equipment_name if record.equipment_type else None,
            "warehouse_name": record.warehouse.warehouse_name if record.warehouse else None,
            "total_count": record.total_count,
            "success_count": record.success_count,
            "failed_count": record.failed_count,
            "duplicate_count": record.duplicate_count,
            "status": record.status,
            "importer_name": record.importer.full_name if record.importer else None
        })
    
    return {"records": result}

@router.get("/import-history/{import_id}/details")
async def get_import_details(
    import_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取导入详情"""
    details = db.query(SNImportDetail).filter(
        SNImportDetail.import_record_id == import_id
    ).order_by(SNImportDetail.line_number).all()
    
    result = []
    for detail in details:
        instance_is_voided = bool(getattr(detail.equipment_instance, "is_voided", False)) if detail.equipment_instance else False
        result.append({
            "line_number": detail.line_number,
            "serial_number": detail.serial_number,
            "mac_address": detail.mac_address,
            "imei": detail.imei,
            "firmware_version": detail.firmware_version,
            "hardware_version": detail.hardware_version,
            "vendor": detail.vendor,
            "batch_number": detail.batch_number,
            "import_status": detail.import_status,
            "error_message": detail.error_message,
            "equipment_instance_id": detail.equipment_instance_id,
            "instance_is_voided": instance_is_voided,
        })
    
    return {"details": result}

@router.get("/validate-sn/{serial_number}")
async def validate_sn(
    serial_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """验证SN是否已存在"""
    existing = db.query(EquipmentInstance).filter(
        EquipmentInstance.serial_number == serial_number
    ).first()
    
    return {
        "exists": existing is not None,
        "message": f"SN {serial_number} 已存在" if existing else f"SN {serial_number} 可用"
    }

@router.post("/check-sn-batch")
async def check_sn_batch(
    request: SNBatchCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量检查SN是否存在"""
    results = []
    
    for sn in request.sn_list:
        if not sn or sn.strip() == "":
            continue
            
        sn = sn.strip()
        existing = db.query(EquipmentInstance).filter(
            EquipmentInstance.serial_number == sn
        ).first()
        
        if existing:
            results.append({
                "sn": sn,
                "exists": True,
                "equipment_name": existing.equipment.equipment_name,
                "equipment_code": existing.equipment.equipment_code,
                "equipment_category": existing.equipment.category,
                "status": existing.status,
                "warehouse_name": existing.warehouse.warehouse_name if existing.warehouse else None,
                "vendor": existing.vendor,
                # 设备实例创建时间来自数据库时间，视为 UTC
                "created_at": to_utc_iso(existing.created_at) if existing.created_at else None
            })
        else:
            results.append({
                "sn": sn,
                "exists": False
            })
    
    return {
        "total_count": len(request.sn_list),
        "existing_count": len([r for r in results if r["exists"]]),
        "available_count": len([r for r in results if not r["exists"]]),
        "results": results
    }

@router.get("/equipment/{equipment_id}/instances")
async def get_equipment_instances(
    equipment_id: int,
    status: Optional[str] = None,
    include_voided: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取设备实例列表"""
    query = (
        db.query(EquipmentInstance)
        .options(joinedload(EquipmentInstance.warehouse))
        .filter(EquipmentInstance.equipment_id == equipment_id)
    )

    if not include_voided:
        query = query.filter(or_(EquipmentInstance.is_voided == False, EquipmentInstance.is_voided.is_(None)))
    
    if status:
        query = query.filter(EquipmentInstance.status == status)
    
    instances = query.order_by(desc(EquipmentInstance.created_at)).all()

    # warehouse_id 为空即视为已出库（或在库外），需回溯上个仓库信息用于前端展示
    out_instance_ids = [inst.id for inst in instances if inst.warehouse_id is None]
    last_warehouse_map = {}
    if out_instance_ids:
        latest_pickup_subq = (
            db.query(
                PickupRecord.equipment_instance_id.label("equipment_instance_id"),
                func.max(PickupRecord.pickup_time).label("last_pickup_time"),
            )
            .filter(PickupRecord.equipment_instance_id.in_(out_instance_ids))
            .group_by(PickupRecord.equipment_instance_id)
            .subquery()
        )

        pickup_rows = (
            db.query(
                PickupRecord.equipment_instance_id,
                StockTransaction.warehouse_id,
                Warehouse.warehouse_name,
            )
            .join(
                latest_pickup_subq,
                and_(
                    PickupRecord.equipment_instance_id == latest_pickup_subq.c.equipment_instance_id,
                    PickupRecord.pickup_time == latest_pickup_subq.c.last_pickup_time,
                ),
            )
            .join(StockTransaction, StockTransaction.id == PickupRecord.transaction_id)
            .join(Warehouse, Warehouse.id == StockTransaction.warehouse_id)
            .all()
        )
        for equipment_instance_id, warehouse_id, warehouse_name in pickup_rows:
            last_warehouse_map[equipment_instance_id] = {
                "warehouse_id": warehouse_id,
                "warehouse_name": warehouse_name,
            }
    
    result = []
    for instance in instances:
        current_warehouse_id = instance.warehouse_id
        current_warehouse_name = instance.warehouse.warehouse_name if instance.warehouse else None

        last_warehouse_id = current_warehouse_id
        last_warehouse_name = current_warehouse_name
        if current_warehouse_id is None:
            last_info = last_warehouse_map.get(instance.id) or {}
            last_warehouse_id = last_info.get("warehouse_id")
            last_warehouse_name = last_info.get("warehouse_name")

        instance_is_voided = bool(getattr(instance, "is_voided", False))
        display_sn = instance.original_serial_number if instance_is_voided and getattr(instance, "original_serial_number", None) else instance.serial_number
        display_barcode = display_sn if instance_is_voided and getattr(instance, "original_serial_number", None) else instance.barcode
        result.append({
            "id": instance.id,
            "serial_number": display_sn,
            "original_serial_number": instance.original_serial_number,
            "is_voided": instance_is_voided,
            # voided_at 由 datetime.now() 写入，按本地->UTC 输出
            "voided_at": to_utc_iso(instance.voided_at, assume_local=True) if instance.voided_at else None,
            "void_reason": instance.void_reason,
            "barcode": display_barcode,
            "mac_address": instance.mac_address,
            "imei": instance.imei,
            "firmware_version": instance.firmware_version,
            "hardware_version": instance.hardware_version,
            # 这些日期字段来源导入文件，多为日期意义，统一视为 UTC
            "manufacture_date": to_utc_iso(instance.manufacture_date) if instance.manufacture_date else None,
            "warranty_start_date": to_utc_iso(instance.warranty_start_date) if instance.warranty_start_date else None,
            "warranty_end_date": to_utc_iso(instance.warranty_end_date) if instance.warranty_end_date else None,
            "vendor": instance.vendor,
            "batch_number": instance.batch_number,
            "quality_status": instance.quality_status,
            "status": instance.status,
            "location": instance.location,
            "warehouse_id": current_warehouse_id,
            "warehouse_name": current_warehouse_name,
            "last_warehouse_id": last_warehouse_id,
            "last_warehouse_name": last_warehouse_name,
            "created_at": to_utc_iso(instance.created_at) if instance.created_at else None
        })
    
    return {"instances": result}


@router.patch("/transactions/{transaction_id}")
async def update_stock_transaction_notes(
    transaction_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑出入库单据备注（需填写原因，用于审计）"""
    _ensure_stock_operator(current_user)

    reason = (payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="请填写修改原因")

    new_notes = payload.get("notes")
    new_notes = "" if new_notes is None else str(new_notes)

    trans = db.query(StockTransaction).filter(StockTransaction.id == transaction_id).first()
    if not trans:
        raise HTTPException(status_code=404, detail="出入库记录不存在")

    old_notes = trans.notes or ""
    trans.notes = new_notes

    _add_audit_event(
        db,
        resource_type="stock_transaction",
        resource_id=transaction_id,
        action="edit_notes",
        operator_id=current_user.id,
        comments=reason,
        details={"from": old_notes, "to": new_notes},
    )

    db.commit()
    return {"message": "备注更新成功"}


@router.patch("/transaction-items/{item_id}")
async def update_stock_transaction_item_info(
    item_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑出入库明细行信息（批次号/供应商/备注等；需填写原因，用于审计）"""
    _ensure_stock_operator(current_user)

    reason = (payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="请填写修改原因")

    item = db.query(StockTransactionItem).filter(StockTransactionItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="出入库明细不存在")

    trans = item.transaction
    if not trans:
        raise HTTPException(status_code=404, detail="关联出入库单不存在")

    old = {
        "batch_number": item.batch_number,
        "vendor": item.vendor,
        "item_notes": item.item_notes,
    }

    if "batch_number" in payload:
        v = payload.get("batch_number")
        item.batch_number = None if v is None or str(v).strip() == "" else str(v).strip()
    if "vendor" in payload:
        v = payload.get("vendor")
        item.vendor = None if v is None or str(v).strip() == "" else str(v).strip()
    if "item_notes" in payload:
        v = payload.get("item_notes")
        item.item_notes = None if v is None else str(v)

    new = {
        "batch_number": item.batch_number,
        "vendor": item.vendor,
        "item_notes": item.item_notes,
    }

    if old == new:
        return {"message": "没有变更"}

    _add_audit_event(
        db,
        resource_type="stock_transaction_item",
        resource_id=str(item_id),
        action="edit_item_info",
        operator_id=current_user.id,
        comments=reason,
        details={"transaction_id": trans.id, "from": old, "to": new},
    )

    db.commit()
    return {"message": "明细信息更新成功"}


@router.post("/transaction-items/{item_id}/adjust")
async def adjust_stock_transaction_item_quantity(
    item_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更正辅材数量：不修改原入库明细，通过生成一条“调整”记录体现（支持正负差量）"""
    _ensure_stock_operator(current_user)

    reason = (payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="请填写更正原因")

    delta = payload.get("delta")
    try:
        delta = int(delta)
    except Exception:
        raise HTTPException(status_code=400, detail="delta 必须为整数")

    if delta == 0:
        raise HTTPException(status_code=400, detail="更正数量不能为 0")

    item = db.query(StockTransactionItem).filter(StockTransactionItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="出入库明细不存在")

    equipment = db.query(Equipment).filter(Equipment.id == item.equipment_id).first()
    if equipment and equipment.category == "main_device":
        raise HTTPException(status_code=400, detail="主设备不支持更正数量，请按 SN 撤销入库或重导")

    if item.equipment_instance_id:
        raise HTTPException(status_code=400, detail="带 SN 的主设备不支持改数量，请使用“撤销入库 + 重导”")

    trans = item.transaction
    if not trans:
        raise HTTPException(status_code=404, detail="关联出入库单不存在")

    warehouse_id = trans.warehouse_id
    inventory = db.query(Inventory).filter(
        and_(Inventory.warehouse_id == warehouse_id, Inventory.equipment_id == item.equipment_id)
    ).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="未找到对应库存记录")

    if delta < 0 and (inventory.available_stock < abs(delta) or inventory.current_stock < abs(delta)):
        raise HTTPException(status_code=400, detail="可用库存不足，无法减少")

    # 更新库存
    inventory.current_stock += delta
    inventory.available_stock += delta
    inventory.last_updated_by = current_user.id

    # 生成一条调整记录（用于可追溯）
    adjustment_id = uuid.uuid4().hex
    document_number = f"ADJ-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_user.id}-{uuid.uuid4().hex[:6]}"

    adj_trans = StockTransaction(
        id=adjustment_id,
        transaction_type=TransactionTypeEnum.ADJUSTMENT,
        warehouse_id=warehouse_id,
        operator_id=current_user.id,
        document_number=document_number,
        total_quantity=delta,
        notes=f"更正数量（原单 {trans.document_number}）：{reason}",
    )
    db.add(adj_trans)

    adj_item = StockTransactionItem(
        transaction_id=adjustment_id,
        equipment_id=item.equipment_id,
        quantity=delta,
        batch_number=item.batch_number,
        vendor=item.vendor,
        item_notes=reason,
    )
    db.add(adj_item)

    _add_audit_event(
        db,
        resource_type="inventory",
        resource_id=f"{warehouse_id}:{item.equipment_id}",
        action="adjust_quantity",
        operator_id=current_user.id,
        comments=reason,
        details={
            "transaction_id": trans.id,
            "transaction_item_id": item_id,
            "delta": delta,
            "adjustment_transaction_id": adjustment_id,
        },
    )

    db.commit()
    return {
        "message": "更正成功",
        "adjustment_transaction_id": adjustment_id,
        "document_number": document_number,
        "delta": delta,
    }


@router.post("/instances/void")
async def void_equipment_instances(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """撤销入库（作废设备实例，释放 SN 以便重导），并生成一条“调整”记录"""
    _ensure_stock_operator(current_user)

    reason = (payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="请填写撤销原因")

    instance_ids = payload.get("instance_ids") or []
    if not isinstance(instance_ids, list) or not instance_ids:
        raise HTTPException(status_code=400, detail="instance_ids 不能为空")

    # 预加载实例
    instances = db.query(EquipmentInstance).filter(EquipmentInstance.id.in_(instance_ids)).all()
    instance_map = {i.id: i for i in instances}

    results = []
    valid_instances = []

    for instance_id in instance_ids:
        inst = instance_map.get(instance_id)
        if not inst:
            results.append({"instance_id": instance_id, "success": False, "error": "设备实例不存在"})
            continue

        if bool(getattr(inst, "is_voided", False)):
            results.append({"instance_id": instance_id, "success": False, "error": "已撤销"})
            continue

        if inst.status != InventoryStatusEnum.IN_STOCK:
            results.append({"instance_id": instance_id, "success": False, "error": "非库存中状态，无法撤销"})
            continue

        if inst.issued_to:
            results.append({"instance_id": instance_id, "success": False, "error": "已出库/被领料，无法撤销"})
            continue

        if not inst.warehouse_id:
            results.append({"instance_id": instance_id, "success": False, "error": "缺少仓库信息，无法撤销"})
            continue

        valid_instances.append(inst)

    if not valid_instances:
        return {"message": "无可撤销实例", "success_count": 0, "failed_count": len(results), "results": results}

    # 检查库存是否足够（按 仓库+设备 聚合）
    needed = {}
    for inst in valid_instances:
        key = (inst.warehouse_id, inst.equipment_id)
        needed[key] = needed.get(key, 0) + 1

    for (warehouse_id, equipment_id), count in needed.items():
        inventory = db.query(Inventory).filter(
            and_(Inventory.warehouse_id == warehouse_id, Inventory.equipment_id == equipment_id)
        ).first()
        if not inventory or inventory.available_stock < count or inventory.current_stock < count:
            # 该组全部标记失败
            for inst in list(valid_instances):
                if inst.warehouse_id == warehouse_id and inst.equipment_id == equipment_id:
                    results.append({"instance_id": inst.id, "success": False, "error": "库存不足，无法撤销"})
                    valid_instances.remove(inst)

    if not valid_instances:
        return {"message": "库存不足，无法撤销", "success_count": 0, "failed_count": len(results), "results": results}

    # 按仓库生成调整单
    now = datetime.now()
    adjustment_ids = []
    by_warehouse = {}
    for inst in valid_instances:
        by_warehouse.setdefault(inst.warehouse_id, []).append(inst)

    for warehouse_id, inst_list in by_warehouse.items():
        adjustment_id = uuid.uuid4().hex
        document_number = f"ADJVOID-{now.strftime('%Y%m%d%H%M%S')}-{current_user.id}-{uuid.uuid4().hex[:6]}"
        adjustment_ids.append({"warehouse_id": warehouse_id, "transaction_id": adjustment_id, "document_number": document_number})

        adj_trans = StockTransaction(
            id=adjustment_id,
            transaction_type=TransactionTypeEnum.ADJUSTMENT,
            warehouse_id=warehouse_id,
            operator_id=current_user.id,
            document_number=document_number,
            total_quantity=-len(inst_list),
            notes=f"撤销入库（作废实例）：{reason}",
        )
        db.add(adj_trans)

        for inst in inst_list:
            placeholder = f"VOID-{uuid.uuid4().hex}"
            original_sn = inst.serial_number

            inst.original_serial_number = inst.original_serial_number or original_sn
            inst.serial_number = placeholder
            inst.barcode = placeholder
            inst.is_voided = True
            inst.voided_at = now
            inst.voided_by = current_user.id
            inst.void_reason = reason

            # 扣减库存
            inventory = db.query(Inventory).filter(
                and_(Inventory.warehouse_id == warehouse_id, Inventory.equipment_id == inst.equipment_id)
            ).first()
            if inventory:
                inventory.current_stock -= 1
                inventory.available_stock -= 1
                inventory.last_updated_by = current_user.id

            db.add(
                StockTransactionItem(
                    transaction_id=adjustment_id,
                    equipment_instance_id=inst.id,
                    equipment_id=inst.equipment_id,
                    quantity=-1,
                    batch_number=inst.batch_number,
                    vendor=inst.vendor,
                    item_notes=reason,
                )
            )

            # 同步导入明细状态（如存在）
            import_details = db.query(SNImportDetail).filter(
                and_(
                    SNImportDetail.equipment_instance_id == inst.id,
                    SNImportDetail.import_status == "success",
                )
            ).all()
            for d in import_details:
                d.import_status = "voided"
                d.error_message = f"已撤销入库：{reason}"

            _add_audit_event(
                db,
                resource_type="equipment_instance",
                resource_id=inst.id,
                action="void_stock_in",
                operator_id=current_user.id,
                comments=reason,
                details={"original_serial_number": original_sn},
            )

            results.append({"instance_id": inst.id, "success": True})

    db.commit()

    success_count = len([r for r in results if r.get("success")])
    failed_count = len([r for r in results if not r.get("success")])
    return {
        "message": "撤销完成",
        "success_count": success_count,
        "failed_count": failed_count,
        "adjustments": adjustment_ids,
        "results": results,
    }


@router.patch("/instances/{instance_id}")
async def update_equipment_instance_info(
    instance_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑设备实例信息（不允许修改 SN；需填写原因，用于审计）"""
    _ensure_stock_operator(current_user)

    reason = (payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="请填写修改原因")

    if "serial_number" in payload or "barcode" in payload:
        raise HTTPException(status_code=400, detail="SN/条码不允许修改，请使用“撤销入库 + 重导”")

    inst = db.query(EquipmentInstance).filter(EquipmentInstance.id == instance_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="设备实例不存在")

    if bool(getattr(inst, "is_voided", False)):
        raise HTTPException(status_code=400, detail="已撤销实例不可编辑")

    editable_fields = [
        "vendor",
        "batch_number",
        "mac_address",
        "imei",
        "firmware_version",
        "hardware_version",
        "manufacture_date",
        "warranty_start_date",
        "warranty_end_date",
        "location",
    ]

    old = {k: getattr(inst, k) for k in editable_fields}

    for field in editable_fields:
        if field not in payload:
            continue
        value = payload.get(field)
        if field in {"manufacture_date", "warranty_start_date", "warranty_end_date"}:
            if value in (None, ""):
                setattr(inst, field, None)
            else:
                try:
                    setattr(inst, field, datetime.fromisoformat(str(value)).date())
                except Exception:
                    raise HTTPException(status_code=400, detail=f"{field} 日期格式不正确")
        else:
            setattr(inst, field, None if value is None else str(value))

    new = {k: getattr(inst, k) for k in editable_fields}
    if old == new:
        return {"message": "没有变更"}

    _add_audit_event(
        db,
        resource_type="equipment_instance",
        resource_id=instance_id,
        action="edit_instance_info",
        operator_id=current_user.id,
        comments=reason,
        details={"from": old, "to": new},
    )

    db.commit()
    return {"message": "设备信息更新成功"}
