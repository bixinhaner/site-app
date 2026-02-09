from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload, aliased
from sqlalchemy import and_, or_, desc, func, case
from typing import List, Optional, Dict
from pydantic import BaseModel
import uuid
import os
from datetime import datetime
import logging
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.equipment import (
    Equipment, 
    EquipmentCategoryEnum,
    EquipmentPackage,
    EquipmentInstance,
    Warehouse,
    Inventory,
    OfflineDocument,
    OfflineDocumentPhoto,
    StockTransaction,
    StockTransactionItem,
    StockTransactionDocument,
    PickupRecord,
    SNImportRecord,
    SNImportDetail,
    TransactionTypeEnum,
    InventoryStatusEnum,
    EquipmentStatusEnum
)
from app.models.system_config import SystemConfig
from app.models.material_request import (
    MaterialRequest,
    MaterialRequestItem,
    MaterialRequestStatusEnum,
)
from app.models.issue_draft import (
    IssueDraft,
    IssueDraftItem,
    IssueDraftSerial,
    IssueDraftStatusEnum,
    IssueDraftSerialStatusEnum,
)
from app.models.work_order import AuditEvent
from app.models.inspection import InspectionCheckItem, InspectionPhoto, SiteInspection, InspectionStatusEnum, CheckItemStatusEnum
from app.utils.file_handler import save_uploaded_file, validate_image_on_disk, ImageValidationError
from app.utils.timezone import to_utc_iso

router = APIRouter()
logger = logging.getLogger(__name__)


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
            "warehouse_id": inv.warehouse_id,
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
    # 旧流程扫码领货：默认关闭（避免与新“物料申请→领料单→确认出库”并行导致使用混淆）
    # 该开关由 /api/system/mobile-settings 控制，并对所有客户端强制生效。
    try:
        from app.api.mobile_settings import _load_mobile_settings, _resolve_bool_for_user
        ms = _load_mobile_settings(db)
        enabled = _resolve_bool_for_user(ms, "enable_legacy_scan_pickup", current_user, default=False)
    except Exception:
        enabled = False
    if not enabled:
        raise HTTPException(status_code=400, detail="旧流程扫码领货已关闭，请使用“物料申请”流程领料")

    barcode = scan_data.get("barcode")
    parsed_barcode = scan_data.get("parsed_barcode")  # 解析后的条码数据
    package_id = scan_data.get("package_id")
    # 出库/领料属于库存链路，为避免影响工单业务，这里不再关联工单ID。
    gps_location = scan_data.get("gps_location")
    warehouse_id = scan_data.get("warehouse_id") or 1
    offline_document_id = scan_data.get("offline_document_id")
    offline_doc = _get_offline_document_for_use(db, current_user=current_user, offline_document_id=offline_document_id)

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
    mac3 = None
    mac4 = None
    
    if parsed_barcode and parsed_barcode.get("success"):
        serial_number = parsed_barcode.get("sn")
        mac1 = parsed_barcode.get("mac1")
        mac2 = parsed_barcode.get("mac2")
        mac3 = parsed_barcode.get("mac3")
        mac4 = parsed_barcode.get("mac4")
    
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
        conflict = (
            db.query(IssueDraftSerial.id)
            .join(IssueDraft, IssueDraftSerial.draft_id == IssueDraft.id)
            .filter(
                IssueDraftSerial.serial_number == serial_number,
                IssueDraftSerial.status == IssueDraftSerialStatusEnum.PENDING,
                IssueDraft.status.in_(
                    [
                        IssueDraftStatusEnum.DRAFT,
                        IssueDraftStatusEnum.PENDING_CONFIRM,
                        IssueDraftStatusEnum.PARTIALLY_CONFIRMED,
                    ]
                ),
            )
            .first()
        )
        if conflict:
            raise HTTPException(status_code=400, detail=f"SN已在领料单待确认，无法扫码出库：{serial_number}")

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
    
    # 2. 查找包含此设备的套装（仅启用）
    active_packages = db.query(EquipmentPackage).filter(
        EquipmentPackage.main_equipment_id == equipment.id,
        EquipmentPackage.status == EquipmentStatusEnum.ACTIVE
    ).all()
    
    if not active_packages:
        raise HTTPException(status_code=404, detail="该设备未配置套装")

    def _build_package_options(pkgs: List[EquipmentPackage]) -> List[dict]:
        options = []
        for pkg in pkgs:
            options.append(
                {
                    "id": pkg.id,
                    "package_code": pkg.package_code,
                    "package_name": pkg.package_name,
                    "site_type": pkg.site_type,
                }
            )
        return options

    # 2.1 兼容：如果客户端显式传入 package_id，则强制使用该套装（并校验合法性/启用状态）
    if package_id is not None:
        try:
            selected_package_id = int(package_id)
        except Exception:
            return JSONResponse(
                status_code=400,
                content={
                    "action": "select_package",
                    "message": "package_id 不合法，请重新选择设备套装",
                    "available_packages": _build_package_options(active_packages),
                },
            )

        selected_package = db.query(EquipmentPackage).filter(EquipmentPackage.id == selected_package_id).first()
        if not selected_package:
            return JSONResponse(
                status_code=400,
                content={
                    "action": "select_package",
                    "message": "所选设备套装不存在，请重新选择",
                    "available_packages": _build_package_options(active_packages),
                },
            )
        if selected_package.status != EquipmentStatusEnum.ACTIVE:
            return JSONResponse(
                status_code=400,
                content={
                    "action": "select_package",
                    "message": "所选设备套装已停用，请重新选择",
                    "available_packages": _build_package_options(active_packages),
                },
            )
        if selected_package.main_equipment_id != equipment.id:
            return JSONResponse(
                status_code=400,
                content={
                    "action": "select_package",
                    "message": "所选设备套装与当前主设备不匹配，请重新选择",
                    "available_packages": _build_package_options(active_packages),
                },
            )
        package = selected_package
    else:
        # 如果有多个套装，返回供选择（兼容旧客户端）
        if len(active_packages) > 1:
            return {
                "action": "select_package",
                "equipment": {
                    "code": equipment.equipment_code,
                    "name": equipment.equipment_name
                },
                "available_packages": _build_package_options(active_packages),
            }

        # 3. 使用第一个套装进行出库
        package = active_packages[0]
    
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
    transaction_id = uuid.uuid4().hex
    document_number = _build_request_no("OUT", current_user.id)

    transaction_scan_location = {}
    if isinstance(gps_location, dict):
        transaction_scan_location.update(gps_location)
    transaction_scan_location["_stock_flow_version"] = 2
    
    # 创建出库记录
    transaction = StockTransaction(
        id=transaction_id,
        transaction_type=TransactionTypeEnum.STOCK_OUT,
        warehouse_id=warehouse_id,
        package_id=package.id,
        operator_id=current_user.id,
        issued_to=current_user.id,
        offline_document_id=offline_doc.id if offline_doc else None,
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
        work_order_id=f"MANUAL-{current_user.id}",  # 仅用于满足非空字段约束
        package_id=package.id,
        picker_id=current_user.id,
        main_device_barcode=barcode,
        serial_number=serial_number,  # 记录SN
        mac_address_1=mac1,  # 记录MAC1
        mac_address_2=mac2,  # 记录MAC2
        mac_address_3=mac3,  # 记录MAC3
        mac_address_4=mac4,  # 记录MAC4
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
        equipment_instance.package_id = int(package.id)
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
    allowed_groups = {"picked", "pending_receive", "installed", "returned", "rejected"}
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
    # 仅将“包含主设备明细”的退库单视为影响该主设备的退库状态，避免“仅退辅料”把主设备误判为已退库
    # - 若 PickupRecord.equipment_instance_id 有值：按出库单 + equipment_instance_id 精确匹配
    # - 若为空：退化为“只要该退库单含任意主设备明细”即可（兼容极少数历史数据）
    return_item_match_cond = and_(
        StockTransactionItem.transaction_id == StockTransaction.id,
        StockTransactionItem.equipment_instance_id.isnot(None),
        or_(
            PickupRecord.equipment_instance_id.is_(None),
            StockTransactionItem.equipment_instance_id == PickupRecord.equipment_instance_id,
        ),
    )

    return_pending_exists = db.query(StockTransaction.id).join(
        StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id
    ).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == PickupRecord.transaction_id,
        StockTransaction.approval_status.in_(["pending_receive", "partially_received"]),
        return_item_match_cond,
    ).exists()
    return_received_exists = db.query(StockTransaction.id).join(
        StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id
    ).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == PickupRecord.transaction_id,
        StockTransaction.approval_status == "received",
        return_item_match_cond,
    ).exists()
    return_rejected_exists = db.query(StockTransaction.id).join(
        StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id
    ).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == PickupRecord.transaction_id,
        StockTransaction.approval_status == "rejected",
        return_item_match_cond,
    ).exists()
    return_reject_or_cancel_exists = db.query(StockTransaction.id).join(
        StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id
    ).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == PickupRecord.transaction_id,
        StockTransaction.approval_status.in_(["rejected", "canceled"]),
        return_item_match_cond,
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
    rejected_cond = and_(
        PickupRecord.is_returned == False,
        ~return_received_exists,
        ~return_pending_exists,
        return_rejected_exists,
    )
    installed_cond = and_(
        PickupRecord.is_returned == False,
        ~return_received_exists,
        ~return_pending_exists,
        ~return_rejected_exists,
        installed_locked_exists,
    )
    picked_cond = and_(
        PickupRecord.is_returned == False,
        ~return_received_exists,
        ~return_pending_exists,
        ~return_rejected_exists,
        ~installed_locked_exists,
    )

    counts_row = (
        query.order_by(None)
        .with_entities(
            func.sum(case((picked_cond, 1), else_=0)).label("picked"),
            func.sum(case((pending_receive_cond, 1), else_=0)).label("pending_receive"),
            func.sum(case((rejected_cond, 1), else_=0)).label("rejected"),
            func.sum(case((installed_cond, 1), else_=0)).label("installed"),
            func.sum(case((returned_cond, 1), else_=0)).label("returned"),
        )
        .one()
    )
    group_counts = {
        "picked": int(getattr(counts_row, "picked", 0) or 0),
        "pending_receive": int(getattr(counts_row, "pending_receive", 0) or 0),
        "rejected": int(getattr(counts_row, "rejected", 0) or 0),
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
    elif pickup_group == "rejected":
        query = query.filter(rejected_cond)
        query = query.order_by(desc(PickupRecord.pickup_time))
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

    # 退库单（方案A）信息：按（出库 transaction_id + equipment_instance_id）聚合取最新一条
    # 仅关注包含主设备明细的退库单，避免“仅退辅料”误影响主设备状态展示
    related_ids = [r.transaction_id for r in records if r.transaction_id]
    return_trans_map: Dict[tuple, dict] = {}
    if related_ids:
        try:
            ret_rows = db.query(
                StockTransaction.related_transaction_id.label("out_id"),
                StockTransaction.document_number.label("return_document_number"),
                StockTransaction.approval_status.label("return_status"),
                StockTransaction.warehouse_id.label("return_warehouse_id"),
                Warehouse.warehouse_name.label("return_warehouse_name"),
                StockTransaction.approval_comments.label("approval_comments"),
                StockTransaction.created_at.label("created_at"),
                StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
            ).join(
                StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id
            ).outerjoin(
                Warehouse, Warehouse.id == StockTransaction.warehouse_id
            ).filter(
                StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                StockTransaction.related_transaction_id.in_(related_ids),
                StockTransaction.approval_status.in_(["pending_receive", "partially_received", "received", "rejected", "canceled"]),
                StockTransactionItem.equipment_instance_id.isnot(None),
            ).order_by(desc(StockTransaction.created_at)).all()

            for rr in ret_rows:
                out_id = str(getattr(rr, "out_id", "") or "").strip()
                inst_id = str(getattr(rr, "equipment_instance_id", "") or "").strip()
                if not out_id or not inst_id:
                    continue
                payload = {
                    "return_document_number": getattr(rr, "return_document_number", None),
                    "return_status": getattr(rr, "return_status", None),
                    "return_warehouse_id": getattr(rr, "return_warehouse_id", None),
                    "return_warehouse_name": getattr(rr, "return_warehouse_name", None),
                    "approval_comments": getattr(rr, "approval_comments", None),
                }
                key_exact = (out_id, inst_id)
                if key_exact not in return_trans_map:
                    return_trans_map[key_exact] = payload
                key_fallback = (out_id, None)
                if key_fallback not in return_trans_map:
                    return_trans_map[key_fallback] = payload
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

        out_id = record.transaction_id
        inst_id = record.equipment_instance_id
        latest_return = None
        if out_id:
            if inst_id:
                latest_return = return_trans_map.get((out_id, str(inst_id))) or return_trans_map.get((out_id, None))
            else:
                latest_return = return_trans_map.get((out_id, None))
        latest_return_status = latest_return.get("return_status") if latest_return else None
        pickup_group_value = "picked"
        if record.is_returned or latest_return_status == "received":
            pickup_group_value = "returned"
        elif latest_return_status in {"pending_receive", "partially_received"}:
            pickup_group_value = "pending_receive"
        elif latest_return_status == "rejected":
            pickup_group_value = "rejected"
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
            "mac_address_3": record.mac_address_3,
            "mac_address_4": record.mac_address_4,
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
            "return_document_number": latest_return.get("return_document_number") if latest_return else None,
            "return_warehouse_id": latest_return.get("return_warehouse_id") if latest_return else None,
            "return_warehouse_name": latest_return.get("return_warehouse_name") if latest_return else None,
            "return_reject_reason": (
                latest_return.get("approval_comments")
                if latest_return_status == "rejected" and latest_return
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

    注意：判定“是否仍绑定/是否需要解绑”以 equipment_binding_history 的最新动作(action)为准，
    避免历史检查项残留 SN 导致退库被永久阻断。
    """

    sn = (sn or "").strip()
    if not sn:
        return {"need_unbind": [], "blocked": []}

    # 仅关心“当前仍绑定”的 SN：取该 SN 最新一条绑定历史记录
    try:
        from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum
    except Exception:
        EquipmentBindingHistory = None  # type: ignore
        BindingActionEnum = None  # type: ignore

    if not EquipmentBindingHistory:
        return {"need_unbind": [], "blocked": []}

    latest = (
        db.query(EquipmentBindingHistory)
        .options(
            joinedload(EquipmentBindingHistory.inspection).joinedload(SiteInspection.work_order),
            joinedload(EquipmentBindingHistory.inspection).joinedload(SiteInspection.site),
        )
        .filter(EquipmentBindingHistory.equipment_sn == sn)
        .order_by(EquipmentBindingHistory.operated_at.desc(), EquipmentBindingHistory.id.desc())
        .first()
    )

    if not latest or getattr(latest, "action", None) == BindingActionEnum.UNBIND:
        return {"need_unbind": [], "blocked": []}

    # 仅设备级绑定需要解绑：sector_id + band 且 cell_id == f"{sector_id}_{band}"（cell_id 缺失视为设备级）
    sector_id = getattr(latest, "sector_id", None)
    band = getattr(latest, "band", None)
    cell_id = getattr(latest, "cell_id", None)
    if not sector_id or not band:
        return {"need_unbind": [], "blocked": []}
    key = f"{sector_id}_{band}"
    if cell_id and str(cell_id) != key:
        return {"need_unbind": [], "blocked": []}

    insp: Optional[SiteInspection] = getattr(latest, "inspection", None)
    work_order = getattr(insp, "work_order", None) if insp else None
    site = getattr(insp, "site", None) if insp else None

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

    insp_status = insp.status if insp and hasattr(insp, "status") else None
    info = {
        "inspection_id": getattr(insp, "id", None) if insp else None,
        "inspection_status": getattr(insp_status, "value", insp_status),
        "sector_id": sector_id,
        "band": band,
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
        return {"need_unbind": need_unbind, "blocked": blocked}

    if insp_status in allow_unbind_status:
        need_unbind.append(info)
        return {"need_unbind": need_unbind, "blocked": blocked}

    if insp_status in block_status:
        info["reason_code"] = "inspection_locked"
        info["reason"] = "检查已提交/审核中/已完成，禁止解绑"
        blocked.append(info)
        return {"need_unbind": need_unbind, "blocked": blocked}

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

    # 写入绑定历史：UNBIND（用于“当前绑定推导/退库判定”）
    try:
        from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum

        for it in device_items:
            prev_sn = (getattr(it, "equipment_sn", None) or "").strip()
            if not prev_sn:
                continue
            insp = getattr(it, "inspection", None)
            site_id = getattr(insp, "site_id", None) if insp else None
            if not site_id:
                continue
            db.add(
                EquipmentBindingHistory(
                    inspection_id=getattr(it, "inspection_id", None) or "",
                    check_item_id=it.id,
                    site_id=int(site_id),
                    sector_id=str(getattr(it, "sector_id", "") or ""),
                    band=str(getattr(it, "band", "") or ""),
                    cell_id=str(getattr(it, "cell_id", "") or f"{it.sector_id}_{it.band}"),
                    equipment_sn=prev_sn,
                    action=BindingActionEnum.UNBIND,
                    operator_id=current_user.id,
                    previous_equipment_sn=None,
                    notes="扫码退库：一键解绑",
                )
            )
    except Exception:
        # 历史表异常不阻断解绑（保持旧行为）
        pass

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
    pickup_record_id = pickup_record.id if pickup_record else None

    out_trans = None
    if pickup_record:
        out_trans = db.query(StockTransaction).filter(StockTransaction.id == pickup_record.transaction_id).first()
    else:
        # 兼容：新流程（领料单确认出库 / 快速出库）不会写 pickup_records
        out_trans = _find_accessible_single_main_stock_out_by_sn(db, sn=sn, current_user=current_user)

    if not out_trans:
        return {"action": "no_active_pickup", "message": "未找到可退库的领料记录"}

    existing_return = db.query(StockTransaction).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == out_trans.id,
        StockTransaction.approval_status.in_(["pending_receive", "partially_received", "received"]),
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
        "pickup_record_id": pickup_record_id,
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
    offline_document_id = payload.get("offline_document_id")
    offline_doc = _get_offline_document_for_use(db, current_user=current_user, offline_document_id=offline_document_id)

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
    out_trans = None
    if pickup_record:
        out_trans = db.query(StockTransaction).filter(StockTransaction.id == pickup_record.transaction_id).first()
    else:
        out_trans = _find_accessible_single_main_stock_out_by_sn(db, sn=sn, current_user=current_user)
        if not out_trans:
            raise HTTPException(status_code=404, detail="未找到可退库的领料记录")
    if not out_trans:
        raise HTTPException(status_code=404, detail="出库单不存在")

    # 检查是否已有活动退库单
    existing_return = db.query(StockTransaction).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.related_transaction_id == out_trans.id,
        StockTransaction.approval_status.in_(["pending_receive", "partially_received", "received"]),
    ).order_by(desc(StockTransaction.created_at)).first()
    if existing_return:
        raise HTTPException(status_code=400, detail="已存在退库单，无法重复申请")

    bindings = _get_blocking_bindings(db, sn=sn, current_user=current_user)
    if bindings["blocked"]:
        raise HTTPException(status_code=400, detail="存在不可解绑的检查绑定，无法发起退库")
    if bindings["need_unbind"]:
        raise HTTPException(status_code=400, detail="存在设备级检查绑定，需先解绑并清理检查内容")

    now = datetime.now()
    return_transaction_id = str(uuid.uuid4())
    document_number = f"RET-{now.strftime('%Y%m%d%H%M%S')}-{current_user.id}"

    return_trans = StockTransaction(
        id=return_transaction_id,
        transaction_type=TransactionTypeEnum.RETURN,
        warehouse_id=return_warehouse_id,
        operator_id=current_user.id,
        offline_document_id=offline_doc.id if offline_doc else None,
        scan_barcode=sn,
        scan_time=now,
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

    # 主设备实例进入“退库待收货”状态（不回滚库存，等待仓库收货确认）
    equipment_instance = db.query(EquipmentInstance).filter(EquipmentInstance.serial_number == sn).first()
    if equipment_instance:
        equipment_instance.status = InventoryStatusEnum.RETURN_PENDING_RECEIVE
        equipment_instance.updated_at = now

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

    now = datetime.now()
    trans.approval_status = "canceled"
    if reason:
        trans.approval_comments = reason

    # 取消后，回退主设备实例状态（与拒收逻辑保持一致）
    try:
        items = db.query(StockTransactionItem).filter(StockTransactionItem.transaction_id == trans.id).all()
        instance_ids = [it.equipment_instance_id for it in items if it and it.equipment_instance_id]
        if instance_ids:
            inst_rows = db.query(EquipmentInstance).filter(EquipmentInstance.id.in_(instance_ids)).all()
            for inst in inst_rows:
                if _enum_value(inst.status) == InventoryStatusEnum.RETURN_PENDING_RECEIVE.value:
                    inst.status = InventoryStatusEnum.ISSUED
                    inst.updated_at = now
    except Exception:
        # 兼容旧库/异常：取消退库仍应成功
        pass

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
    pickup_query = db.query(PickupRecord).filter(
        PickupRecord.transaction_id == out_trans.id,
        PickupRecord.picker_id == return_trans.operator_id,
        PickupRecord.is_returned == False,
    )
    if equipment_instance:
        pickup_query = pickup_query.filter(PickupRecord.equipment_instance_id == equipment_instance.id)
    pickup_record = pickup_query.order_by(desc(PickupRecord.pickup_time)).first()
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

    # 拒收后，设备仍视为“已出库”（回退实例状态）
    sn = (return_trans.scan_barcode or "").strip()
    if sn:
        equipment_instance = db.query(EquipmentInstance).filter(EquipmentInstance.serial_number == sn).first()
        if equipment_instance:
            equipment_instance.status = InventoryStatusEnum.ISSUED
            equipment_instance.updated_at = now

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
    offline_document_id = return_data.get("offline_document_id")
    offline_doc = _get_offline_document_for_use(db, current_user=current_user, offline_document_id=offline_document_id)

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
        offline_document_id=offline_doc.id if offline_doc else None,
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
    offline_document_id = stock_in_data.get("offline_document_id")
    offline_doc = _get_offline_document_for_use(db, current_user=current_user, offline_document_id=offline_document_id)
    
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
        offline_document_id=offline_doc.id if offline_doc else None,
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
        operator_id = getattr(trans, "operator_id", None)
        operator_name = None
        if operator_id is not None and str(operator_id).strip() != "":
            operator = getattr(trans, "operator", None)
            if operator:
                operator_name = operator.full_name or operator.username or str(operator_id)
            else:
                operator_name = f"已删除用户(原ID:{operator_id})"

        issued_to = getattr(trans, "issued_to", None)
        receiver_name = None
        if issued_to is not None and str(issued_to).strip() != "":
            receiver = getattr(trans, "receiver", None)
            if receiver:
                receiver_name = receiver.full_name or receiver.username or str(issued_to)
            else:
                receiver_name = f"已删除用户(原ID:{issued_to})"

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
            "operator_name": operator_name,
            "issued_to": issued_to,
            "receiver_name": receiver_name,
            "operation_time": to_utc_iso(trans.operation_time) if trans.operation_time else None,
            "total_quantity": trans.total_quantity,
            "approval_status": trans.approval_status,
            "approval_comments": trans.approval_comments,
            "approved_by": trans.approved_by,
            "approved_at": to_utc_iso(trans.approved_at, assume_local=True) if trans.approved_at else None,
            "scan_barcode": trans.scan_barcode,
            "notes": trans.notes,
            "related_transaction_id": getattr(trans, "related_transaction_id", None),
            "offline_document_id": getattr(trans, "offline_document_id", None),
            "items": items,
            "task_id": None,
            "package_name": trans.package.package_name if trans.package else None
        })
    
    return {"transactions": result, "total": len(result)}

# ===== 线下票据（可复用） =====

MAX_OFFLINE_DOCUMENT_PHOTOS = 10


def _ensure_can_manage_offline_document(current_user: User, doc: OfflineDocument) -> None:
    if current_user.role in ["admin", "warehouse_manager", "manager"]:
        return
    if doc.created_by == current_user.id:
        return
    raise HTTPException(status_code=403, detail="无权限操作该线下票据")


def _get_offline_document_for_use(
    db: Session, *, current_user: User, offline_document_id: Optional[str]
) -> Optional[OfflineDocument]:
    doc_id = str(offline_document_id or "").strip()
    if not doc_id:
        return None
    doc = db.query(OfflineDocument).filter(OfflineDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="线下票据不存在")
    _ensure_can_manage_offline_document(current_user, doc)
    return doc


def _serialize_offline_document_photo(p: OfflineDocumentPhoto) -> dict:
    return {
        "id": p.id,
        "document_id": p.document_id,
        "original_name": p.original_name,
        "file_path": p.file_path,
        "file_size": p.file_size,
        "mime_type": p.mime_type,
        "uploaded_by": p.uploaded_by,
        "created_at": to_utc_iso(p.created_at) if p.created_at else None,
    }


def _serialize_offline_document(doc: OfflineDocument) -> dict:
    photos = [_serialize_offline_document_photo(p) for p in (doc.photos or [])]
    photos.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {
        "id": doc.id,
        "remark": doc.remark,
        "created_by": doc.created_by,
        "created_at": to_utc_iso(doc.created_at) if doc.created_at else None,
        "photos": photos,
        "photo_count": len(photos),
    }


@router.post("/offline-documents")
async def create_offline_document(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建线下票据（不含照片）。照片请调用 /offline-documents/{id}/photos 上传。"""
    _ensure_not_surveyor(current_user)

    remark = ""
    if isinstance(payload, dict):
        remark = str(payload.get("remark") or "").strip()
        if len(remark) > 500:
            remark = remark[:500]

    doc = OfflineDocument(
        id=uuid.uuid4().hex,
        remark=remark or None,
        created_by=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _serialize_offline_document(doc)


@router.get("/offline-documents/{document_id}")
async def get_offline_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取线下票据及照片列表。"""
    _ensure_not_surveyor(current_user)

    doc = (
        db.query(OfflineDocument)
        .options(joinedload(OfflineDocument.photos))
        .filter(OfflineDocument.id == document_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="线下票据不存在")
    _ensure_can_manage_offline_document(current_user, doc)
    return _serialize_offline_document(doc)


@router.post("/offline-documents/{document_id}/photos")
async def upload_offline_document_photo(
    document_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传线下票据照片：单张上传，最多 10 张（jpg/jpeg/png）。"""
    _ensure_not_surveyor(current_user)

    doc = db.query(OfflineDocument).filter(OfflineDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="线下票据不存在")
    _ensure_can_manage_offline_document(current_user, doc)

    existing_count = (
        db.query(func.count(OfflineDocumentPhoto.id))
        .filter(OfflineDocumentPhoto.document_id == document_id)
        .scalar()
        or 0
    )
    if int(existing_count) >= MAX_OFFLINE_DOCUMENT_PHOTOS:
        raise HTTPException(status_code=400, detail=f"票据照片已达到上限（{MAX_OFFLINE_DOCUMENT_PHOTOS}张）")

    filename = (file.filename or "").strip()
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_STOCK_DOCUMENT_EXTS:
        raise HTTPException(status_code=400, detail="仅支持 jpg/jpeg/png 图片")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件")

    stored_path = await save_uploaded_file(file, category="stock_offline_documents", sub_folder=document_id)

    try:
        validate_image_on_disk(stored_path, detect_blank_bottom=False)
    except ImageValidationError as e:
        try:
            if stored_path and os.path.exists(stored_path):
                os.remove(stored_path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))

    try:
        max_bytes = int(getattr(settings, "MAX_FILE_SIZE", 10 * 1024 * 1024) or 10 * 1024 * 1024)
    except Exception:
        max_bytes = 10 * 1024 * 1024

    file_size = None
    try:
        if stored_path and os.path.exists(stored_path):
            file_size = int(os.path.getsize(stored_path))
    except Exception:
        file_size = None
    if file_size is not None and file_size > max_bytes:
        try:
            if stored_path and os.path.exists(stored_path):
                os.remove(stored_path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"图片大小超过限制（{max_bytes // (1024 * 1024)}MB）")

    photo = OfflineDocumentPhoto(
        id=uuid.uuid4().hex,
        document_id=document_id,
        original_name=filename or None,
        file_path=stored_path,
        file_size=file_size,
        mime_type=file.content_type,
        uploaded_by=current_user.id,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return _serialize_offline_document_photo(photo)


@router.delete("/offline-documents/{document_id}/photos/{photo_id}")
async def delete_offline_document_photo(
    document_id: str,
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除线下票据照片。"""
    _ensure_not_surveyor(current_user)

    doc = db.query(OfflineDocument).filter(OfflineDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="线下票据不存在")
    _ensure_can_manage_offline_document(current_user, doc)

    photo = (
        db.query(OfflineDocumentPhoto)
        .filter(OfflineDocumentPhoto.id == photo_id, OfflineDocumentPhoto.document_id == document_id)
        .first()
    )
    if not photo:
        raise HTTPException(status_code=404, detail="票据照片不存在")

    file_path = photo.file_path
    db.delete(photo)
    db.commit()

    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass
    return {"success": True}

# ===== 出入库单据照片（按单上传，历史兼容） =====

MAX_STOCK_TRANSACTION_DOCUMENTS = 10
ALLOWED_STOCK_DOCUMENT_EXTS = {".jpg", ".jpeg", ".png"}


def _ensure_can_manage_transaction_docs(current_user: User, tx: StockTransaction) -> None:
    """仅允许出入库操作人或仓库侧角色管理单据照片。"""
    if current_user.role in ["admin", "warehouse_manager", "manager"]:
        return
    if tx.operator_id == current_user.id:
        return
    raise HTTPException(status_code=403, detail="无权限操作该出入库单据照片")


def _serialize_stock_transaction_document(doc: StockTransactionDocument) -> dict:
    return {
        "id": doc.id,
        "transaction_id": doc.transaction_id,
        "original_name": doc.original_name,
        "file_path": doc.file_path,
        "file_size": doc.file_size,
        "mime_type": doc.mime_type,
        "uploaded_by": doc.uploaded_by,
        "created_at": to_utc_iso(doc.created_at) if doc.created_at else None,
    }


@router.get("/transactions/{transaction_id}/documents")
async def list_stock_transaction_documents(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取出入库单据照片列表（线下单据）。"""
    _ensure_not_surveyor(current_user)

    tx = db.query(StockTransaction).filter(StockTransaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="出入库单不存在")
    _ensure_can_manage_transaction_docs(current_user, tx)

    docs = (
        db.query(StockTransactionDocument)
        .filter(StockTransactionDocument.transaction_id == transaction_id)
        .order_by(desc(StockTransactionDocument.created_at))
        .all()
    )
    return {"documents": [_serialize_stock_transaction_document(d) for d in docs], "total": len(docs)}


@router.post("/transactions/{transaction_id}/documents")
async def upload_stock_transaction_document(
    transaction_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传出入库单据照片（线下单据拍照）。单张上传，最多 10 张。"""
    _ensure_not_surveyor(current_user)

    tx = db.query(StockTransaction).filter(StockTransaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="出入库单不存在")
    _ensure_can_manage_transaction_docs(current_user, tx)

    existing_count = (
        db.query(func.count(StockTransactionDocument.id))
        .filter(StockTransactionDocument.transaction_id == transaction_id)
        .scalar()
        or 0
    )
    if int(existing_count) >= MAX_STOCK_TRANSACTION_DOCUMENTS:
        raise HTTPException(status_code=400, detail=f"单据照片已达到上限（{MAX_STOCK_TRANSACTION_DOCUMENTS}张）")

    filename = (file.filename or "").strip()
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_STOCK_DOCUMENT_EXTS:
        raise HTTPException(status_code=400, detail="仅支持 jpg/jpeg/png 图片")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件")

    stored_path = await save_uploaded_file(file, category="stock_documents", sub_folder=transaction_id)

    # 校验图片可完整解码（线下单据照片允许留白，不做“底部空白”启发式拦截）
    try:
        validate_image_on_disk(stored_path, detect_blank_bottom=False)
    except ImageValidationError as e:
        try:
            if stored_path and os.path.exists(stored_path):
                os.remove(stored_path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))

    # 尺寸限制：默认 10MB（沿用系统配置）
    try:
        max_bytes = int(getattr(settings, "MAX_FILE_SIZE", 10 * 1024 * 1024) or 10 * 1024 * 1024)
    except Exception:
        max_bytes = 10 * 1024 * 1024
    file_size = None
    try:
        if stored_path and os.path.exists(stored_path):
            file_size = int(os.path.getsize(stored_path))
    except Exception:
        file_size = None
    if file_size is not None and file_size > max_bytes:
        try:
            if stored_path and os.path.exists(stored_path):
                os.remove(stored_path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"图片大小超过限制（{max_bytes // (1024 * 1024)}MB）")

    doc = StockTransactionDocument(
        id=uuid.uuid4().hex,
        transaction_id=transaction_id,
        original_name=filename or None,
        file_path=stored_path,
        file_size=file_size,
        mime_type=file.content_type,
        uploaded_by=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _serialize_stock_transaction_document(doc)


@router.delete("/transactions/{transaction_id}/documents/{document_id}")
async def delete_stock_transaction_document(
    transaction_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除出入库单据照片。"""
    _ensure_not_surveyor(current_user)

    tx = db.query(StockTransaction).filter(StockTransaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="出入库单不存在")
    _ensure_can_manage_transaction_docs(current_user, tx)

    doc = (
        db.query(StockTransactionDocument)
        .filter(
            StockTransactionDocument.id == document_id,
            StockTransactionDocument.transaction_id == transaction_id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="单据照片不存在")

    file_path = doc.file_path
    db.delete(doc)
    db.commit()

    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass
    return {"success": True}

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

    offline_document_id = None
    if isinstance(file_data, dict):
        offline_document_id = file_data.get("offline_document_id")
    offline_doc = _get_offline_document_for_use(
        db, current_user=current_user, offline_document_id=offline_document_id
    )
    
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
                offline_document_id=offline_doc.id if offline_doc else None,
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
    warehouse_id: Optional[int] = None,
    include_out: bool = False,
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

    # 仅查询指定仓库的实例（默认只看仓库内；可选包含“已出库但上次出库仓库=当前仓库”的实例）
    if warehouse_id is not None:
        out_instance_ids = []
        if include_out:
            out_instance_subq = (
                db.query(EquipmentInstance.id.label("id"))
                .filter(
                    EquipmentInstance.equipment_id == equipment_id,
                    EquipmentInstance.warehouse_id.is_(None),
                )
            )
            if not include_voided:
                out_instance_subq = out_instance_subq.filter(
                    or_(EquipmentInstance.is_voided == False, EquipmentInstance.is_voided.is_(None))
                )
            if status:
                out_instance_subq = out_instance_subq.filter(EquipmentInstance.status == status)
            out_instance_subq = out_instance_subq.subquery()

            latest_out_subq = (
                db.query(
                    StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
                    func.max(StockTransaction.operation_time).label("last_out_time"),
                )
                .join(StockTransaction, StockTransaction.id == StockTransactionItem.transaction_id)
                .join(out_instance_subq, StockTransactionItem.equipment_instance_id == out_instance_subq.c.id)
                .filter(StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT)
                .group_by(StockTransactionItem.equipment_instance_id)
                .subquery()
            )

            out_rows = (
                db.query(StockTransactionItem.equipment_instance_id)
                .join(StockTransaction, StockTransaction.id == StockTransactionItem.transaction_id)
                .join(
                    latest_out_subq,
                    and_(
                        StockTransactionItem.equipment_instance_id == latest_out_subq.c.equipment_instance_id,
                        StockTransaction.operation_time == latest_out_subq.c.last_out_time,
                    ),
                )
                .filter(
                    StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
                    StockTransaction.warehouse_id == warehouse_id,
                )
                .distinct()
                .all()
            )
            out_instance_ids = [r[0] for r in out_rows]

        if out_instance_ids:
            query = query.filter(or_(EquipmentInstance.warehouse_id == warehouse_id, EquipmentInstance.id.in_(out_instance_ids)))
        else:
            query = query.filter(EquipmentInstance.warehouse_id == warehouse_id)
    
    instances = query.order_by(desc(EquipmentInstance.created_at)).all()

    # warehouse_id 为空即视为已出库（或在库外），需回溯上个仓库信息用于前端展示
    out_instance_ids = [inst.id for inst in instances if inst.warehouse_id is None]
    last_warehouse_map = {}
    if out_instance_ids:
        latest_out_subq = (
            db.query(
                StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
                func.max(StockTransaction.operation_time).label("last_out_time"),
            )
            .join(StockTransaction, StockTransaction.id == StockTransactionItem.transaction_id)
            .filter(
                StockTransactionItem.equipment_instance_id.in_(out_instance_ids),
                StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            )
            .group_by(StockTransactionItem.equipment_instance_id)
            .subquery()
        )

        out_rows = (
            db.query(
                StockTransactionItem.equipment_instance_id,
                StockTransaction.warehouse_id,
                Warehouse.warehouse_name,
            )
            .join(StockTransaction, StockTransaction.id == StockTransactionItem.transaction_id)
            .join(Warehouse, Warehouse.id == StockTransaction.warehouse_id)
            .join(
                latest_out_subq,
                and_(
                    StockTransactionItem.equipment_instance_id == latest_out_subq.c.equipment_instance_id,
                    StockTransaction.operation_time == latest_out_subq.c.last_out_time,
                ),
            )
            .filter(StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT)
            .all()
        )
        for equipment_instance_id, last_wh_id, warehouse_name in out_rows:
            last_warehouse_map[equipment_instance_id] = {
                "warehouse_id": last_wh_id,
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


# ===== 新流程：流程设置 / 物料申请 / 领料单（待确认出库）/ 快速出库 / 退库（按出库明细）=====

STOCK_FLOW_SETTINGS_KEY = "stock_flow_settings"
DEFAULT_STOCK_FLOW_SETTINGS = {
    # 申请 → 领料单 → 仓库确认出库
    "enable_material_request": True,
    "request_requires_approval": True,
    "issue_requires_warehouse_confirm": True,
    # 无申请直接出库（兜底）
    "allow_quick_stock_out": True,
}


def _enum_value(value):
    try:
        return value.value
    except Exception:
        return value


def _ensure_not_surveyor(current_user: User) -> None:
    if getattr(current_user, "role", None) == "surveyor":
        raise HTTPException(status_code=403, detail="权限不足")


def _get_flow_settings(db: Session) -> dict:
    settings = dict(DEFAULT_STOCK_FLOW_SETTINGS)
    row = db.query(SystemConfig).filter(SystemConfig.key == STOCK_FLOW_SETTINGS_KEY).first()
    if row and isinstance(row.value, dict):
        for k in settings.keys():
            if k in row.value:
                settings[k] = bool(row.value.get(k))
    return settings


def _save_flow_settings(db: Session, incoming: dict) -> dict:
    settings = dict(DEFAULT_STOCK_FLOW_SETTINGS)
    if isinstance(incoming, dict):
        for k in settings.keys():
            if k in incoming:
                settings[k] = bool(incoming.get(k))
    row = db.query(SystemConfig).filter(SystemConfig.key == STOCK_FLOW_SETTINGS_KEY).first()
    if row is None:
        row = SystemConfig(key=STOCK_FLOW_SETTINGS_KEY, value=settings)
        db.add(row)
    else:
        row.value = settings
    db.commit()
    return settings


def _ensure_material_request_enabled(db: Session) -> None:
    settings = _get_flow_settings(db)
    if not settings.get("enable_material_request", True):
        raise HTTPException(status_code=400, detail="物料申请流程已关闭")


def _ensure_quick_stock_out_enabled(db: Session) -> None:
    settings = _get_flow_settings(db)
    if not settings.get("allow_quick_stock_out", True):
        raise HTTPException(status_code=400, detail="快捷出库已关闭")


@router.get("/flow-settings")
async def get_stock_flow_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_not_surveyor(current_user)
    return {"settings": _get_flow_settings(db)}


@router.put("/flow-settings")
async def update_stock_flow_settings(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_stock_operator(current_user)
    settings = payload.get("settings") if isinstance(payload, dict) else {}
    saved = _save_flow_settings(db, settings)
    return {"settings": saved}


def _ensure_active_warehouse(db: Session, warehouse_id: int) -> Warehouse:
    wh = (
        db.query(Warehouse)
        .filter(Warehouse.id == warehouse_id, Warehouse.status == EquipmentStatusEnum.ACTIVE)
        .first()
    )
    if not wh:
        raise HTTPException(status_code=400, detail="仓库不存在或已停用")
    return wh


def _build_request_no(prefix: str, user_id: int) -> str:
    # 避免秒级并发导致单号冲突：使用毫秒 + 随机后缀
    ts_ms = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    suffix = uuid.uuid4().hex[:6]
    return f"{prefix}-{ts_ms}-{user_id}-{suffix}"


def _merge_request_items(items: list) -> list:
    merged: Dict[int, int] = {}
    for row in items or []:
        if not isinstance(row, dict):
            continue
        try:
            eid = int(row.get("equipment_id"))
            qty = int(row.get("quantity") or 0)
        except Exception:
            continue
        if eid <= 0 or qty <= 0:
            continue
        merged[eid] = merged.get(eid, 0) + qty
    return [{"equipment_id": eid, "quantity": qty} for eid, qty in merged.items()]


def _calc_request_pending_map(db: Session, request_id: str) -> Dict[int, int]:
    """统计某申请单各物料“待确认数量”（包含 draft/pending_confirm/partially_confirmed）。"""
    pending: Dict[int, int] = {}

    active_status = [
        IssueDraftStatusEnum.DRAFT,
        IssueDraftStatusEnum.PENDING_CONFIRM,
        IssueDraftStatusEnum.PARTIALLY_CONFIRMED,
    ]

    # 辅料：planned - confirmed
    aux_rows = (
        db.query(
            IssueDraftItem.equipment_id,
            func.sum(
                func.coalesce(IssueDraftItem.planned_qty, 0) - func.coalesce(IssueDraftItem.confirmed_qty, 0)
            ).label("pending_qty"),
        )
        .join(IssueDraft, IssueDraftItem.draft_id == IssueDraft.id)
        .filter(IssueDraft.request_id == request_id, IssueDraft.status.in_(active_status))
        .group_by(IssueDraftItem.equipment_id)
        .all()
    )
    for equipment_id, qty in aux_rows:
        try:
            pending[int(equipment_id)] = max(int(qty or 0), 0)
        except Exception:
            continue

    # 主设备：pending serial 计数
    main_rows = (
        db.query(
            IssueDraftSerial.equipment_id,
            func.count(IssueDraftSerial.id).label("pending_count"),
        )
        .join(IssueDraft, IssueDraftSerial.draft_id == IssueDraft.id)
        .filter(
            IssueDraft.request_id == request_id,
            IssueDraft.status.in_(active_status),
            IssueDraftSerial.status == IssueDraftSerialStatusEnum.PENDING,
        )
        .group_by(IssueDraftSerial.equipment_id)
        .all()
    )
    for equipment_id, cnt in main_rows:
        try:
            eid = int(equipment_id)
            pending[eid] = pending.get(eid, 0) + int(cnt or 0)
        except Exception:
            continue

    return pending


def _serialize_material_request(db: Session, req: MaterialRequest) -> dict:
    pending_map = _calc_request_pending_map(db, req.id)

    items = []
    for it in req.items or []:
        eq = it.equipment
        eq_cat = _enum_value(eq.category) if eq else None
        pending_qty = int(pending_map.get(int(it.equipment_id), 0))
        approved_qty = int(getattr(it, "approved_qty", 0) or 0)
        issued_qty = int(getattr(it, "issued_qty", 0) or 0)
        remaining_qty = max(approved_qty - issued_qty - pending_qty, 0)

        items.append(
            {
                "id": it.id,
                "equipment_id": it.equipment_id,
                "equipment_name": eq.equipment_name if eq else None,
                "equipment_code": eq.equipment_code if eq else None,
                "equipment_category": eq_cat,
                "unit": getattr(eq, "unit", None) if eq else None,
                "requested_qty": int(getattr(it, "requested_qty", 0) or 0),
                "approved_qty": approved_qty,
                "issued_qty": issued_qty,
                "pending_qty": pending_qty,
                "remaining_qty": remaining_qty,
            }
        )

    # 主设备摘要（列表展示用）
    main_items = [x for x in items if x.get("equipment_category") == EquipmentCategoryEnum.MAIN_DEVICE.value]
    main_total = sum(int(x.get("requested_qty") or 0) for x in main_items)
    if main_total <= 0:
        main_summary = "-"
    else:
        parts = []
        for x in main_items[:2]:
            nm = x.get("equipment_name") or ""
            qty = int(x.get("requested_qty") or 0)
            if nm:
                parts.append(f"{nm}×{qty}")
        if len(main_items) > 2:
            main_summary = "，".join(parts) + f"…（共{main_total}台）"
        else:
            main_summary = "，".join(parts) if parts else f"共{main_total}台"

    return {
        "id": req.id,
        "request_no": req.request_no,
        "warehouse_id": req.warehouse_id,
        "warehouse_name": req.warehouse.warehouse_name if req.warehouse else None,
        "requester_id": req.requester_id,
        "requester_name": req.requester.full_name if req.requester and req.requester.full_name else (req.requester.username if req.requester else None),
        "status": _enum_value(req.status),
        "notes": req.notes,
        "submitted_at": to_utc_iso(req.submitted_at, assume_local=True) if req.submitted_at else None,
        "approved_at": to_utc_iso(req.approved_at, assume_local=True) if req.approved_at else None,
        "approval_comments": req.approval_comments,
        "created_at": to_utc_iso(req.created_at) if req.created_at else None,
        "updated_at": to_utc_iso(req.updated_at) if req.updated_at else None,
        "main_summary": main_summary,
        "items": items,
    }


@router.get("/material-requests")
async def list_material_requests(
    status_filter: str = "all",
    warehouse_id: Optional[int] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    try:
        skip = int(skip or 0)
    except Exception:
        skip = 0
    skip = max(0, skip)

    try:
        limit = int(limit or 50)
    except Exception:
        limit = 50
    limit = max(1, min(limit, 200))

    query = db.query(MaterialRequest).options(
        joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
        joinedload(MaterialRequest.warehouse),
        joinedload(MaterialRequest.requester),
    )

    is_warehouse_side = getattr(current_user, "role", None) in {"admin", "warehouse_manager"}
    if is_warehouse_side:
        managed_ids = _get_managed_warehouse_ids(db, current_user)
        if managed_ids is not None:
            query = query.filter(MaterialRequest.warehouse_id.in_(list(managed_ids)))
    else:
        query = query.filter(MaterialRequest.requester_id == current_user.id)

    if status_filter and status_filter != "all":
        try:
            status_enum = MaterialRequestStatusEnum(str(status_filter))
        except Exception:
            raise HTTPException(status_code=400, detail="status_filter 参数不合法")
        query = query.filter(MaterialRequest.status == status_enum)
    if warehouse_id:
        query = query.filter(MaterialRequest.warehouse_id == warehouse_id)
    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        query = query.filter(or_(MaterialRequest.request_no.like(like), MaterialRequest.notes.like(like)))

    total = query.count()
    records = (
        query.order_by(desc(MaterialRequest.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {"records": [_serialize_material_request(db, r) for r in records], "total": total}


@router.post("/material-requests")
async def create_material_request(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    warehouse_id = payload.get("warehouse_id")
    requester_id = payload.get("requester_id") if isinstance(payload, dict) else None
    items = payload.get("items") if isinstance(payload, dict) else []
    notes = (payload.get("notes") or "").strip() if isinstance(payload, dict) else ""

    try:
        warehouse_id = int(warehouse_id)
    except Exception:
        raise HTTPException(status_code=400, detail="请选择仓库")
    _ensure_active_warehouse(db, warehouse_id)

    # 支持仓库侧“代他人创建申请单”
    if requester_id is None or str(requester_id).strip() == "":
        requester_id = current_user.id
    try:
        requester_id = int(requester_id)
    except Exception:
        raise HTTPException(status_code=400, detail="请选择申请人")
    if requester_id <= 0:
        raise HTTPException(status_code=400, detail="请选择申请人")

    if requester_id != current_user.id:
        _ensure_stock_operator(current_user)
        managed_ids = _get_managed_warehouse_ids(db, current_user)
        if managed_ids is not None and warehouse_id not in managed_ids:
            raise HTTPException(status_code=403, detail="无权限为该仓库代创建申请单")

        requester_user = db.query(User).filter(User.id == requester_id).first()
        if not requester_user or not bool(getattr(requester_user, "is_active", True)):
            raise HTTPException(status_code=400, detail="申请人不存在或已禁用")

    merged_items = _merge_request_items(items)
    if not merged_items:
        raise HTTPException(status_code=400, detail="请至少添加一条明细")

    # 校验物料存在
    equipment_ids = [int(x["equipment_id"]) for x in merged_items]
    eq_rows = db.query(Equipment.id).filter(
        Equipment.id.in_(equipment_ids),
        Equipment.status == EquipmentStatusEnum.ACTIVE,
    ).all()
    exists = {int(r[0]) for r in eq_rows}
    missing = [eid for eid in equipment_ids if eid not in exists]
    if missing:
        raise HTTPException(status_code=400, detail="物料不存在或已停用")

    req = MaterialRequest(
        id=uuid.uuid4().hex,
        request_no=_build_request_no("REQ", current_user.id),
        warehouse_id=warehouse_id,
        requester_id=requester_id,
        status=MaterialRequestStatusEnum.DRAFT,
        notes=notes or None,
    )
    db.add(req)
    db.flush()

    for row in merged_items:
        db.add(
            MaterialRequestItem(
                request_id=req.id,
                equipment_id=int(row["equipment_id"]),
                requested_qty=int(row["quantity"]),
                approved_qty=0,
                issued_qty=0,
            )
        )

    db.commit()

    full = (
        db.query(MaterialRequest)
        .options(
            joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
            joinedload(MaterialRequest.warehouse),
            joinedload(MaterialRequest.requester),
        )
        .filter(MaterialRequest.id == req.id)
        .first()
    )
    return {"request": _serialize_material_request(db, full)}


@router.get("/material-requests/{request_id}")
async def get_material_request_detail(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    req = (
        db.query(MaterialRequest)
        .options(
            joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
            joinedload(MaterialRequest.warehouse),
            joinedload(MaterialRequest.requester),
        )
        .filter(MaterialRequest.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="申请单不存在")

    is_warehouse_side = getattr(current_user, "role", None) in {"admin", "warehouse_manager"}
    if not is_warehouse_side and req.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限查看该申请单")
    if is_warehouse_side:
        managed_ids = _get_managed_warehouse_ids(db, current_user)
        if managed_ids is not None and req.warehouse_id not in managed_ids:
            raise HTTPException(status_code=403, detail="无权限查看该仓库的申请单")

    return {"request": _serialize_material_request(db, req)}


@router.patch("/material-requests/{request_id}")
@router.put("/material-requests/{request_id}")
async def update_material_request(
    request_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    req = db.query(MaterialRequest).filter(MaterialRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请单不存在")
    if _enum_value(req.status) != MaterialRequestStatusEnum.DRAFT.value:
        raise HTTPException(status_code=400, detail="仅草稿可编辑")

    is_warehouse_side = getattr(current_user, "role", None) in {"admin", "warehouse_manager"}
    if not is_warehouse_side and req.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限编辑该申请单")

    warehouse_id = payload.get("warehouse_id") if isinstance(payload, dict) else None
    notes = (payload.get("notes") or "").strip() if isinstance(payload, dict) else ""
    items = payload.get("items") if isinstance(payload, dict) else []

    try:
        warehouse_id = int(warehouse_id)
    except Exception:
        raise HTTPException(status_code=400, detail="请选择仓库")
    _ensure_active_warehouse(db, warehouse_id)
    if is_warehouse_side and req.requester_id != current_user.id:
        managed_ids = _get_managed_warehouse_ids(db, current_user)
        if managed_ids is not None and warehouse_id not in managed_ids:
            raise HTTPException(status_code=403, detail="无权限编辑该仓库的申请单")

    merged_items = _merge_request_items(items)
    if not merged_items:
        raise HTTPException(status_code=400, detail="请至少添加一条明细")

    equipment_ids = [int(x["equipment_id"]) for x in merged_items]
    eq_rows = db.query(Equipment.id).filter(
        Equipment.id.in_(equipment_ids),
        Equipment.status == EquipmentStatusEnum.ACTIVE,
    ).all()
    exists = {int(r[0]) for r in eq_rows}
    if len(exists) != len(set(equipment_ids)):
        raise HTTPException(status_code=400, detail="物料不存在或已停用")

    req.warehouse_id = warehouse_id
    req.notes = notes or None

    # 直接重建明细（草稿态不会产生已批准/已发放）
    db.query(MaterialRequestItem).filter(MaterialRequestItem.request_id == req.id).delete()
    db.flush()
    for row in merged_items:
        db.add(
            MaterialRequestItem(
                request_id=req.id,
                equipment_id=int(row["equipment_id"]),
                requested_qty=int(row["quantity"]),
                approved_qty=0,
                issued_qty=0,
            )
        )

    db.commit()

    full = (
        db.query(MaterialRequest)
        .options(
            joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
            joinedload(MaterialRequest.warehouse),
            joinedload(MaterialRequest.requester),
        )
        .filter(MaterialRequest.id == req.id)
        .first()
    )
    return {"request": _serialize_material_request(db, full)}


@router.post("/material-requests/{request_id}/submit")
async def submit_material_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    req = db.query(MaterialRequest).options(joinedload(MaterialRequest.items)).filter(MaterialRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请单不存在")
    if _enum_value(req.status) != MaterialRequestStatusEnum.DRAFT.value:
        raise HTTPException(status_code=400, detail="当前状态不可提交")
    if req.requester_id != current_user.id:
        # 允许仓库侧代提交（兜底）
        is_warehouse_side = getattr(current_user, "role", None) in {"admin", "warehouse_manager"}
        if not is_warehouse_side:
            raise HTTPException(status_code=403, detail="无权限提交该申请单")
        managed_ids = _get_managed_warehouse_ids(db, current_user)
        if managed_ids is not None and req.warehouse_id not in managed_ids:
            raise HTTPException(status_code=403, detail="无权限提交该仓库的申请单")

    req.submitted_at = datetime.now()
    req.status = MaterialRequestStatusEnum.SUBMITTED

    settings = _get_flow_settings(db)
    if not settings.get("request_requires_approval", True):
        # 提交即自动批准（不占用库存）
        for it in req.items or []:
            it.approved_qty = int(getattr(it, "requested_qty", 0) or 0)
        req.status = MaterialRequestStatusEnum.APPROVED
        req.approved_at = datetime.now()
        req.approved_by = None
        req.approval_comments = "系统自动批准（无需仓库审批）"

    db.commit()

    full = (
        db.query(MaterialRequest)
        .options(
            joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
            joinedload(MaterialRequest.warehouse),
            joinedload(MaterialRequest.requester),
        )
        .filter(MaterialRequest.id == req.id)
        .first()
    )
    return {"request": _serialize_material_request(db, full)}


@router.post("/material-requests/{request_id}/cancel")
async def cancel_material_request(
    request_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    reason = (payload.get("reason") or "").strip() if isinstance(payload, dict) else ""

    req = db.query(MaterialRequest).filter(MaterialRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请单不存在")
    if _enum_value(req.status) not in {MaterialRequestStatusEnum.DRAFT.value, MaterialRequestStatusEnum.SUBMITTED.value}:
        raise HTTPException(status_code=400, detail="当前状态不可取消")

    is_warehouse_side = getattr(current_user, "role", None) in {"admin", "warehouse_manager"}
    if not is_warehouse_side and req.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限取消该申请单")
    if is_warehouse_side and req.requester_id != current_user.id:
        managed_ids = _get_managed_warehouse_ids(db, current_user)
        if managed_ids is not None and req.warehouse_id not in managed_ids:
            raise HTTPException(status_code=403, detail="无权限取消该仓库的申请单")

    req.status = MaterialRequestStatusEnum.CANCELED
    if reason:
        req.approval_comments = reason
    db.commit()
    return {"message": "已取消", "status": _enum_value(req.status)}


@router.post("/material-requests/{request_id}/approve")
async def approve_material_request(
    request_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_stock_operator(current_user)

    req = db.query(MaterialRequest).options(joinedload(MaterialRequest.items)).filter(MaterialRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请单不存在")
    if _enum_value(req.status) != MaterialRequestStatusEnum.SUBMITTED.value:
        raise HTTPException(status_code=400, detail="当前状态不可审批")
    managed_ids = _get_managed_warehouse_ids(db, current_user)
    if managed_ids is not None and req.warehouse_id not in managed_ids:
        raise HTTPException(status_code=403, detail="无权限审批该仓库的申请单")

    items_payload = payload.get("items") if isinstance(payload, dict) else []
    comments = (payload.get("comments") or "").strip() if isinstance(payload, dict) else ""

    approved_map: Dict[int, int] = {}
    for row in items_payload or []:
        if not isinstance(row, dict):
            continue
        try:
            eid = int(row.get("equipment_id"))
            qty = int(row.get("approved_qty") or 0)
        except Exception:
            continue
        if eid <= 0 or qty < 0:
            continue
        approved_map[eid] = qty

    if not approved_map:
        raise HTTPException(status_code=400, detail="审批明细不能为空")

    any_positive = False
    all_full = True
    for it in req.items or []:
        requested = int(getattr(it, "requested_qty", 0) or 0)
        approved = int(approved_map.get(int(it.equipment_id), 0) or 0)
        if approved > requested:
            raise HTTPException(status_code=400, detail="批准数量不能超过申请数量")
        it.approved_qty = approved
        if approved > 0:
            any_positive = True
        if approved != requested:
            all_full = False

    if not any_positive:
        raise HTTPException(status_code=400, detail="全部批准数量为0，请使用驳回")

    req.status = MaterialRequestStatusEnum.APPROVED if all_full else MaterialRequestStatusEnum.PARTIALLY_APPROVED
    req.approved_by = current_user.id
    req.approved_at = datetime.now()
    req.approval_comments = comments or None
    db.commit()

    full = (
        db.query(MaterialRequest)
        .options(
            joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
            joinedload(MaterialRequest.warehouse),
            joinedload(MaterialRequest.requester),
        )
        .filter(MaterialRequest.id == req.id)
        .first()
    )
    return {"request": _serialize_material_request(db, full)}


@router.post("/material-requests/{request_id}/reject")
async def reject_material_request(
    request_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_stock_operator(current_user)

    reason = (payload.get("reason") or "").strip() if isinstance(payload, dict) else ""
    if not reason:
        raise HTTPException(status_code=400, detail="请填写驳回原因")

    req = db.query(MaterialRequest).filter(MaterialRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请单不存在")
    if _enum_value(req.status) != MaterialRequestStatusEnum.SUBMITTED.value:
        raise HTTPException(status_code=400, detail="当前状态不可驳回")
    managed_ids = _get_managed_warehouse_ids(db, current_user)
    if managed_ids is not None and req.warehouse_id not in managed_ids:
        raise HTTPException(status_code=403, detail="无权限驳回该仓库的申请单")

    req.status = MaterialRequestStatusEnum.REJECTED
    req.approved_by = current_user.id
    req.approved_at = datetime.now()
    req.approval_comments = reason
    db.commit()
    return {"message": "已驳回", "status": _enum_value(req.status)}


def _serialize_issue_draft(db: Session, draft: IssueDraft) -> dict:
    req = draft.request
    request_payload = _serialize_material_request(db, req) if req else None

    serials = []
    for s in draft.serials or []:
        serials.append(
            {
                "id": s.id,
                "equipment_id": s.equipment_id,
                "equipment_instance_id": s.equipment_instance_id,
                "serial_number": s.serial_number,
                "status": _enum_value(s.status),
                "scanned_at": to_utc_iso(s.scanned_at, assume_local=True) if s.scanned_at else None,
                "confirmed_at": to_utc_iso(s.confirmed_at, assume_local=True) if s.confirmed_at else None,
                "confirmed_transaction_id": getattr(s, "confirmed_transaction_id", None),
            }
        )

    aux_items = []
    for it in draft.items or []:
        eq = it.equipment
        pending_qty = max(int(getattr(it, "planned_qty", 0) or 0) - int(getattr(it, "confirmed_qty", 0) or 0), 0)
        aux_items.append(
            {
                "id": it.id,
                "equipment_id": it.equipment_id,
                "equipment_name": eq.equipment_name if eq else None,
                "equipment_code": eq.equipment_code if eq else None,
                "unit": getattr(eq, "unit", None) if eq else None,
                "planned_qty": int(getattr(it, "planned_qty", 0) or 0),
                "confirmed_qty": int(getattr(it, "confirmed_qty", 0) or 0),
                "pending_qty": pending_qty,
            }
        )

    return {
        "id": draft.id,
        "draft_no": draft.draft_no,
        "request_id": draft.request_id,
        "warehouse_id": draft.warehouse_id,
        "warehouse_name": draft.warehouse.warehouse_name if draft.warehouse else None,
        "requester_id": draft.requester_id,
        "status": _enum_value(draft.status),
        "submitted_at": to_utc_iso(draft.submitted_at, assume_local=True) if draft.submitted_at else None,
        "confirmed_at": to_utc_iso(draft.confirmed_at, assume_local=True) if draft.confirmed_at else None,
        "reject_reason": draft.reject_reason,
        "created_at": to_utc_iso(draft.created_at) if draft.created_at else None,
        "updated_at": to_utc_iso(draft.updated_at) if draft.updated_at else None,
        "request": request_payload,
        "serials": serials,
        "aux_items": aux_items,
    }


def _get_request_item_map(req: MaterialRequest) -> Dict[int, MaterialRequestItem]:
    mapping: Dict[int, MaterialRequestItem] = {}
    for it in req.items or []:
        try:
            mapping[int(it.equipment_id)] = it
        except Exception:
            continue
    return mapping


def _maybe_close_material_request(db: Session, req: MaterialRequest) -> None:
    """若已发放 >= 已批准（且无待确认），自动关闭申请单。"""
    pending_map = _calc_request_pending_map(db, req.id)
    for it in req.items or []:
        approved_qty = int(getattr(it, "approved_qty", 0) or 0)
        issued_qty = int(getattr(it, "issued_qty", 0) or 0)
        pending_qty = int(pending_map.get(int(it.equipment_id), 0))
        if approved_qty > issued_qty or pending_qty > 0:
            return
    req.status = MaterialRequestStatusEnum.CLOSED


def _ensure_issue_draft_access(
    db: Session,
    draft: IssueDraft,
    current_user: User,
) -> None:
    is_warehouse_side = getattr(current_user, "role", None) in {"admin", "warehouse_manager"}
    if is_warehouse_side:
        managed_ids = _get_managed_warehouse_ids(db, current_user)
        if managed_ids is not None and draft.warehouse_id not in managed_ids:
            raise HTTPException(status_code=403, detail="无权限处理该仓库的领料单")
        return
    if draft.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该领料单")


@router.post("/issue-drafts")
async def create_or_get_issue_draft(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    request_id = (payload.get("request_id") or "").strip() if isinstance(payload, dict) else ""
    if not request_id:
        raise HTTPException(status_code=400, detail="缺少 request_id")

    req = (
        db.query(MaterialRequest)
        .options(joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment), joinedload(MaterialRequest.warehouse), joinedload(MaterialRequest.requester))
        .filter(MaterialRequest.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="申请单不存在")
    if req.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="仅申请人可创建领料单")

    if _enum_value(req.status) not in {
        MaterialRequestStatusEnum.APPROVED.value,
        MaterialRequestStatusEnum.PARTIALLY_APPROVED.value,
    }:
        raise HTTPException(status_code=400, detail="申请单未批准，无法领料")
    if _enum_value(req.status) == MaterialRequestStatusEnum.CLOSED.value:
        raise HTTPException(status_code=400, detail="申请单已关闭")

    # 有剩余才允许创建
    req_payload = _serialize_material_request(db, req)
    remaining_total = sum(int(it.get("remaining_qty") or 0) for it in (req_payload.get("items") or []))
    if remaining_total <= 0:
        raise HTTPException(status_code=400, detail="无可领物料")

    # 幂等：若存在未提交的草稿，直接返回
    existing = db.query(IssueDraft).filter(
        IssueDraft.request_id == req.id,
        IssueDraft.requester_id == current_user.id,
        IssueDraft.status == IssueDraftStatusEnum.DRAFT,
    ).order_by(desc(IssueDraft.created_at)).first()
    if existing:
        full = (
            db.query(IssueDraft)
            .options(
                joinedload(IssueDraft.request).joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
                joinedload(IssueDraft.request).joinedload(MaterialRequest.warehouse),
                joinedload(IssueDraft.request).joinedload(MaterialRequest.requester),
                joinedload(IssueDraft.warehouse),
                joinedload(IssueDraft.items).joinedload(IssueDraftItem.equipment),
                joinedload(IssueDraft.serials),
            )
            .filter(IssueDraft.id == existing.id)
            .first()
        )
        return {"draft": _serialize_issue_draft(db, full)}

    draft = IssueDraft(
        id=uuid.uuid4().hex,
        draft_no=_build_request_no("ISD", current_user.id),
        request_id=req.id,
        warehouse_id=req.warehouse_id,
        requester_id=current_user.id,
        status=IssueDraftStatusEnum.DRAFT,
    )
    db.add(draft)
    db.flush()

    # 预创建辅料行（便于前端直接编辑 planned_qty）
    for it in req.items or []:
        eq = it.equipment
        if not eq or _enum_value(eq.category) != EquipmentCategoryEnum.AUXILIARY.value:
            continue
        db.add(
            IssueDraftItem(
                draft_id=draft.id,
                equipment_id=int(it.equipment_id),
                planned_qty=0,
                confirmed_qty=0,
            )
        )

    db.commit()

    full = (
        db.query(IssueDraft)
        .options(
            joinedload(IssueDraft.request).joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
            joinedload(IssueDraft.request).joinedload(MaterialRequest.warehouse),
            joinedload(IssueDraft.request).joinedload(MaterialRequest.requester),
            joinedload(IssueDraft.warehouse),
            joinedload(IssueDraft.items).joinedload(IssueDraftItem.equipment),
            joinedload(IssueDraft.serials),
        )
        .filter(IssueDraft.id == draft.id)
        .first()
    )
    return {"draft": _serialize_issue_draft(db, full)}


@router.get("/issue-drafts")
async def list_issue_drafts(
    status_filter: str = "pending_confirm",
    warehouse_id: Optional[int] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_stock_operator(current_user)

    try:
        skip = int(skip or 0)
    except Exception:
        skip = 0
    skip = max(0, skip)

    try:
        limit = int(limit or 50)
    except Exception:
        limit = 50
    limit = max(1, min(limit, 200))

    query = db.query(IssueDraft).options(
        joinedload(IssueDraft.warehouse),
        joinedload(IssueDraft.request).joinedload(MaterialRequest.requester),
    )

    managed_ids = _get_managed_warehouse_ids(db, current_user)
    if managed_ids is not None:
        query = query.filter(IssueDraft.warehouse_id.in_(list(managed_ids)))

    if status_filter and status_filter != "all":
        try:
            status_enum = IssueDraftStatusEnum(str(status_filter))
        except Exception:
            raise HTTPException(status_code=400, detail="status_filter 参数不合法")
        query = query.filter(IssueDraft.status == status_enum)
    if warehouse_id:
        query = query.filter(IssueDraft.warehouse_id == warehouse_id)

    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        query = query.join(IssueDraft.request).filter(
            or_(IssueDraft.draft_no.like(like), MaterialRequest.request_no.like(like))
        )

    total = query.count()
    rows = query.order_by(desc(IssueDraft.created_at)).offset(skip).limit(limit).all()

    records = []
    for d in rows:
        req = d.request
        records.append(
            {
                "id": d.id,
                "draft_no": d.draft_no,
                "request_id": d.request_id,
                "request_no": req.request_no if req else None,
                "warehouse_id": d.warehouse_id,
                "warehouse_name": d.warehouse.warehouse_name if d.warehouse else None,
                "requester_id": d.requester_id,
                "requester_name": (
                    req.requester.full_name
                    if req and req.requester and req.requester.full_name
                    else (req.requester.username if req and req.requester else None)
                ),
                "status": _enum_value(d.status),
                "submitted_at": to_utc_iso(d.submitted_at, assume_local=True) if d.submitted_at else None,
                "created_at": to_utc_iso(d.created_at) if d.created_at else None,
            }
        )

    return {"records": records, "total": total}


@router.get("/issue-drafts/{draft_id}")
async def get_issue_draft_detail(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    draft = (
        db.query(IssueDraft)
        .options(
            joinedload(IssueDraft.request).joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
            joinedload(IssueDraft.request).joinedload(MaterialRequest.warehouse),
            joinedload(IssueDraft.request).joinedload(MaterialRequest.requester),
            joinedload(IssueDraft.warehouse),
            joinedload(IssueDraft.items).joinedload(IssueDraftItem.equipment),
            joinedload(IssueDraft.serials),
        )
        .filter(IssueDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="领料单不存在")

    _ensure_issue_draft_access(db, draft, current_user)

    return {"draft": _serialize_issue_draft(db, draft)}


@router.post("/issue-drafts/{draft_id}/scan-main")
async def issue_draft_scan_main_device(
    draft_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    barcode = ""
    sn = ""
    try:
        _ensure_material_request_enabled(db)
        _ensure_not_surveyor(current_user)

        draft = (
            db.query(IssueDraft)
            .options(
                joinedload(IssueDraft.request).joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
                joinedload(IssueDraft.request).joinedload(MaterialRequest.warehouse),
                joinedload(IssueDraft.request).joinedload(MaterialRequest.requester),
                joinedload(IssueDraft.warehouse),
                joinedload(IssueDraft.items).joinedload(IssueDraftItem.equipment),
                joinedload(IssueDraft.serials),
            )
            .filter(IssueDraft.id == draft_id)
            .first()
        )
        if not draft:
            raise HTTPException(status_code=404, detail="领料单不存在")
        _ensure_issue_draft_access(db, draft, current_user)

        if _enum_value(draft.status) != IssueDraftStatusEnum.DRAFT.value:
            raise HTTPException(status_code=400, detail="当前状态不可扫码")

        barcode = (payload.get("barcode") or "").strip() if isinstance(payload, dict) else ""
        parsed_barcode = payload.get("parsed_barcode") if isinstance(payload, dict) else None
        sn = _extract_sn_from_scan(barcode, parsed_barcode)
        if not sn:
            raise HTTPException(status_code=400, detail="条码不能为空")

        instance = db.query(EquipmentInstance).filter(EquipmentInstance.serial_number == sn).first()
        if not instance:
            raise HTTPException(
                status_code=404,
                detail=f"未找到该SN对应的设备实例：{sn}。请确认扫描的是设备SN，或联系管理员导入库存。",
            )
        if bool(getattr(instance, "is_voided", False)):
            raise HTTPException(status_code=400, detail="该SN实例已撤销")
        if _enum_value(instance.status) != InventoryStatusEnum.IN_STOCK.value:
            raise HTTPException(
                status_code=400,
                detail=f"设备当前状态为 {_enum_value(instance.status)}，不在库中，无法领料",
            )
        if instance.warehouse_id != draft.warehouse_id:
            device_wh = (
                instance.warehouse.warehouse_name
                if getattr(instance, "warehouse", None) and getattr(instance.warehouse, "warehouse_name", None)
                else str(instance.warehouse_id or "-")
            )
            draft_wh = (
                draft.warehouse.warehouse_name
                if getattr(draft, "warehouse", None) and getattr(draft.warehouse, "warehouse_name", None)
                else str(draft.warehouse_id or "-")
            )
            raise HTTPException(
                status_code=400,
                detail=f"设备不在申请仓库，无法领料（设备仓库：{device_wh}，申请仓库：{draft_wh}）",
            )

        eq = instance.equipment
        if not eq or _enum_value(eq.category) != EquipmentCategoryEnum.MAIN_DEVICE.value:
            raise HTTPException(status_code=400, detail="该SN不是主设备，无法加入领料单")

        req = draft.request
        req_item_map = _get_request_item_map(req)
        req_item = req_item_map.get(int(eq.id))
        if not req_item:
            eq_name = getattr(eq, "equipment_name", None) or getattr(eq, "equipment_code", None) or "未知型号"
            raise HTTPException(status_code=400, detail=f"该SN对应型号【{eq_name}】不在申请单内，无法领料")

        # 是否超出可领上限
        pending_map = _calc_request_pending_map(db, req.id)
        approved_qty = int(getattr(req_item, "approved_qty", 0) or 0)
        issued_qty = int(getattr(req_item, "issued_qty", 0) or 0)
        pending_qty = int(pending_map.get(int(eq.id), 0))
        remaining = max(approved_qty - issued_qty - pending_qty, 0)
        if remaining <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"该物料已无剩余可领数量（已审批{approved_qty}，已出库{issued_qty}，其他领料单占用{pending_qty}）",
            )

        # 防重复：同草稿内 unique constraint
        dup = db.query(IssueDraftSerial).filter(
            IssueDraftSerial.draft_id == draft.id,
            IssueDraftSerial.serial_number == sn,
        ).first()
        if dup:
            return {"draft": _serialize_issue_draft(db, draft)}

        # 防冲突：同SN不允许同时出现在多个未完成的领料单
        conflict = (
            db.query(IssueDraftSerial)
            .join(IssueDraft, IssueDraftSerial.draft_id == IssueDraft.id)
            .filter(
                IssueDraftSerial.serial_number == sn,
                IssueDraftSerial.status == IssueDraftSerialStatusEnum.PENDING,
                IssueDraft.status.in_(
                    [
                        IssueDraftStatusEnum.DRAFT,
                        IssueDraftStatusEnum.PENDING_CONFIRM,
                        IssueDraftStatusEnum.PARTIALLY_CONFIRMED,
                    ]
                ),
                IssueDraft.id != draft.id,
            )
            .first()
        )
        if conflict:
            other = db.query(IssueDraft).filter(IssueDraft.id == conflict.draft_id).first()
            other_no = other.draft_no if other else conflict.draft_id
            raise HTTPException(status_code=400, detail=f"该SN已在其他领料单【{other_no}】中待确认，无法重复添加")

        db.add(
            IssueDraftSerial(
                draft_id=draft.id,
                equipment_instance_id=instance.id,
                equipment_id=instance.equipment_id,
                serial_number=sn,
                status=IssueDraftSerialStatusEnum.PENDING,
                scanned_by=current_user.id,
                scanned_at=datetime.now(),
            )
        )
        db.commit()

        fresh = (
            db.query(IssueDraft)
            .options(
                joinedload(IssueDraft.request).joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
                joinedload(IssueDraft.request).joinedload(MaterialRequest.warehouse),
                joinedload(IssueDraft.request).joinedload(MaterialRequest.requester),
                joinedload(IssueDraft.warehouse),
                joinedload(IssueDraft.items).joinedload(IssueDraftItem.equipment),
                joinedload(IssueDraft.serials),
            )
            .filter(IssueDraft.id == draft.id)
            .first()
        )
        return {"draft": _serialize_issue_draft(db, fresh)}
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        error_id = uuid.uuid4().hex[:8]
        logger.exception(
            "issue_draft_scan_main_device integrity_error error_id=%s draft_id=%s sn=%s user_id=%s",
            error_id,
            draft_id,
            sn,
            getattr(current_user, "id", None),
        )
        raise HTTPException(
            status_code=409,
            detail=f"扫码添加SN发生冲突（可能是重复提交或并发操作），请刷新后重试（错误编号：{error_id}）",
        )
    except Exception:
        db.rollback()
        error_id = uuid.uuid4().hex[:8]
        logger.exception(
            "issue_draft_scan_main_device failed error_id=%s draft_id=%s barcode=%s sn=%s user_id=%s",
            error_id,
            draft_id,
            barcode,
            sn,
            getattr(current_user, "id", None),
        )
        raise HTTPException(
            status_code=500,
            detail=f"系统异常，扫码添加SN失败，请稍后重试或联系管理员（错误编号：{error_id}）",
        )


@router.delete("/issue-drafts/{draft_id}/serials/{serial_id}")
async def issue_draft_delete_serial(
    draft_id: str,
    serial_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    draft = db.query(IssueDraft).filter(IssueDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="领料单不存在")
    _ensure_issue_draft_access(db, draft, current_user)
    if _enum_value(draft.status) != IssueDraftStatusEnum.DRAFT.value:
        raise HTTPException(status_code=400, detail="当前状态不可删除SN")

    serial = db.query(IssueDraftSerial).filter(IssueDraftSerial.id == serial_id, IssueDraftSerial.draft_id == draft.id).first()
    if not serial:
        raise HTTPException(status_code=404, detail="SN记录不存在")
    if _enum_value(serial.status) != IssueDraftSerialStatusEnum.PENDING.value:
        raise HTTPException(status_code=400, detail="该SN已确认，不能删除")

    db.delete(serial)
    db.commit()
    return {"message": "已删除"}


@router.put("/issue-drafts/{draft_id}/aux-items")
async def issue_draft_update_aux_items(
    draft_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    draft = (
        db.query(IssueDraft)
        .options(
            joinedload(IssueDraft.request).joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
            joinedload(IssueDraft.request).joinedload(MaterialRequest.warehouse),
            joinedload(IssueDraft.request).joinedload(MaterialRequest.requester),
            joinedload(IssueDraft.warehouse),
            joinedload(IssueDraft.items).joinedload(IssueDraftItem.equipment),
            joinedload(IssueDraft.serials),
        )
        .filter(IssueDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="领料单不存在")
    _ensure_issue_draft_access(db, draft, current_user)
    if _enum_value(draft.status) != IssueDraftStatusEnum.DRAFT.value:
        raise HTTPException(status_code=400, detail="当前状态不可编辑辅料")

    items_payload = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items_payload, list):
        raise HTTPException(status_code=400, detail="items 参数不合法")

    req = draft.request
    req_item_map = _get_request_item_map(req)
    pending_map = _calc_request_pending_map(db, req.id)

    # 允许仅更新部分行：未传入的保持不变
    input_map: Dict[int, int] = {}
    for row in items_payload:
        if not isinstance(row, dict):
            continue
        try:
            eid = int(row.get("equipment_id"))
            planned = int(row.get("planned_qty") or 0)
        except Exception:
            continue
        if eid <= 0 or planned < 0:
            continue
        input_map[eid] = planned

    for row in draft.items or []:
        eid = int(row.equipment_id)
        if eid not in input_map:
            continue
        planned_new = int(input_map[eid])
        req_item = req_item_map.get(eid)
        if not req_item:
            continue
        eq = req_item.equipment
        if not eq or _enum_value(eq.category) != EquipmentCategoryEnum.AUXILIARY.value:
            continue

        approved_qty = int(getattr(req_item, "approved_qty", 0) or 0)
        issued_qty = int(getattr(req_item, "issued_qty", 0) or 0)

        current_pending = max(int(getattr(row, "planned_qty", 0) or 0) - int(getattr(row, "confirmed_qty", 0) or 0), 0)
        global_pending = int(pending_map.get(eid, 0))
        pending_other = max(global_pending - current_pending, 0)
        cap = max(approved_qty - issued_qty - pending_other, 0)

        if planned_new > cap:
            raise HTTPException(status_code=400, detail="辅料数量超过可领上限")

        row.planned_qty = planned_new

    db.commit()

    fresh = (
        db.query(IssueDraft)
        .options(
            joinedload(IssueDraft.request).joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
            joinedload(IssueDraft.request).joinedload(MaterialRequest.warehouse),
            joinedload(IssueDraft.request).joinedload(MaterialRequest.requester),
            joinedload(IssueDraft.warehouse),
            joinedload(IssueDraft.items).joinedload(IssueDraftItem.equipment),
            joinedload(IssueDraft.serials),
        )
        .filter(IssueDraft.id == draft.id)
        .first()
    )
    return {"draft": _serialize_issue_draft(db, fresh)}


@router.post("/issue-drafts/{draft_id}/submit")
async def issue_draft_submit(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    draft = (
        db.query(IssueDraft)
        .options(
            joinedload(IssueDraft.request).joinedload(MaterialRequest.items),
            joinedload(IssueDraft.items),
            joinedload(IssueDraft.serials),
        )
        .filter(IssueDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="领料单不存在")
    _ensure_issue_draft_access(db, draft, current_user)
    if _enum_value(draft.status) != IssueDraftStatusEnum.DRAFT.value:
        raise HTTPException(status_code=400, detail="当前状态不可提交")

    has_main = any(_enum_value(s.status) == IssueDraftSerialStatusEnum.PENDING.value for s in (draft.serials or []))
    has_aux = any(int(getattr(it, "planned_qty", 0) or 0) > int(getattr(it, "confirmed_qty", 0) or 0) for it in (draft.items or []))
    if not has_main and not has_aux:
        raise HTTPException(status_code=400, detail="请至少选择1个SN或填写辅料数量")

    settings = _get_flow_settings(db)
    draft.submitted_at = datetime.now()

    if settings.get("issue_requires_warehouse_confirm", True):
        draft.status = IssueDraftStatusEnum.PENDING_CONFIRM
        db.commit()
        return {"status": _enum_value(draft.status)}

    # 不需要仓库确认：提交即出库（自动确认全部待确认项）
    # 将当前用户视为“出库操作人”
    return await _confirm_issue_draft_impl(
        draft_id=draft_id,
        payload={
            "serial_ids": [
                int(s.id)
                for s in (draft.serials or [])
                if _enum_value(s.status) == IssueDraftSerialStatusEnum.PENDING.value
            ],
            "aux_items": [
                {
                    "equipment_id": int(it.equipment_id),
                    "quantity": max(
                        int(getattr(it, "planned_qty", 0) or 0) - int(getattr(it, "confirmed_qty", 0) or 0),
                        0,
                    ),
                }
                for it in (draft.items or [])
                if max(
                    int(getattr(it, "planned_qty", 0) or 0) - int(getattr(it, "confirmed_qty", 0) or 0),
                    0,
                )
                > 0
            ],
            "notes": "无需仓库确认，提交即出库",
        },
        db=db,
        current_user=current_user,
        skip_role_check=True,
    )


@router.post("/issue-drafts/{draft_id}/cancel")
async def issue_draft_cancel(
    draft_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_not_surveyor(current_user)

    reason = (payload.get("reason") or "").strip() if isinstance(payload, dict) else ""

    draft = db.query(IssueDraft).filter(IssueDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="领料单不存在")
    _ensure_issue_draft_access(db, draft, current_user)

    if _enum_value(draft.status) not in {IssueDraftStatusEnum.DRAFT.value, IssueDraftStatusEnum.PENDING_CONFIRM.value}:
        raise HTTPException(status_code=400, detail="当前状态不可取消")

    # 若已发生部分确认，则禁止取消
    has_any_confirmed = (
        db.query(IssueDraftSerial.id)
        .filter(IssueDraftSerial.draft_id == draft.id, IssueDraftSerial.status == IssueDraftSerialStatusEnum.CONFIRMED)
        .first()
        is not None
    )
    if has_any_confirmed:
        raise HTTPException(status_code=400, detail="已发生部分确认，不能取消")

    draft.status = IssueDraftStatusEnum.CANCELED
    if reason and not draft.reject_reason:
        draft.reject_reason = reason
    db.commit()
    return {"message": "已取消", "status": _enum_value(draft.status)}


def _collect_stock_shortage(db: Session, warehouse_id: int, requirements: Dict[int, int]) -> List[dict]:
    shortages: List[dict] = []
    if not requirements:
        return shortages

    eqs = (
        db.query(Equipment)
        .filter(Equipment.id.in_(list(requirements.keys())))
        .all()
    )
    eq_map = {int(e.id): e for e in eqs}

    for equipment_id, required_qty in requirements.items():
        inv = db.query(Inventory).filter(
            and_(Inventory.warehouse_id == warehouse_id, Inventory.equipment_id == equipment_id)
        ).first()
        available = int(inv.available_stock or 0) if inv else 0
        current_stock = int(inv.current_stock or 0) if inv else 0
        if available < required_qty or current_stock < required_qty:
            eq = eq_map.get(int(equipment_id))
            shortages.append(
                {
                    "equipment_name": eq.equipment_name if eq else str(equipment_id),
                    "required": int(required_qty),
                    "available": available,
                    "current_stock": current_stock,
                }
            )

    return shortages


async def _confirm_issue_draft_impl(
    draft_id: str,
    payload: dict,
    db: Session,
    current_user: User,
    skip_role_check: bool = False,
):
    _ensure_material_request_enabled(db)
    if not skip_role_check:
        _ensure_stock_operator(current_user)
    _ensure_not_surveyor(current_user)

    draft = (
        db.query(IssueDraft)
        .options(
            joinedload(IssueDraft.request).joinedload(MaterialRequest.items).joinedload(MaterialRequestItem.equipment),
            joinedload(IssueDraft.request).joinedload(MaterialRequest.warehouse),
            joinedload(IssueDraft.request).joinedload(MaterialRequest.requester),
            joinedload(IssueDraft.warehouse),
            joinedload(IssueDraft.items).joinedload(IssueDraftItem.equipment),
            joinedload(IssueDraft.serials),
        )
        .filter(IssueDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="领料单不存在")

    if not skip_role_check:
        _ensure_issue_draft_access(db, draft, current_user)
    else:
        # 自助模式仍需是申请人
        if draft.requester_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权限确认出库")

    allowed_status = {IssueDraftStatusEnum.PENDING_CONFIRM.value, IssueDraftStatusEnum.PARTIALLY_CONFIRMED.value}
    if skip_role_check:
        allowed_status.add(IssueDraftStatusEnum.DRAFT.value)
    if _enum_value(draft.status) not in allowed_status:
        raise HTTPException(status_code=400, detail="当前状态不可确认出库")

    req = draft.request
    managed_ids = _get_managed_warehouse_ids(db, current_user)
    if not skip_role_check and managed_ids is not None and draft.warehouse_id not in managed_ids:
        raise HTTPException(status_code=403, detail="无权限处理该仓库的领料单")

    serial_ids = payload.get("serial_ids") if isinstance(payload, dict) else []
    aux_items_payload = payload.get("aux_items") if isinstance(payload, dict) else []
    notes = (payload.get("notes") or "").strip() if isinstance(payload, dict) else ""

    serial_ids_set = set()
    for sid in serial_ids or []:
        try:
            serial_ids_set.add(int(sid))
        except Exception:
            continue

    aux_confirm_map: Dict[int, int] = {}
    for row in aux_items_payload or []:
        if not isinstance(row, dict):
            continue
        try:
            eid = int(row.get("equipment_id"))
            qty = int(row.get("quantity") or 0)
        except Exception:
            continue
        if eid <= 0 or qty <= 0:
            continue
        aux_confirm_map[eid] = aux_confirm_map.get(eid, 0) + qty

    if not serial_ids_set and not aux_confirm_map:
        raise HTTPException(status_code=400, detail="请至少确认1个SN或辅料数量")

    # 构建本次确认所需数量（按 equipment_id 汇总）
    requirements: Dict[int, int] = {}

    serial_by_id = {int(s.id): s for s in (draft.serials or [])}
    serials_to_confirm: List[IssueDraftSerial] = []
    for sid in serial_ids_set:
        s = serial_by_id.get(int(sid))
        if not s:
            continue
        if _enum_value(s.status) != IssueDraftSerialStatusEnum.PENDING.value:
            continue
        serials_to_confirm.append(s)
        requirements[int(s.equipment_id)] = requirements.get(int(s.equipment_id), 0) + 1
    if not serials_to_confirm and not aux_confirm_map:
        raise HTTPException(status_code=400, detail="没有可确认的SN或辅料，请刷新后重试")

    draft_item_by_eid = {int(it.equipment_id): it for it in (draft.items or [])}
    for eid, qty in aux_confirm_map.items():
        row = draft_item_by_eid.get(int(eid))
        if not row:
            raise HTTPException(status_code=400, detail="辅料不在领料单中")
        pending_qty = max(int(getattr(row, "planned_qty", 0) or 0) - int(getattr(row, "confirmed_qty", 0) or 0), 0)
        if qty > pending_qty:
            raise HTTPException(status_code=400, detail="辅料确认数量不能超过待确认数量")
        requirements[int(eid)] = requirements.get(int(eid), 0) + int(qty)

    # 库存校验
    shortages = _collect_stock_shortage(db, draft.warehouse_id, requirements)
    if shortages:
        raise HTTPException(status_code=400, detail={"message": "库存不足，无法确认出库", "shortages": shortages})

    now = datetime.now()
    tx_id = uuid.uuid4().hex
    doc_no = _build_request_no("OUT", current_user.id)

    loc = {"_stock_flow_version": 2, "_source": "issue_draft_confirm", "issue_draft_id": draft.id, "request_id": draft.request_id}

    transaction = StockTransaction(
        id=tx_id,
        transaction_type=TransactionTypeEnum.STOCK_OUT,
        warehouse_id=draft.warehouse_id,
        operator_id=current_user.id,
        issued_to=draft.requester_id,
        scan_location=loc,
        document_number=doc_no,
        total_quantity=sum(int(v) for v in requirements.values()),
        notes=notes or f"领料单确认出库 - {draft.draft_no}",
    )
    db.add(transaction)

    # 逐行扣库存 + 写明细
    for equipment_id, qty in requirements.items():
        updated = (
            db.query(Inventory)
            .filter(
                Inventory.warehouse_id == draft.warehouse_id,
                Inventory.equipment_id == equipment_id,
                Inventory.current_stock >= int(qty),
                Inventory.available_stock >= int(qty),
            )
            .update(
                {
                    Inventory.current_stock: Inventory.current_stock - int(qty),
                    Inventory.available_stock: Inventory.available_stock - int(qty),
                    Inventory.allocated_stock: Inventory.allocated_stock + int(qty),
                    Inventory.last_updated_by: current_user.id,
                },
                synchronize_session=False,
            )
        )
        if updated != 1:
            db.expire_all()
            latest_shortages = _collect_stock_shortage(db, draft.warehouse_id, requirements)
            if latest_shortages:
                raise HTTPException(
                    status_code=400,
                    detail={"message": "库存不足，无法确认出库", "shortages": latest_shortages},
                )
            raise HTTPException(status_code=400, detail="库存更新失败")

    # 主设备明细：每SN一条
    for s in serials_to_confirm:
        db.add(
            StockTransactionItem(
                transaction_id=tx_id,
                equipment_instance_id=s.equipment_instance_id,
                equipment_id=s.equipment_id,
                quantity=1,
                received_qty=0,
            )
        )

        s.status = IssueDraftSerialStatusEnum.CONFIRMED
        s.confirmed_transaction_id = tx_id
        s.confirmed_at = now

        updated_inst = (
            db.query(EquipmentInstance)
            .filter(
                EquipmentInstance.id == s.equipment_instance_id,
                EquipmentInstance.equipment_id == s.equipment_id,
                or_(EquipmentInstance.is_voided.is_(False), EquipmentInstance.is_voided.is_(None)),
                EquipmentInstance.status == InventoryStatusEnum.IN_STOCK,
                EquipmentInstance.warehouse_id == draft.warehouse_id,
            )
            .update(
                {
                    EquipmentInstance.status: InventoryStatusEnum.ISSUED,
                    EquipmentInstance.issued_to: draft.requester_id,
                    EquipmentInstance.issued_date: now,
                    EquipmentInstance.warehouse_id: None,
                    EquipmentInstance.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        if updated_inst != 1:
            raise HTTPException(status_code=400, detail=f"SN当前状态不可出库：{s.serial_number}")

        # 申请单已发放+1
        req_item = db.query(MaterialRequestItem).filter(
            MaterialRequestItem.request_id == req.id,
            MaterialRequestItem.equipment_id == int(s.equipment_id),
        ).first()
        if req_item:
            req_item.issued_qty = int(getattr(req_item, "issued_qty", 0) or 0) + 1

    # 辅料明细：按设备聚合
    for eid, qty in aux_confirm_map.items():
        db.add(
            StockTransactionItem(
                transaction_id=tx_id,
                equipment_id=int(eid),
                quantity=int(qty),
                received_qty=0,
            )
        )

        row = draft_item_by_eid.get(int(eid))
        if row:
            row.confirmed_qty = int(getattr(row, "confirmed_qty", 0) or 0) + int(qty)

        req_item = db.query(MaterialRequestItem).filter(
            MaterialRequestItem.request_id == req.id,
            MaterialRequestItem.equipment_id == int(eid),
        ).first()
        if req_item:
            req_item.issued_qty = int(getattr(req_item, "issued_qty", 0) or 0) + int(qty)

    # 更新领料单状态
    any_pending_serial = any(
        _enum_value(x.status) == IssueDraftSerialStatusEnum.PENDING.value for x in (draft.serials or [])
    )
    any_pending_aux = any(
        int(getattr(it, "planned_qty", 0) or 0) > int(getattr(it, "confirmed_qty", 0) or 0)
        for it in (draft.items or [])
    )

    draft.confirmed_by = current_user.id
    draft.confirmed_at = now
    if not any_pending_serial and not any_pending_aux:
        draft.status = IssueDraftStatusEnum.CONFIRMED
    else:
        draft.status = IssueDraftStatusEnum.PARTIALLY_CONFIRMED

    # 若申请单已全部发放则关闭
    db.flush()
    _maybe_close_material_request(db, req)

    db.commit()

    return {
        "message": "确认出库成功",
        "transaction_id": tx_id,
        "document_number": doc_no,
        "draft_status": _enum_value(draft.status),
    }


@router.post("/issue-drafts/{draft_id}/confirm")
async def confirm_issue_draft(
    draft_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _confirm_issue_draft_impl(
        draft_id=draft_id,
        payload=payload,
        db=db,
        current_user=current_user,
        skip_role_check=False,
    )


@router.post("/issue-drafts/{draft_id}/reject")
async def reject_issue_draft(
    draft_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_material_request_enabled(db)
    _ensure_stock_operator(current_user)

    reason = (payload.get("reason") or "").strip() if isinstance(payload, dict) else ""
    if not reason:
        raise HTTPException(status_code=400, detail="请填写驳回原因")

    draft = db.query(IssueDraft).filter(IssueDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="领料单不存在")

    _ensure_issue_draft_access(db, draft, current_user)
    if _enum_value(draft.status) != IssueDraftStatusEnum.PENDING_CONFIRM.value:
        raise HTTPException(status_code=400, detail="当前状态不可驳回")

    # 若已发生部分确认，则禁止驳回
    has_any_confirmed = (
        db.query(IssueDraftSerial.id)
        .filter(IssueDraftSerial.draft_id == draft.id, IssueDraftSerial.status == IssueDraftSerialStatusEnum.CONFIRMED)
        .first()
        is not None
    )
    if has_any_confirmed:
        raise HTTPException(status_code=400, detail="已发生部分确认，不能驳回整单")

    draft.status = IssueDraftStatusEnum.REJECTED
    draft.reject_reason = reason
    db.commit()
    return {"message": "已驳回", "status": _enum_value(draft.status)}


@router.post("/manual-stock-out")
async def manual_stock_out(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """快速出库（无申请）：主设备按SN逐台、辅料按数量。"""
    _ensure_quick_stock_out_enabled(db)
    _ensure_stock_operator(current_user)

    warehouse_id = payload.get("warehouse_id") if isinstance(payload, dict) else None
    main_sns = payload.get("main_sns") if isinstance(payload, dict) else []
    aux_items = payload.get("aux_items") if isinstance(payload, dict) else []
    issued_to = payload.get("issued_to") if isinstance(payload, dict) else None
    notes = (payload.get("notes") or "").strip() if isinstance(payload, dict) else ""
    offline_document_id = payload.get("offline_document_id") if isinstance(payload, dict) else None
    offline_doc = _get_offline_document_for_use(db, current_user=current_user, offline_document_id=offline_document_id)

    try:
        warehouse_id = int(warehouse_id)
    except Exception:
        raise HTTPException(status_code=400, detail="请选择出库仓库")

    wh = _ensure_active_warehouse(db, warehouse_id)
    managed_ids = _get_managed_warehouse_ids(db, current_user)
    if managed_ids is not None and wh.id not in managed_ids:
        raise HTTPException(status_code=403, detail="无权限操作该仓库")

    # 领取人（必填）：必须明确选择，避免“人货不一致”
    if issued_to is None or str(issued_to).strip() == "":
        raise HTTPException(status_code=400, detail="请选择领取人")
    try:
        issued_to = int(issued_to)
    except Exception:
        raise HTTPException(status_code=400, detail="请选择领取人")
    if issued_to <= 0:
        raise HTTPException(status_code=400, detail="请选择领取人")
    issued_to_user = db.query(User).filter(User.id == issued_to).first()
    if not issued_to_user or not bool(getattr(issued_to_user, "is_active", True)):
        raise HTTPException(status_code=400, detail="领取人不存在或已禁用")

    # 主设备：SN去重
    sn_set = []
    seen = set()
    for s in main_sns or []:
        v = str(s or "").strip()
        if not v or v in seen:
            continue
        seen.add(v)
        sn_set.append(v)

    # 辅料合并
    aux_map: Dict[int, int] = {}
    for row in aux_items or []:
        if not isinstance(row, dict):
            continue
        try:
            eid = int(row.get("equipment_id"))
            qty = int(row.get("quantity") or 0)
        except Exception:
            continue
        if eid <= 0 or qty <= 0:
            continue
        aux_map[eid] = aux_map.get(eid, 0) + qty

    if not sn_set and not aux_map:
        raise HTTPException(status_code=400, detail="请至少录入1个主设备SN或辅料数量")

    requirements: Dict[int, int] = {}
    instance_rows: List[EquipmentInstance] = []
    for sn in sn_set:
        conflict = (
            db.query(IssueDraftSerial.id)
            .join(IssueDraft, IssueDraftSerial.draft_id == IssueDraft.id)
            .filter(
                IssueDraftSerial.serial_number == sn,
                IssueDraftSerial.status == IssueDraftSerialStatusEnum.PENDING,
                IssueDraft.status.in_(
                    [
                        IssueDraftStatusEnum.DRAFT,
                        IssueDraftStatusEnum.PENDING_CONFIRM,
                        IssueDraftStatusEnum.PARTIALLY_CONFIRMED,
                    ]
                ),
            )
            .first()
        )
        if conflict:
            raise HTTPException(status_code=400, detail=f"SN已在领料单待确认，无法快速出库：{sn}")

        inst = db.query(EquipmentInstance).filter(EquipmentInstance.serial_number == sn).first()
        if not inst:
            raise HTTPException(status_code=404, detail=f"未找到SN：{sn}")
        if bool(getattr(inst, "is_voided", False)):
            raise HTTPException(status_code=400, detail=f"SN已撤销：{sn}")
        if _enum_value(inst.status) != InventoryStatusEnum.IN_STOCK.value:
            raise HTTPException(status_code=400, detail=f"设备不在库中：{sn}")
        if inst.warehouse_id != warehouse_id:
            raise HTTPException(status_code=400, detail=f"设备不在所选仓库：{sn}")
        if not inst.equipment or _enum_value(inst.equipment.category) != EquipmentCategoryEnum.MAIN_DEVICE.value:
            raise HTTPException(status_code=400, detail=f"SN不是主设备：{sn}")
        instance_rows.append(inst)
        requirements[int(inst.equipment_id)] = requirements.get(int(inst.equipment_id), 0) + 1

    # 辅料校验
    if aux_map:
        eqs = db.query(Equipment).filter(Equipment.id.in_(list(aux_map.keys()))).all()
        for e in eqs:
            if _enum_value(e.category) != EquipmentCategoryEnum.AUXILIARY.value:
                raise HTTPException(status_code=400, detail="辅料明细包含非辅料物料")
        for eid, qty in aux_map.items():
            requirements[int(eid)] = requirements.get(int(eid), 0) + int(qty)

    shortages = _collect_stock_shortage(db, warehouse_id, requirements)
    if shortages:
        raise HTTPException(status_code=400, detail={"message": "库存不足，无法出库", "shortages": shortages})

    now = datetime.now()
    tx_id = uuid.uuid4().hex
    doc_no = _build_request_no("OUT", current_user.id)
    loc = {"_stock_flow_version": 2, "_source": "manual_stock_out"}

    tx = StockTransaction(
        id=tx_id,
        transaction_type=TransactionTypeEnum.STOCK_OUT,
        warehouse_id=warehouse_id,
        operator_id=current_user.id,
        issued_to=issued_to,
        offline_document_id=offline_doc.id if offline_doc else None,
        scan_location=loc,
        document_number=doc_no,
        total_quantity=sum(int(v) for v in requirements.values()),
        notes=notes or "快速出库",
    )
    db.add(tx)

    # 库存扣减
    for equipment_id, qty in requirements.items():
        inv = db.query(Inventory).filter(
            and_(Inventory.warehouse_id == warehouse_id, Inventory.equipment_id == equipment_id)
        ).first()
        if not inv:
            raise HTTPException(status_code=400, detail="库存更新失败：未找到库存记录")
        inv.current_stock -= int(qty)
        inv.available_stock -= int(qty)
        inv.allocated_stock += int(qty)
        inv.last_updated_by = current_user.id

    # 主设备明细
    for inst in instance_rows:
        db.add(
            StockTransactionItem(
                transaction_id=tx_id,
                equipment_instance_id=inst.id,
                equipment_id=inst.equipment_id,
                quantity=1,
                received_qty=0,
            )
        )
        inst.status = InventoryStatusEnum.ISSUED
        inst.issued_to = issued_to
        inst.issued_date = now
        inst.warehouse_id = None
        inst.updated_at = now

    # 辅料明细
    for eid, qty in aux_map.items():
        db.add(
            StockTransactionItem(
                transaction_id=tx_id,
                equipment_id=int(eid),
                quantity=int(qty),
                received_qty=0,
            )
        )

    db.commit()
    return {"transaction_id": tx_id, "document_number": doc_no}


def _return_reserved_maps(db: Session, out_transaction_id: str) -> tuple[Dict[int, int], set]:
    """返回：aux_reserved_by_equipment、main_reserved_instance_ids。"""
    aux_reserved: Dict[int, int] = {}
    main_reserved: set = set()

    rows = (
        db.query(StockTransaction)
        .options(joinedload(StockTransaction.transaction_items))
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
            StockTransaction.related_transaction_id == out_transaction_id,
            StockTransaction.approval_status.notin_(["rejected", "canceled"]),
        )
        .all()
    )
    for t in rows:
        for it in t.transaction_items or []:
            if it.equipment_instance_id:
                main_reserved.add(str(it.equipment_instance_id))
            else:
                try:
                    eid = int(it.equipment_id)
                    aux_reserved[eid] = aux_reserved.get(eid, 0) + int(it.quantity or 0)
                except Exception:
                    continue

    return aux_reserved, main_reserved


def _serialize_stock_out_for_return(db: Session, out_trans: StockTransaction) -> dict:
    aux_reserved, main_reserved = _return_reserved_maps(db, out_trans.id)

    items = []
    for it in out_trans.transaction_items or []:
        eq = it.equipment
        cat = _enum_value(eq.category) if eq else None
        is_main = cat == EquipmentCategoryEnum.MAIN_DEVICE.value
        serial_number = it.equipment_instance.serial_number if it.equipment_instance else None
        if is_main and not serial_number:
            pick = (
                db.query(PickupRecord)
                .filter(PickupRecord.transaction_id == out_trans.id)
                .order_by(desc(PickupRecord.pickup_time))
                .first()
            )
            if pick:
                if pick.serial_number:
                    serial_number = pick.serial_number
                elif pick.main_device_barcode:
                    serial_number = pick.main_device_barcode
            if not serial_number and getattr(out_trans, "scan_barcode", None):
                serial_number = out_trans.scan_barcode

        if is_main:
            max_returnable = 0 if (it.equipment_instance_id and str(it.equipment_instance_id) in main_reserved) else 1
        else:
            reserved = int(aux_reserved.get(int(it.equipment_id), 0))
            max_returnable = max(int(it.quantity or 0) - reserved, 0)

        items.append(
            {
                "item_id": it.id,
                "equipment_id": it.equipment_id,
                "equipment_name": eq.equipment_name if eq else None,
                "equipment_code": eq.equipment_code if eq else None,
                "unit": getattr(eq, "unit", None) if eq else None,
                "quantity": int(it.quantity or 0),
                "is_main_device": is_main,
                "serial_number": serial_number,
                "max_returnable": int(max_returnable),
            }
        )

    return {
        "id": out_trans.id,
        "document_number": out_trans.document_number,
        "warehouse_id": out_trans.warehouse_id,
        "warehouse_name": out_trans.warehouse.warehouse_name if out_trans.warehouse else None,
        "operation_time": to_utc_iso(out_trans.operation_time) if out_trans.operation_time else None,
        "items": items,
    }


def _stock_out_source_tag(out_trans: StockTransaction) -> str:
    loc = out_trans.scan_location if isinstance(out_trans.scan_location, dict) else {}
    src = str(loc.get("_source") or "").strip()
    if src == "issue_draft_confirm":
        return "领料单"
    if src == "manual_stock_out":
        return "快速出库"
    # 扫码出库链路通常会写 scan_time/scan_barcode
    if getattr(out_trans, "scan_time", None) or getattr(out_trans, "scan_barcode", None):
        return "扫码领料"
    return "其他"


def _stock_out_method_tag(*, has_main: bool, has_aux: bool) -> str:
    if has_main and has_aux:
        return "套装领料"
    if has_main and not has_aux:
        return "主设备领料"
    if has_aux and not has_main:
        return "纯辅料领料"
    return "未知"


def _has_main_aux_map(db: Session, out_ids: List[str]) -> Dict[str, dict]:
    """返回 {out_id: {has_main: bool, has_aux: bool}}"""
    if not out_ids:
        return {}

    rows = (
        db.query(StockTransactionItem.transaction_id, Equipment.category)
        .join(Equipment, Equipment.id == StockTransactionItem.equipment_id)
        .filter(StockTransactionItem.transaction_id.in_(out_ids))
        .distinct()
        .all()
    )
    mapping: Dict[str, dict] = {str(tid): {"has_main": False, "has_aux": False} for tid in out_ids}
    for tid, cat in rows:
        key = str(tid)
        if key not in mapping:
            mapping[key] = {"has_main": False, "has_aux": False}
        v = _enum_value(cat)
        if v == EquipmentCategoryEnum.MAIN_DEVICE.value:
            mapping[key]["has_main"] = True
        elif v == EquipmentCategoryEnum.AUXILIARY.value:
            mapping[key]["has_aux"] = True
    return mapping


def _can_access_stock_out_as_receiver(
    db: Session,
    *,
    out_trans: StockTransaction,
    current_user: User,
) -> bool:
    if not out_trans:
        return False
    if out_trans.issued_to == current_user.id:
        return True

    legacy_pick = db.query(PickupRecord.id).filter(
        PickupRecord.transaction_id == out_trans.id,
        PickupRecord.picker_id == current_user.id,
    ).first()
    return legacy_pick is not None


def _find_accessible_single_main_stock_out_by_sn(
    db: Session,
    *,
    sn: str,
    current_user: User,
) -> Optional[StockTransaction]:
    """根据主设备 SN 查找“当前用户可作为领取人查看”的最近一笔出库单。

    注意：
    - 为避免多主设备出库单被扫码退库误操作，这里仅允许“单主设备”出库单匹配。
    """
    sn = (sn or "").strip()
    if not sn:
        return None

    inst = db.query(EquipmentInstance).filter(EquipmentInstance.serial_number == sn).first()
    if not inst:
        return None

    legacy_pick_exists = db.query(PickupRecord.id).filter(
        PickupRecord.transaction_id == StockTransaction.id,
        PickupRecord.picker_id == current_user.id,
    ).exists()

    out_trans = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment),
            joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
        )
        .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransactionItem.equipment_instance_id == inst.id,
            or_(StockTransaction.issued_to == current_user.id, legacy_pick_exists),
        )
        .order_by(desc(StockTransaction.operation_time))
        .first()
    )
    if not out_trans:
        return None

    # 安全限制：仅允许“单主设备”的出库单走扫码退库（避免误把多SN整单退回）
    main_sns = []
    for it in out_trans.transaction_items or []:
        eq = it.equipment
        if not eq or _enum_value(eq.category) != EquipmentCategoryEnum.MAIN_DEVICE.value:
            continue
        sn_item = it.equipment_instance.serial_number if it.equipment_instance else None
        if sn_item:
            main_sns.append(str(sn_item).strip())

    unique = [s for s in dict.fromkeys(main_sns) if s]
    if len(unique) != 1:
        return None
    if unique[0] != sn:
        return None
    return out_trans


@router.get("/my-stock-outs")
async def list_my_stock_outs(
    page: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_not_surveyor(current_user)

    try:
        page = int(page or 1)
    except Exception:
        page = 1
    page = max(1, page)
    try:
        page_size = int(page_size or 10)
    except Exception:
        page_size = 10
    page_size = max(1, min(page_size, 50))

    query = db.query(StockTransaction).options(
        joinedload(StockTransaction.warehouse),
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment),
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
    ).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
        or_(StockTransaction.operator_id == current_user.id, StockTransaction.issued_to == current_user.id),
    )

    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        query = query.filter(StockTransaction.document_number.like(like))

    total = query.count()
    rows = (
        query.order_by(desc(StockTransaction.operation_time))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    records = [_serialize_stock_out_for_return(db, t) for t in rows]
    return {"records": records, "total": total}


@router.get("/my-stock-outs/{out_transaction_id}")
async def get_my_stock_out_detail(
    out_transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取“我领取的出库单”详情（用于移动端详情页）。"""
    _ensure_not_surveyor(current_user)

    out_id = (out_transaction_id or "").strip()
    if not out_id:
        raise HTTPException(status_code=400, detail="缺少 out_transaction_id")

    out_trans = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment),
            joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
        )
        .filter(StockTransaction.id == out_id, StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT)
        .first()
    )
    if not out_trans:
        raise HTTPException(status_code=404, detail="出库单不存在")

    if not _can_access_stock_out_as_receiver(db, out_trans=out_trans, current_user=current_user):
        raise HTTPException(status_code=403, detail="无权限查看该出库单")

    has_main = False
    has_aux = False
    for it in out_trans.transaction_items or []:
        eq = it.equipment
        if not eq:
            continue
        cat = _enum_value(eq.category)
        if cat == EquipmentCategoryEnum.MAIN_DEVICE.value:
            has_main = True
        elif cat == EquipmentCategoryEnum.AUXILIARY.value:
            has_aux = True

    payload = _serialize_stock_out_for_return(db, out_trans)
    payload["source_tag"] = _stock_out_source_tag(out_trans)
    payload["method_tag"] = _stock_out_method_tag(has_main=has_main, has_aux=has_aux)
    payload["notes"] = out_trans.notes
    return payload


@router.get("/stock-outs/{out_transaction_id}")
async def get_stock_out_detail(
    out_transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取出库单详情（管理员/仓库侧）。"""
    _ensure_stock_operator(current_user)

    out_id = (out_transaction_id or "").strip()
    if not out_id:
        raise HTTPException(status_code=400, detail="缺少 out_transaction_id")

    out_trans = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment),
            joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
        )
        .filter(StockTransaction.id == out_id, StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT)
        .first()
    )
    if not out_trans:
        raise HTTPException(status_code=404, detail="出库单不存在")

    has_main = False
    has_aux = False
    for it in out_trans.transaction_items or []:
        eq = it.equipment
        if not eq:
            continue
        cat = _enum_value(eq.category)
        if cat == EquipmentCategoryEnum.MAIN_DEVICE.value:
            has_main = True
        elif cat == EquipmentCategoryEnum.AUXILIARY.value:
            has_aux = True

    payload = _serialize_stock_out_for_return(db, out_trans)
    payload["source_tag"] = _stock_out_source_tag(out_trans)
    payload["method_tag"] = _stock_out_method_tag(has_main=has_main, has_aux=has_aux)
    payload["notes"] = out_trans.notes
    payload["issued_to"] = out_trans.issued_to
    payload["operator_id"] = out_trans.operator_id
    return payload


def _list_issued_items_for_user(
    db: Session,
    *,
    receiver_user_id: int,
    item_type: str = "main",
    status_group: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    paginate: bool = True,
) -> dict:
    """按领取人/扫码领取人返回“主设备/辅料”扁平列表（管理员可查看指定人员）。"""
    t = str(item_type or "main").strip().lower()
    if t not in {"main", "aux"}:
        raise HTTPException(status_code=400, detail="item_type 参数不合法")

    allowed_groups = {"picked", "installed", "pending_receive", "returned", "rejected"}
    g = str(status_group or "").strip()
    if g and g not in allowed_groups:
        raise HTTPException(status_code=400, detail="status_group 参数不合法")

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

    search = (q or "").strip()
    like_contains = f"%{search}%"
    like_prefix = f"{search}%"

    group_counts = {"picked": 0, "installed": 0, "pending_receive": 0, "returned": 0, "rejected": 0}

    # 归属规则：
    # 1) issued_to 有值：归属到 issued_to；
    # 2) issued_to 为空：归属到“该出库单最新一条 pickup_record”的 picker_id。
    assigned_out_ids: set = set()

    direct_out_rows = (
        db.query(StockTransaction.id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransaction.issued_to == receiver_user_id,
        )
        .all()
    )
    for row in direct_out_rows:
        if row and row[0]:
            assigned_out_ids.add(str(row[0]))

    pick_latest_subq = (
        db.query(
            PickupRecord.transaction_id.label("out_id"),
            func.max(PickupRecord.pickup_time).label("max_time"),
        )
        .join(StockTransaction, StockTransaction.id == PickupRecord.transaction_id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransaction.issued_to.is_(None),
        )
        .group_by(PickupRecord.transaction_id)
        .subquery()
    )
    pick_out_rows = (
        db.query(StockTransaction.id.label("out_id"))
        .join(pick_latest_subq, pick_latest_subq.c.out_id == StockTransaction.id)
        .join(
            PickupRecord,
            and_(
                PickupRecord.transaction_id == pick_latest_subq.c.out_id,
                PickupRecord.pickup_time == pick_latest_subq.c.max_time,
            ),
        )
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransaction.issued_to.is_(None),
            PickupRecord.picker_id == receiver_user_id,
        )
        .all()
    )
    for r in pick_out_rows:
        out_id = str(getattr(r, "out_id", "") or "").strip()
        if out_id:
            assigned_out_ids.add(out_id)

    if not assigned_out_ids:
        return {
            "items": [],
            "page": page,
            "page_size": page_size,
            "total": 0,
            "has_more": False,
            "group_counts": group_counts,
        }

    if t == "main":
        query = (
            db.query(
                StockTransaction.id.label("out_id"),
                StockTransaction.document_number.label("out_document_number"),
                StockTransaction.operation_time.label("operation_time"),
                Warehouse.id.label("warehouse_id"),
                Warehouse.warehouse_name.label("warehouse_name"),
                StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
                EquipmentInstance.serial_number.label("serial_number"),
                Equipment.id.label("equipment_id"),
                Equipment.equipment_name.label("equipment_name"),
                Equipment.equipment_code.label("equipment_code"),
            )
            .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
            .join(Equipment, Equipment.id == StockTransactionItem.equipment_id)
            .outerjoin(EquipmentInstance, EquipmentInstance.id == StockTransactionItem.equipment_instance_id)
            .outerjoin(Warehouse, Warehouse.id == StockTransaction.warehouse_id)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
                StockTransaction.id.in_(list(assigned_out_ids)),
                Equipment.category == EquipmentCategoryEnum.MAIN_DEVICE,
            )
        )

        if search:
            pickup_search_exists = db.query(PickupRecord.id).filter(
                PickupRecord.transaction_id == StockTransaction.id,
                or_(
                    PickupRecord.serial_number == search,
                    PickupRecord.serial_number.like(like_prefix),
                    PickupRecord.main_device_barcode == search,
                    PickupRecord.main_device_barcode.like(like_prefix),
                ),
            ).exists()
            query = query.filter(
                or_(
                    StockTransaction.document_number.like(like_contains),
                    EquipmentInstance.serial_number == search,
                    EquipmentInstance.serial_number.like(like_prefix),
                    Equipment.equipment_name.like(like_contains),
                    Equipment.equipment_code.like(like_contains),
                    pickup_search_exists,
                )
            )

        rows = query.order_by(desc(StockTransaction.operation_time)).all()

        out_ids = list({str(r.out_id) for r in rows if r and r.out_id})
        pickup_map: Dict[str, dict] = {}
        if out_ids:
            pick_any_latest_subq = (
                db.query(
                    PickupRecord.transaction_id.label("out_id"),
                    func.max(PickupRecord.pickup_time).label("max_time"),
                )
                .filter(PickupRecord.transaction_id.in_(out_ids))
                .group_by(PickupRecord.transaction_id)
                .subquery()
            )
            pick_rows = (
                db.query(
                    PickupRecord.transaction_id,
                    PickupRecord.serial_number,
                    PickupRecord.main_device_barcode,
                )
                .join(
                    pick_any_latest_subq,
                    and_(
                        PickupRecord.transaction_id == pick_any_latest_subq.c.out_id,
                        PickupRecord.pickup_time == pick_any_latest_subq.c.max_time,
                    ),
                )
                .all()
            )
            for pr in pick_rows:
                key = str(pr.transaction_id)
                if key not in pickup_map:
                    pickup_map[key] = {
                        "serial_number": str(pr.serial_number).strip() if pr.serial_number else None,
                        "main_device_barcode": str(pr.main_device_barcode).strip() if pr.main_device_barcode else None,
                    }

        sns = []
        for r in rows:
            sn_value = (r.serial_number or "").strip() if r.serial_number else ""
            if not sn_value:
                pick = pickup_map.get(str(r.out_id)) or {}
                sn_value = str(pick.get("serial_number") or "").strip()
                if not sn_value:
                    sn_value = str(pick.get("main_device_barcode") or "").strip()
            if sn_value:
                sns.append(sn_value)
        sns = list({s for s in sns if s})

        lock_status = {
            InspectionStatusEnum.SUBMITTED,
            InspectionStatusEnum.UNDER_REVIEW,
            InspectionStatusEnum.APPROVED,
            InspectionStatusEnum.COMPLETED,
        }
        device_level_cond = and_(
            InspectionCheckItem.sector_id.isnot(None),
            InspectionCheckItem.band.isnot(None),
            or_(
                InspectionCheckItem.cell_id.is_(None),
                InspectionCheckItem.cell_id
                == (InspectionCheckItem.sector_id + "_" + InspectionCheckItem.band),
            ),
        )

        installed_locked_sns: set = set()
        if sns:
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

        out_ids = list({str(r.out_id) for r in rows if r and r.out_id})
        instance_ids = list({str(r.equipment_instance_id) for r in rows if r and r.equipment_instance_id})

        return_map: Dict[tuple, dict] = {}
        if out_ids and instance_ids:
            ret_rows = (
                db.query(
                    StockTransaction.related_transaction_id.label("out_id"),
                    StockTransaction.id.label("return_id"),
                    StockTransaction.document_number.label("return_document_number"),
                    StockTransaction.approval_status.label("return_status"),
                    StockTransaction.approval_comments.label("approval_comments"),
                    StockTransaction.created_at.label("created_at"),
                    StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
                    StockTransactionItem.quantity.label("quantity"),
                    StockTransactionItem.received_qty.label("received_qty"),
                )
                .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
                .filter(
                    StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                    StockTransaction.related_transaction_id.in_(out_ids),
                    StockTransaction.approval_status.in_(["pending_receive", "partially_received", "received", "rejected"]),
                    StockTransactionItem.equipment_instance_id.in_(instance_ids),
                )
                .order_by(desc(StockTransaction.created_at))
                .all()
            )
            for rr in ret_rows:
                key = (str(rr.out_id), str(rr.equipment_instance_id))
                if key in return_map:
                    continue
                qty = int(rr.quantity or 0)
                received = int(rr.received_qty or 0)
                status = str(rr.return_status or "")
                eff_received = qty if status == "received" else received
                return_map[key] = {
                    "return_transaction_id": str(rr.return_id),
                    "return_document_number": rr.return_document_number,
                    "return_status": status,
                    "quantity": qty,
                    "received_qty": eff_received,
                    "return_reject_reason": rr.approval_comments if status == "rejected" else None,
                }

        out_meta_map: Dict[str, dict] = {}
        if out_ids:
            has_map = _has_main_aux_map(db, out_ids)
            out_rows = (
                db.query(StockTransaction)
                .options(joinedload(StockTransaction.operator))
                .filter(StockTransaction.id.in_(out_ids))
                .all()
            )
            for ot in out_rows:
                key = str(ot.id)
                flags = has_map.get(key, {"has_main": False, "has_aux": False})
                operator_name = None
                if ot.operator:
                    operator_name = ot.operator.full_name or ot.operator.username
                out_meta_map[key] = {
                    "source_tag": _stock_out_source_tag(ot),
                    "method_tag": _stock_out_method_tag(
                        has_main=bool(flags["has_main"]), has_aux=bool(flags["has_aux"])
                    ),
                    "operator_id": ot.operator_id,
                    "operator_name": operator_name,
                }

        items_all = []
        for r in rows:
            out_id = str(r.out_id)
            sn = (r.serial_number or "").strip() if r.serial_number else ""
            pick = pickup_map.get(out_id) or {}
            pick_sn = str(pick.get("serial_number") or "").strip()
            pick_barcode = str(pick.get("main_device_barcode") or "").strip()
            main_device_barcode = pick_barcode or None
            if not sn and pick_sn:
                sn = pick_sn
            if not sn and pick_barcode:
                sn = pick_barcode
            inst_id = str(r.equipment_instance_id or "")

            ret = return_map.get((out_id, inst_id))
            status_value = "picked"
            return_status = None
            return_tx_id = None
            return_doc = None
            is_returned = False
            if ret:
                return_status = ret.get("return_status")
                return_tx_id = ret.get("return_transaction_id")
                return_doc = ret.get("return_document_number")
                qty = int(ret.get("quantity") or 0)
                received_qty = int(ret.get("received_qty") or 0)
                if return_status == "received" or (qty > 0 and received_qty >= qty):
                    status_value = "returned"
                    is_returned = True
                elif return_status in {"pending_receive", "partially_received"}:
                    status_value = "pending_receive"
                elif return_status == "rejected":
                    status_value = "rejected"
            else:
                if sn and sn in installed_locked_sns:
                    status_value = "installed"

            group_counts[status_value] = int(group_counts.get(status_value, 0) or 0) + 1

            meta = out_meta_map.get(out_id, {})
            items_all.append(
                {
                    "item_type": "main",
                    "status_group": status_value,
                    "source_tag": meta.get("source_tag") or "其他",
                    "method_tag": meta.get("method_tag") or "未知",
                    "out_transaction_id": out_id,
                    "out_document_number": r.out_document_number,
                    "warehouse_id": r.warehouse_id,
                    "warehouse_name": r.warehouse_name,
                    "operation_time": to_utc_iso(r.operation_time) if r.operation_time else None,
                    "operator_id": meta.get("operator_id"),
                    "operator_name": meta.get("operator_name"),
                    "equipment_instance_id": r.equipment_instance_id,
                    "serial_number": sn,
                    "main_device_barcode": main_device_barcode,
                    "equipment_id": r.equipment_id,
                    "equipment_name": r.equipment_name,
                    "equipment_code": r.equipment_code,
                    "return_status": return_status,
                    "return_transaction_id": return_tx_id,
                    "return_document_number": return_doc,
                    "return_reject_reason": ret.get("return_reject_reason") if ret else None,
                    "is_returned": is_returned,
                }
            )

        if g:
            items_all = [it for it in items_all if it.get("status_group") == g]

        items_all.sort(key=lambda x: x.get("operation_time") or "", reverse=True)
        total = len(items_all)

        if not paginate:
            return {
                "items": items_all,
                "page": 1,
                "page_size": total,
                "total": total,
                "has_more": False,
                "group_counts": group_counts,
            }

        offset = (page - 1) * page_size
        items_page = items_all[offset : offset + page_size]
        has_more = offset + len(items_page) < total

        return {
            "items": items_page,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_more": has_more,
            "group_counts": group_counts,
        }

    # ===== aux =====
    group_counts["installed"] = 0  # 辅料不展示“已安装”

    query = (
        db.query(
            StockTransaction.id.label("out_id"),
            StockTransaction.document_number.label("out_document_number"),
            StockTransaction.operation_time.label("operation_time"),
            Warehouse.id.label("warehouse_id"),
            Warehouse.warehouse_name.label("warehouse_name"),
            Equipment.id.label("equipment_id"),
            Equipment.equipment_name.label("equipment_name"),
            Equipment.equipment_code.label("equipment_code"),
            Equipment.unit.label("unit"),
            func.sum(StockTransactionItem.quantity).label("out_qty"),
        )
        .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
        .join(Equipment, Equipment.id == StockTransactionItem.equipment_id)
        .outerjoin(Warehouse, Warehouse.id == StockTransaction.warehouse_id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransaction.id.in_(list(assigned_out_ids)),
            Equipment.category == EquipmentCategoryEnum.AUXILIARY,
        )
        .group_by(
            StockTransaction.id,
            StockTransaction.document_number,
            StockTransaction.operation_time,
            Warehouse.id,
            Warehouse.warehouse_name,
            Equipment.id,
            Equipment.equipment_name,
            Equipment.equipment_code,
            Equipment.unit,
        )
    )

    if search:
        query = query.filter(
            or_(
                StockTransaction.document_number.like(like_contains),
                Equipment.equipment_name.like(like_contains),
                Equipment.equipment_code.like(like_contains),
            )
        )

    rows = query.order_by(desc(StockTransaction.operation_time)).all()
    out_ids = list({str(r.out_id) for r in rows if r and r.out_id})

    out_meta_map: Dict[str, dict] = {}
    if out_ids:
        has_map = _has_main_aux_map(db, out_ids)
        out_rows = (
            db.query(StockTransaction)
            .options(joinedload(StockTransaction.operator))
            .filter(StockTransaction.id.in_(out_ids))
            .all()
        )
        for ot in out_rows:
            key = str(ot.id)
            flags = has_map.get(key, {"has_main": False, "has_aux": False})
            operator_name = None
            if ot.operator:
                operator_name = ot.operator.full_name or ot.operator.username
            out_meta_map[key] = {
                "source_tag": _stock_out_source_tag(ot),
                "method_tag": _stock_out_method_tag(
                    has_main=bool(flags["has_main"]), has_aux=bool(flags["has_aux"])
                ),
                "operator_id": ot.operator_id,
                "operator_name": operator_name,
            }

    aux_return_map: Dict[tuple, dict] = {}
    if out_ids:
        ret_rows = (
            db.query(
                StockTransaction.related_transaction_id.label("out_id"),
                StockTransaction.approval_status.label("return_status"),
                StockTransactionItem.equipment_id.label("equipment_id"),
                StockTransactionItem.quantity.label("quantity"),
                StockTransactionItem.received_qty.label("received_qty"),
            )
            .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                StockTransaction.related_transaction_id.in_(out_ids),
                StockTransaction.approval_status.in_(["pending_receive", "partially_received", "received"]),
                StockTransactionItem.equipment_instance_id.is_(None),
            )
            .all()
        )
        for rr in ret_rows:
            key = (str(rr.out_id), int(rr.equipment_id))
            if key not in aux_return_map:
                aux_return_map[key] = {"requested_qty": 0, "received_qty": 0}
            qty = int(rr.quantity or 0)
            if qty <= 0:
                continue
            status = str(rr.return_status or "")
            aux_return_map[key]["requested_qty"] += qty
            if status == "received":
                aux_return_map[key]["received_qty"] += qty
            else:
                aux_return_map[key]["received_qty"] += int(rr.received_qty or 0)

    items_all = []
    for r in rows:
        out_id = str(r.out_id)
        equipment_id = int(r.equipment_id)
        out_qty = int(r.out_qty or 0)
        ret = aux_return_map.get((out_id, equipment_id), {"requested_qty": 0, "received_qty": 0})

        requested = min(int(ret.get("requested_qty") or 0), out_qty)
        received = min(int(ret.get("received_qty") or 0), out_qty)
        pending = max(requested - received, 0)

        status_value = "picked"
        is_returned = False
        if out_qty > 0 and received >= out_qty:
            status_value = "returned"
            is_returned = True
        elif pending > 0:
            status_value = "pending_receive"

        group_counts[status_value] = int(group_counts.get(status_value, 0) or 0) + 1

        meta = out_meta_map.get(out_id, {})
        items_all.append(
            {
                "item_type": "aux",
                "status_group": status_value,
                "source_tag": meta.get("source_tag") or "其他",
                "method_tag": meta.get("method_tag") or "未知",
                "out_transaction_id": out_id,
                "out_document_number": r.out_document_number,
                "warehouse_id": r.warehouse_id,
                "warehouse_name": r.warehouse_name,
                "operation_time": to_utc_iso(r.operation_time) if r.operation_time else None,
                "operator_id": meta.get("operator_id"),
                "operator_name": meta.get("operator_name"),
                "equipment_id": equipment_id,
                "equipment_name": r.equipment_name,
                "equipment_code": r.equipment_code,
                "unit": r.unit,
                "quantity": out_qty,
                "is_returned": is_returned,
                "return_pending_qty": int(pending),
                "return_received_qty": int(received),
            }
        )

    if g:
        if g == "installed":
            items_all = []
        else:
            items_all = [it for it in items_all if it.get("status_group") == g]

    items_all.sort(key=lambda x: x.get("operation_time") or "", reverse=True)
    total = len(items_all)

    if not paginate:
        return {
            "items": items_all,
            "page": 1,
            "page_size": total,
            "total": total,
            "has_more": False,
            "group_counts": group_counts,
        }

    offset = (page - 1) * page_size
    items_page = items_all[offset : offset + page_size]
    has_more = offset + len(items_page) < total

    return {
        "items": items_page,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_more": has_more,
        "group_counts": group_counts,
    }


@router.get("/users/{user_id}/issued-items")
async def list_user_issued_items(
    user_id: int,
    item_type: str = "main",
    status_group: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """web-admin：查看指定用户的“我的设备/辅料”扁平列表。"""
    _ensure_stock_operator(current_user)

    target = db.query(User).filter(User.id == int(user_id)).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    return _list_issued_items_for_user(
        db,
        receiver_user_id=int(user_id),
        item_type=item_type,
        status_group=status_group,
        q=q,
        page=page,
        page_size=page_size,
        paginate=True,
    )


@router.get("/users/{user_id}/issued-items/export")
async def export_user_issued_items(
    user_id: int,
    item_type: str = "main",
    status_group: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """web-admin：导出指定用户的“主设备/辅料”归属明细（按当前 Tab 单 Sheet）。"""
    _ensure_stock_operator(current_user)

    target = db.query(User).filter(User.id == int(user_id)).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    resp = _list_issued_items_for_user(
        db,
        receiver_user_id=int(user_id),
        item_type=item_type,
        status_group=status_group,
        q=q,
        page=1,
        page_size=100,
        paginate=False,
    )
    items = resp.get("items") or []

    import pandas as pd
    import io
    from fastapi.responses import StreamingResponse
    from urllib.parse import quote

    t = str(item_type or "main").strip().lower()

    status_map = {
        "picked": "已领货",
        "installed": "已安装",
        "pending_receive": "退库待收货",
        "returned": "已退库",
    }
    def status_text(v: Optional[str]) -> str:
        key = str(v or "").strip()
        return status_map.get(key, key or "-")

    rows = []
    if t == "main":
        for it in items:
            rows.append(
                {
                    "SN": it.get("serial_number") or "",
                    "条码": it.get("main_device_barcode") or "",
                    "设备名称": it.get("equipment_name") or "",
                    "设备编码": it.get("equipment_code") or "",
                    "状态": status_text(it.get("status_group")),
                    "出库单号": it.get("out_document_number") or "",
                    "出库单ID": it.get("out_transaction_id") or "",
                    "设备实例ID": it.get("equipment_instance_id") or "",
                    "仓库": it.get("warehouse_name") or "",
                    "出库时间": it.get("operation_time") or "",
                    "领料方式": it.get("method_tag") or "",
                    "来源": it.get("source_tag") or "",
                    "退库状态": it.get("return_status") or "",
                    "退库单号": it.get("return_document_number") or "",
                    "退库单ID": it.get("return_transaction_id") or "",
                }
            )
        sheet_name = "主设备"
    else:
        for it in items:
            rows.append(
                {
                    "物料名称": it.get("equipment_name") or "",
                    "物料编码": it.get("equipment_code") or "",
                    "数量": int(it.get("quantity") or 0),
                    "单位": it.get("unit") or "",
                    "状态": status_text(it.get("status_group")),
                    "出库单号": it.get("out_document_number") or "",
                    "出库单ID": it.get("out_transaction_id") or "",
                    "仓库": it.get("warehouse_name") or "",
                    "出库时间": it.get("operation_time") or "",
                    "领料方式": it.get("method_tag") or "",
                    "来源": it.get("source_tag") or "",
                    "退库待收货数量": int(it.get("return_pending_qty") or 0),
                    "退库已收货数量": int(it.get("return_received_qty") or 0),
                }
            )
        sheet_name = "辅料"

    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets.get(sheet_name)
        if ws:
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        max_length = max(max_length, len(str(cell.value or "")))
                    except Exception:
                        pass
                ws.column_dimensions[column_letter].width = min(max(max_length + 2, 10), 50)

    output.seek(0)

    base_name = target.full_name or target.username or f"user_{user_id}"
    file_name = f"{base_name}_{sheet_name}_归属明细.xlsx"
    quoted = quote(file_name)
    return StreamingResponse(
        io.BytesIO(output.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
    )


@router.get("/user-ownership/export")
async def export_user_ownership(
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """web-admin：导出全部人员物料归属（跟随页面用户关键字筛选，单 Sheet）。"""
    _ensure_stock_operator(current_user)

    kw = str(keyword or "").strip()

    user_query = db.query(User)
    if kw:
        user_query = user_query.filter(
            or_(
                User.username.contains(kw),
                User.full_name.contains(kw),
                User.email.contains(kw),
            )
        )
    user_rows = user_query.all()
    user_ids = [int(u.id) for u in user_rows if u and getattr(u, "id", None) is not None]
    user_meta = {
        int(u.id): {
            "user_id": int(u.id),
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": bool(getattr(u, "is_active", True)),
        }
        for u in user_rows
        if u and getattr(u, "id", None) is not None
    }

    # 归属：优先 issued_to；若 issued_to 为空，则归属到扫码领取人（pickup_record.picker_id）
    assigned_out_map: Dict[str, int] = {}

    if user_ids:
        direct_out_rows = (
            db.query(StockTransaction.id, StockTransaction.issued_to)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
                StockTransaction.issued_to.in_(user_ids),
            )
            .all()
        )
        for out_id, issued_to in direct_out_rows:
            if not out_id or not issued_to:
                continue
            try:
                assigned_out_map[str(out_id)] = int(issued_to)
            except Exception:
                continue

        pick_latest_subq = (
            db.query(
                PickupRecord.transaction_id.label("out_id"),
                func.max(PickupRecord.pickup_time).label("max_time"),
            )
            .join(StockTransaction, StockTransaction.id == PickupRecord.transaction_id)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
                StockTransaction.issued_to.is_(None),
            )
            .group_by(PickupRecord.transaction_id)
            .subquery()
        )

        pick_assign_rows = (
            db.query(
                StockTransaction.id.label("out_id"),
                PickupRecord.picker_id.label("picker_id"),
            )
            .join(pick_latest_subq, pick_latest_subq.c.out_id == StockTransaction.id)
            .join(
                PickupRecord,
                and_(
                    PickupRecord.transaction_id == pick_latest_subq.c.out_id,
                    PickupRecord.pickup_time == pick_latest_subq.c.max_time,
                ),
            )
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
                StockTransaction.issued_to.is_(None),
                PickupRecord.picker_id.in_(user_ids),
            )
            .all()
        )
        for r in pick_assign_rows:
            out_id = str(getattr(r, "out_id", "") or "").strip()
            if not out_id or out_id in assigned_out_map:
                continue
            try:
                assigned_out_map[out_id] = int(getattr(r, "picker_id", 0) or 0)
            except Exception:
                continue

    out_ids = [oid for oid in assigned_out_map.keys() if oid]

    import pandas as pd
    import io
    from fastapi.responses import StreamingResponse
    from urllib.parse import quote

    if not out_ids:
        df = pd.DataFrame(
            columns=[
                "用户ID",
                "用户名",
                "姓名",
                "角色",
                "是否启用",
                "物料类型",
                "SN",
                "条码",
                "物料名称",
                "物料编码",
                "数量",
                "单位",
                "状态",
                "出库单号",
                "出库单ID",
                "设备实例ID",
                "仓库",
                "出库时间",
                "领料方式",
                "来源",
                "退库状态",
                "退库单号",
                "退库单ID",
                "退库待收货数量",
                "退库已收货数量",
            ]
        )
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="归属明细")
        output.seek(0)
        file_name = "人员领用台账_全部物料.xlsx"
        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}"},
        )

    # 出库单基础信息
    out_rows = (
        db.query(
            StockTransaction.id.label("out_id"),
            StockTransaction.document_number.label("out_document_number"),
            StockTransaction.operation_time.label("operation_time"),
            Warehouse.warehouse_name.label("warehouse_name"),
        )
        .outerjoin(Warehouse, Warehouse.id == StockTransaction.warehouse_id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransaction.id.in_(out_ids),
        )
        .all()
    )
    out_meta = {
        str(r.out_id): {
            "out_document_number": r.out_document_number,
            "operation_time": to_utc_iso(r.operation_time) if r.operation_time else None,
            "warehouse_name": r.warehouse_name,
        }
        for r in out_rows
        if r and r.out_id
    }

    # 领料方式/来源标签
    has_map = _has_main_aux_map(db, out_ids)
    out_obj_rows = db.query(StockTransaction).filter(StockTransaction.id.in_(out_ids)).all()
    out_tags = {}
    for ot in out_obj_rows:
        key = str(ot.id)
        flags = has_map.get(key, {"has_main": False, "has_aux": False})
        out_tags[key] = {
            "source_tag": _stock_out_source_tag(ot),
            "method_tag": _stock_out_method_tag(has_main=bool(flags["has_main"]), has_aux=bool(flags["has_aux"])),
        }

    # 取每个出库单最近一条 pickup_record（用于 SN/条码回填）
    pick_any_latest_subq = (
        db.query(
            PickupRecord.transaction_id.label("out_id"),
            func.max(PickupRecord.pickup_time).label("max_time"),
        )
        .filter(PickupRecord.transaction_id.in_(out_ids))
        .group_by(PickupRecord.transaction_id)
        .subquery()
    )
    pick_any_rows = (
        db.query(
            PickupRecord.transaction_id.label("out_id"),
            PickupRecord.serial_number.label("serial_number"),
            PickupRecord.main_device_barcode.label("main_device_barcode"),
        )
        .join(
            pick_any_latest_subq,
            and_(
                PickupRecord.transaction_id == pick_any_latest_subq.c.out_id,
                PickupRecord.pickup_time == pick_any_latest_subq.c.max_time,
            ),
        )
        .all()
    )
    pick_any_map: Dict[str, dict] = {}
    for pr in pick_any_rows:
        out_id = str(pr.out_id)
        if not out_id:
            continue
        pick_any_map[out_id] = {
            "serial_number": str(pr.serial_number).strip() if pr.serial_number else "",
            "main_device_barcode": str(pr.main_device_barcode).strip() if pr.main_device_barcode else "",
        }

    # ===== 主设备明细：每台一行 =====
    main_item_rows = (
        db.query(
            StockTransactionItem.transaction_id.label("out_id"),
            StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
            EquipmentInstance.serial_number.label("serial_number"),
            Equipment.id.label("equipment_id"),
            Equipment.equipment_name.label("equipment_name"),
            Equipment.equipment_code.label("equipment_code"),
            Equipment.unit.label("unit"),
        )
        .join(StockTransaction, StockTransaction.id == StockTransactionItem.transaction_id)
        .join(Equipment, Equipment.id == StockTransactionItem.equipment_id)
        .outerjoin(EquipmentInstance, EquipmentInstance.id == StockTransactionItem.equipment_instance_id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransactionItem.transaction_id.in_(out_ids),
            Equipment.category == EquipmentCategoryEnum.MAIN_DEVICE,
        )
        .all()
    )

    # 主设备退库映射（按 out_id + equipment_instance_id）
    main_out_ids = list({str(r.out_id) for r in main_item_rows if r and r.out_id})
    instance_ids = list({str(r.equipment_instance_id) for r in main_item_rows if r and r.equipment_instance_id})
    return_map: Dict[tuple, dict] = {}
    if main_out_ids and instance_ids:
        ret_rows = (
            db.query(
                StockTransaction.related_transaction_id.label("out_id"),
                StockTransaction.id.label("return_id"),
                StockTransaction.document_number.label("return_document_number"),
                StockTransaction.approval_status.label("return_status"),
                StockTransaction.created_at.label("created_at"),
                StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
                StockTransactionItem.quantity.label("quantity"),
                StockTransactionItem.received_qty.label("received_qty"),
            )
            .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                StockTransaction.related_transaction_id.in_(main_out_ids),
                StockTransaction.approval_status.in_(["pending_receive", "partially_received", "received"]),
                StockTransactionItem.equipment_instance_id.in_(instance_ids),
            )
            .order_by(desc(StockTransaction.created_at))
            .all()
        )
        for rr in ret_rows:
            key = (str(rr.out_id), str(rr.equipment_instance_id))
            if key in return_map:
                continue
            qty = int(rr.quantity or 0)
            received = int(rr.received_qty or 0)
            status = str(rr.return_status or "")
            eff_received = qty if status == "received" else received
            return_map[key] = {
                "return_transaction_id": str(rr.return_id),
                "return_document_number": rr.return_document_number,
                "return_status": status,
                "quantity": qty,
                "received_qty": eff_received,
            }

    # 已安装判定：锁定检查（设备级）
    lock_status = {
        InspectionStatusEnum.SUBMITTED,
        InspectionStatusEnum.UNDER_REVIEW,
        InspectionStatusEnum.APPROVED,
        InspectionStatusEnum.COMPLETED,
    }
    device_level_cond = and_(
        InspectionCheckItem.sector_id.isnot(None),
        InspectionCheckItem.band.isnot(None),
        or_(
            InspectionCheckItem.cell_id.is_(None),
            InspectionCheckItem.cell_id
            == (InspectionCheckItem.sector_id + "_" + InspectionCheckItem.band),
        ),
    )

    sns = []
    for r in main_item_rows:
        out_id = str(r.out_id)
        sn_value = (r.serial_number or "").strip() if r.serial_number else ""
        if not sn_value:
            pick = pick_any_map.get(out_id) or {}
            sn_value = str(pick.get("serial_number") or "").strip()
            if not sn_value:
                sn_value = str(pick.get("main_device_barcode") or "").strip()
        if sn_value:
            sns.append(sn_value)
    sns = list({s for s in sns if s})

    installed_locked_sns: set = set()
    if sns:
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

    # ===== 辅料明细：按 out_id + equipment_id 聚合一行 =====
    aux_rows = (
        db.query(
            StockTransactionItem.transaction_id.label("out_id"),
            Equipment.id.label("equipment_id"),
            Equipment.equipment_name.label("equipment_name"),
            Equipment.equipment_code.label("equipment_code"),
            Equipment.unit.label("unit"),
            func.sum(StockTransactionItem.quantity).label("out_qty"),
        )
        .join(StockTransaction, StockTransaction.id == StockTransactionItem.transaction_id)
        .join(Equipment, Equipment.id == StockTransactionItem.equipment_id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransactionItem.transaction_id.in_(out_ids),
            Equipment.category == EquipmentCategoryEnum.AUXILIARY,
        )
        .group_by(
            StockTransactionItem.transaction_id,
            Equipment.id,
            Equipment.equipment_name,
            Equipment.equipment_code,
            Equipment.unit,
        )
        .all()
    )

    aux_return_map: Dict[tuple, dict] = {}
    if out_ids:
        aux_ret_rows = (
            db.query(
                StockTransaction.related_transaction_id.label("out_id"),
                StockTransaction.approval_status.label("return_status"),
                StockTransactionItem.equipment_id.label("equipment_id"),
                StockTransactionItem.quantity.label("quantity"),
                StockTransactionItem.received_qty.label("received_qty"),
            )
            .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                StockTransaction.related_transaction_id.in_(out_ids),
                StockTransaction.approval_status.in_(["pending_receive", "partially_received", "received"]),
                StockTransactionItem.equipment_instance_id.is_(None),
            )
            .all()
        )
        for rr in aux_ret_rows:
            key = (str(rr.out_id), int(rr.equipment_id))
            if key not in aux_return_map:
                aux_return_map[key] = {"requested_qty": 0, "received_qty": 0}
            qty = int(rr.quantity or 0)
            if qty <= 0:
                continue
            status = str(rr.return_status or "")
            aux_return_map[key]["requested_qty"] += qty
            if status == "received":
                aux_return_map[key]["received_qty"] += qty
            else:
                aux_return_map[key]["received_qty"] += int(rr.received_qty or 0)

    status_map = {
        "picked": "已领货",
        "installed": "已安装",
        "pending_receive": "退库待收货",
        "returned": "已退库",
    }
    def status_text(v: Optional[str]) -> str:
        key = str(v or "").strip()
        return status_map.get(key, key or "-")

    rows = []

    for r in main_item_rows:
        out_id = str(r.out_id)
        assigned_user_id = int(assigned_out_map.get(out_id) or 0)
        meta = user_meta.get(assigned_user_id) or {}
        outm = out_meta.get(out_id) or {}
        tags = out_tags.get(out_id) or {}
        pick = pick_any_map.get(out_id) or {}

        sn_value = (r.serial_number or "").strip() if r.serial_number else ""
        main_device_barcode = str(pick.get("main_device_barcode") or "").strip()
        if not sn_value:
            sn_value = str(pick.get("serial_number") or "").strip()
        if not sn_value and main_device_barcode:
            sn_value = main_device_barcode

        inst_id = str(r.equipment_instance_id or "")
        ret = return_map.get((out_id, inst_id))
        status_group = "picked"
        return_status = ""
        return_tx_id = ""
        return_doc = ""
        if ret:
            return_status = str(ret.get("return_status") or "")
            return_tx_id = str(ret.get("return_transaction_id") or "")
            return_doc = str(ret.get("return_document_number") or "")
            qty = int(ret.get("quantity") or 0)
            received_qty = int(ret.get("received_qty") or 0)
            if return_status == "received" or (qty > 0 and received_qty >= qty):
                status_group = "returned"
            else:
                status_group = "pending_receive"
        else:
            if sn_value and sn_value in installed_locked_sns:
                status_group = "installed"

        rows.append(
            {
                "用户ID": meta.get("user_id") or assigned_user_id or "",
                "用户名": meta.get("username") or "",
                "姓名": meta.get("full_name") or "",
                "角色": meta.get("role") or "",
                "是否启用": "是" if meta.get("is_active") else "否",
                "物料类型": "主设备",
                "SN": sn_value or "",
                "条码": main_device_barcode or "",
                "物料名称": r.equipment_name or "",
                "物料编码": r.equipment_code or "",
                "数量": 1,
                "单位": r.unit or "",
                "状态": status_text(status_group),
                "出库单号": outm.get("out_document_number") or "",
                "出库单ID": out_id,
                "设备实例ID": inst_id,
                "仓库": outm.get("warehouse_name") or "",
                "出库时间": outm.get("operation_time") or "",
                "领料方式": tags.get("method_tag") or "",
                "来源": tags.get("source_tag") or "",
                "退库状态": return_status,
                "退库单号": return_doc,
                "退库单ID": return_tx_id,
                "退库待收货数量": 0,
                "退库已收货数量": 0,
            }
        )

    for r in aux_rows:
        out_id = str(r.out_id)
        assigned_user_id = int(assigned_out_map.get(out_id) or 0)
        meta = user_meta.get(assigned_user_id) or {}
        outm = out_meta.get(out_id) or {}
        tags = out_tags.get(out_id) or {}

        equipment_id = int(r.equipment_id)
        out_qty = int(r.out_qty or 0)

        ret = aux_return_map.get((out_id, equipment_id), {"requested_qty": 0, "received_qty": 0})
        requested = min(int(ret.get("requested_qty") or 0), out_qty)
        received = min(int(ret.get("received_qty") or 0), out_qty)
        pending = max(requested - received, 0)

        status_group = "picked"
        if out_qty > 0 and received >= out_qty:
            status_group = "returned"
        elif pending > 0:
            status_group = "pending_receive"

        rows.append(
            {
                "用户ID": meta.get("user_id") or assigned_user_id or "",
                "用户名": meta.get("username") or "",
                "姓名": meta.get("full_name") or "",
                "角色": meta.get("role") or "",
                "是否启用": "是" if meta.get("is_active") else "否",
                "物料类型": "辅料",
                "SN": "",
                "条码": "",
                "物料名称": r.equipment_name or "",
                "物料编码": r.equipment_code or "",
                "数量": out_qty,
                "单位": r.unit or "",
                "状态": status_text(status_group),
                "出库单号": outm.get("out_document_number") or "",
                "出库单ID": out_id,
                "设备实例ID": "",
                "仓库": outm.get("warehouse_name") or "",
                "出库时间": outm.get("operation_time") or "",
                "领料方式": tags.get("method_tag") or "",
                "来源": tags.get("source_tag") or "",
                "退库状态": "",
                "退库单号": "",
                "退库单ID": "",
                "退库待收货数量": int(pending),
                "退库已收货数量": int(received),
            }
        )

    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="归属明细")
        ws = writer.sheets.get("归属明细")
        if ws:
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        max_length = max(max_length, len(str(cell.value or "")))
                    except Exception:
                        pass
                ws.column_dimensions[column_letter].width = min(max(max_length + 2, 10), 50)

    output.seek(0)
    file_name = "人员领用台账_全部物料.xlsx"
    return StreamingResponse(
        io.BytesIO(output.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}"},
    )


@router.get("/user-ownership/summary")
async def get_user_ownership_summary(
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """web-admin：分页返回用户 + 主/辅料状态汇总 + 最近出库时间。"""
    _ensure_stock_operator(current_user)

    try:
        skip = int(skip or 0)
    except Exception:
        skip = 0
    skip = max(0, skip)

    try:
        limit = int(limit or 20)
    except Exception:
        limit = 20
    limit = max(1, min(limit, 200))

    kw = str(keyword or "").strip()

    user_query = db.query(User)
    if kw:
        user_query = user_query.filter(
            or_(
                User.username.contains(kw),
                User.full_name.contains(kw),
                User.email.contains(kw),
            )
        )

    total = user_query.count()
    user_rows = user_query.order_by(User.id.asc()).offset(skip).limit(limit).all()
    user_ids = [int(u.id) for u in user_rows if u and getattr(u, "id", None) is not None]

    def _empty_counts(*, with_installed: bool) -> dict:
        base = {"picked": 0, "pending_receive": 0, "returned": 0}
        if with_installed:
            base["installed"] = 0
        return base

    summary_map: Dict[int, dict] = {}
    for u in user_rows:
        if not u or getattr(u, "id", None) is None:
            continue
        uid = int(u.id)
        summary_map[uid] = {
            "id": uid,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": bool(getattr(u, "is_active", True)),
            "main_counts": _empty_counts(with_installed=True),
            "aux_counts": _empty_counts(with_installed=False),
            "last_out_time": None,
        }

    # 归属：issued_to 优先；issued_to 为空时取最新 pickup_record.picker_id
    out_user_map: Dict[str, int] = {}
    out_time_map: Dict[str, datetime] = {}
    latest_by_user: Dict[int, datetime] = {}

    if user_ids:
        direct_out_rows = (
            db.query(StockTransaction.id, StockTransaction.issued_to, StockTransaction.operation_time)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
                StockTransaction.issued_to.in_(user_ids),
            )
            .all()
        )
        for out_id, issued_to, op_time in direct_out_rows:
            if not out_id or not issued_to:
                continue
            uid = int(issued_to)
            if uid not in summary_map:
                continue
            oid = str(out_id)
            out_user_map[oid] = uid
            if op_time:
                out_time_map[oid] = op_time
                prev = latest_by_user.get(uid)
                if not prev or op_time > prev:
                    latest_by_user[uid] = op_time

        pick_latest_subq = (
            db.query(
                PickupRecord.transaction_id.label("out_id"),
                func.max(PickupRecord.pickup_time).label("max_time"),
            )
            .join(StockTransaction, StockTransaction.id == PickupRecord.transaction_id)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
                StockTransaction.issued_to.is_(None),
            )
            .group_by(PickupRecord.transaction_id)
            .subquery()
        )
        pick_assign_rows = (
            db.query(
                StockTransaction.id.label("out_id"),
                PickupRecord.picker_id.label("picker_id"),
                StockTransaction.operation_time.label("operation_time"),
            )
            .join(pick_latest_subq, pick_latest_subq.c.out_id == StockTransaction.id)
            .join(
                PickupRecord,
                and_(
                    PickupRecord.transaction_id == pick_latest_subq.c.out_id,
                    PickupRecord.pickup_time == pick_latest_subq.c.max_time,
                ),
            )
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
                StockTransaction.issued_to.is_(None),
                PickupRecord.picker_id.in_(user_ids),
            )
            .all()
        )
        for r in pick_assign_rows:
            oid = str(getattr(r, "out_id", "") or "").strip()
            if not oid:
                continue
            uid = int(getattr(r, "picker_id", 0) or 0)
            if uid not in summary_map:
                continue
            if oid in out_user_map:
                continue
            out_user_map[oid] = uid

            op_time = getattr(r, "operation_time", None)
            if op_time:
                out_time_map[oid] = op_time
                prev = latest_by_user.get(uid)
                if not prev or op_time > prev:
                    latest_by_user[uid] = op_time

    # 写回最近出库时间
    for uid, dt in latest_by_user.items():
        if uid in summary_map:
            summary_map[uid]["last_out_time"] = to_utc_iso(dt) if dt else None

    out_ids = list(out_user_map.keys())
    if not out_ids:
        return {"users": list(summary_map.values()), "total": total, "skip": skip, "limit": limit}

    # 取每个出库单最近一条 pickup_record（用于 SN/条码回填）
    pick_any_latest_subq = (
        db.query(
            PickupRecord.transaction_id.label("out_id"),
            func.max(PickupRecord.pickup_time).label("max_time"),
        )
        .filter(PickupRecord.transaction_id.in_(out_ids))
        .group_by(PickupRecord.transaction_id)
        .subquery()
    )
    pick_any_rows = (
        db.query(
            PickupRecord.transaction_id.label("out_id"),
            PickupRecord.serial_number.label("serial_number"),
            PickupRecord.main_device_barcode.label("main_device_barcode"),
        )
        .join(
            pick_any_latest_subq,
            and_(
                PickupRecord.transaction_id == pick_any_latest_subq.c.out_id,
                PickupRecord.pickup_time == pick_any_latest_subq.c.max_time,
            ),
        )
        .all()
    )
    pick_any_map: Dict[str, dict] = {}
    for pr in pick_any_rows:
        oid = str(pr.out_id)
        if not oid:
            continue
        pick_any_map[oid] = {
            "serial_number": str(pr.serial_number).strip() if pr.serial_number else "",
            "main_device_barcode": str(pr.main_device_barcode).strip() if pr.main_device_barcode else "",
        }

    # ===== 主设备：每台一条 =====
    main_rows = (
        db.query(
            StockTransactionItem.transaction_id.label("out_id"),
            StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
            EquipmentInstance.serial_number.label("serial_number"),
        )
        .join(StockTransaction, StockTransaction.id == StockTransactionItem.transaction_id)
        .join(Equipment, Equipment.id == StockTransactionItem.equipment_id)
        .outerjoin(EquipmentInstance, EquipmentInstance.id == StockTransactionItem.equipment_instance_id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransactionItem.transaction_id.in_(out_ids),
            Equipment.category == EquipmentCategoryEnum.MAIN_DEVICE,
        )
        .all()
    )

    # 主设备退库映射（按 out_id + equipment_instance_id）
    main_out_ids = list({str(r.out_id) for r in main_rows if r and r.out_id})
    instance_ids = list({str(r.equipment_instance_id) for r in main_rows if r and r.equipment_instance_id})
    return_map: Dict[tuple, dict] = {}
    if main_out_ids and instance_ids:
        ret_rows = (
            db.query(
                StockTransaction.related_transaction_id.label("out_id"),
                StockTransaction.approval_status.label("return_status"),
                StockTransaction.created_at.label("created_at"),
                StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
                StockTransactionItem.quantity.label("quantity"),
                StockTransactionItem.received_qty.label("received_qty"),
            )
            .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                StockTransaction.related_transaction_id.in_(main_out_ids),
                StockTransaction.approval_status.in_(["pending_receive", "partially_received", "received"]),
                StockTransactionItem.equipment_instance_id.in_(instance_ids),
            )
            .order_by(desc(StockTransaction.created_at))
            .all()
        )
        for rr in ret_rows:
            key = (str(rr.out_id), str(rr.equipment_instance_id))
            if key in return_map:
                continue
            qty = int(rr.quantity or 0)
            received = int(rr.received_qty or 0)
            status = str(rr.return_status or "")
            eff_received = qty if status == "received" else received
            return_map[key] = {"return_status": status, "quantity": qty, "received_qty": eff_received}

    # 已安装判定：锁定检查（设备级）
    lock_status = {
        InspectionStatusEnum.SUBMITTED,
        InspectionStatusEnum.UNDER_REVIEW,
        InspectionStatusEnum.APPROVED,
        InspectionStatusEnum.COMPLETED,
    }
    device_level_cond = and_(
        InspectionCheckItem.sector_id.isnot(None),
        InspectionCheckItem.band.isnot(None),
        or_(
            InspectionCheckItem.cell_id.is_(None),
            InspectionCheckItem.cell_id
            == (InspectionCheckItem.sector_id + "_" + InspectionCheckItem.band),
        ),
    )

    sns = []
    for r in main_rows:
        oid = str(r.out_id)
        sn_value = (r.serial_number or "").strip() if r.serial_number else ""
        if not sn_value:
            pick = pick_any_map.get(oid) or {}
            sn_value = str(pick.get("serial_number") or "").strip()
            if not sn_value:
                sn_value = str(pick.get("main_device_barcode") or "").strip()
        if sn_value:
            sns.append(sn_value)
    sns = list({s for s in sns if s})

    installed_locked_sns: set = set()
    if sns:
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

    for r in main_rows:
        oid = str(r.out_id)
        uid = out_user_map.get(oid)
        if not uid or uid not in summary_map:
            continue

        sn_value = (r.serial_number or "").strip() if r.serial_number else ""
        if not sn_value:
            pick = pick_any_map.get(oid) or {}
            sn_value = str(pick.get("serial_number") or "").strip()
            if not sn_value:
                sn_value = str(pick.get("main_device_barcode") or "").strip()

        inst_id = str(r.equipment_instance_id or "")
        ret = return_map.get((oid, inst_id))
        status_group = "picked"
        if ret:
            return_status = str(ret.get("return_status") or "")
            qty = int(ret.get("quantity") or 0)
            received_qty = int(ret.get("received_qty") or 0)
            if return_status == "received" or (qty > 0 and received_qty >= qty):
                status_group = "returned"
            else:
                status_group = "pending_receive"
        else:
            if sn_value and sn_value in installed_locked_sns:
                status_group = "installed"

        summary_map[uid]["main_counts"][status_group] = int(summary_map[uid]["main_counts"].get(status_group, 0) or 0) + 1

    # ===== 辅料：按 out_id + equipment_id 聚合 =====
    aux_rows = (
        db.query(
            StockTransactionItem.transaction_id.label("out_id"),
            Equipment.id.label("equipment_id"),
            func.sum(StockTransactionItem.quantity).label("out_qty"),
        )
        .join(StockTransaction, StockTransaction.id == StockTransactionItem.transaction_id)
        .join(Equipment, Equipment.id == StockTransactionItem.equipment_id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransactionItem.transaction_id.in_(out_ids),
            Equipment.category == EquipmentCategoryEnum.AUXILIARY,
        )
        .group_by(
            StockTransactionItem.transaction_id,
            Equipment.id,
        )
        .all()
    )

    aux_return_map: Dict[tuple, dict] = {}
    if out_ids:
        aux_ret_rows = (
            db.query(
                StockTransaction.related_transaction_id.label("out_id"),
                StockTransaction.approval_status.label("return_status"),
                StockTransactionItem.equipment_id.label("equipment_id"),
                StockTransactionItem.quantity.label("quantity"),
                StockTransactionItem.received_qty.label("received_qty"),
            )
            .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                StockTransaction.related_transaction_id.in_(out_ids),
                StockTransaction.approval_status.in_(["pending_receive", "partially_received", "received"]),
                StockTransactionItem.equipment_instance_id.is_(None),
            )
            .all()
        )
        for rr in aux_ret_rows:
            key = (str(rr.out_id), int(rr.equipment_id))
            if key not in aux_return_map:
                aux_return_map[key] = {"requested_qty": 0, "received_qty": 0}
            qty = int(rr.quantity or 0)
            if qty <= 0:
                continue
            status = str(rr.return_status or "")
            aux_return_map[key]["requested_qty"] += qty
            if status == "received":
                aux_return_map[key]["received_qty"] += qty
            else:
                aux_return_map[key]["received_qty"] += int(rr.received_qty or 0)

    for r in aux_rows:
        oid = str(r.out_id)
        uid = out_user_map.get(oid)
        if not uid or uid not in summary_map:
            continue
        out_qty = int(r.out_qty or 0)
        equipment_id = int(r.equipment_id)
        ret = aux_return_map.get((oid, equipment_id), {"requested_qty": 0, "received_qty": 0})
        requested = min(int(ret.get("requested_qty") or 0), out_qty)
        received = min(int(ret.get("received_qty") or 0), out_qty)
        pending = max(requested - received, 0)

        status_group = "picked"
        if out_qty > 0 and received >= out_qty:
            status_group = "returned"
        elif pending > 0:
            status_group = "pending_receive"

        summary_map[uid]["aux_counts"][status_group] = int(summary_map[uid]["aux_counts"].get(status_group, 0) or 0) + 1

    return {"users": list(summary_map.values()), "total": total, "skip": skip, "limit": limit}


@router.get("/my-issued-items")
async def list_my_issued_items(
    item_type: str = "main",
    status_group: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """我的设备（扁平列表）：按“主设备 SN / 辅料行”返回。"""
    _ensure_not_surveyor(current_user)

    t = str(item_type or "main").strip().lower()
    if t not in {"main", "aux"}:
        raise HTTPException(status_code=400, detail="item_type 参数不合法")

    allowed_groups = {"picked", "installed", "pending_receive", "returned", "rejected"}
    g = str(status_group or "").strip()
    if g and g not in allowed_groups:
        raise HTTPException(status_code=400, detail="status_group 参数不合法")

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

    legacy_pick_exists = db.query(PickupRecord.id).filter(
        PickupRecord.transaction_id == StockTransaction.id,
        PickupRecord.picker_id == current_user.id,
    ).exists()

    search = (q or "").strip()
    like_contains = f"%{search}%"
    like_prefix = f"{search}%"

    group_counts = {"picked": 0, "installed": 0, "pending_receive": 0, "returned": 0, "rejected": 0}

    if t == "main":
        query = (
            db.query(
                StockTransaction.id.label("out_id"),
                StockTransaction.document_number.label("out_document_number"),
                StockTransaction.operation_time.label("operation_time"),
                Warehouse.id.label("warehouse_id"),
                Warehouse.warehouse_name.label("warehouse_name"),
                StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
                EquipmentInstance.serial_number.label("serial_number"),
                Equipment.id.label("equipment_id"),
                Equipment.equipment_name.label("equipment_name"),
                Equipment.equipment_code.label("equipment_code"),
            )
            .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
            .join(Equipment, Equipment.id == StockTransactionItem.equipment_id)
            .outerjoin(EquipmentInstance, EquipmentInstance.id == StockTransactionItem.equipment_instance_id)
            .outerjoin(Warehouse, Warehouse.id == StockTransaction.warehouse_id)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
                Equipment.category == EquipmentCategoryEnum.MAIN_DEVICE,
                or_(StockTransaction.issued_to == current_user.id, legacy_pick_exists),
            )
        )

        if search:
            pickup_search_exists = db.query(PickupRecord.id).filter(
                PickupRecord.transaction_id == StockTransaction.id,
                PickupRecord.picker_id == current_user.id,
                or_(
                    PickupRecord.serial_number == search,
                    PickupRecord.serial_number.like(like_prefix),
                    PickupRecord.main_device_barcode == search,
                    PickupRecord.main_device_barcode.like(like_prefix),
                ),
            ).exists()
            query = query.filter(
                or_(
                    StockTransaction.document_number.like(like_contains),
                    EquipmentInstance.serial_number == search,
                    EquipmentInstance.serial_number.like(like_prefix),
                    Equipment.equipment_name.like(like_contains),
                    Equipment.equipment_code.like(like_contains),
                    pickup_search_exists,
                )
            )

        rows = query.order_by(desc(StockTransaction.operation_time)).all()

        out_ids = list({str(r.out_id) for r in rows if r and r.out_id})
        pickup_map: Dict[str, dict] = {}
        if out_ids:
            pick_rows = (
                db.query(
                    PickupRecord.transaction_id,
                    PickupRecord.serial_number,
                    PickupRecord.main_device_barcode,
                    PickupRecord.pickup_time,
                )
                .filter(
                    PickupRecord.transaction_id.in_(out_ids),
                    PickupRecord.picker_id == current_user.id,
                )
                .order_by(desc(PickupRecord.pickup_time))
                .all()
            )
            for transaction_id, serial_number, main_device_barcode, _ in pick_rows:
                key = str(transaction_id)
                if key in pickup_map:
                    continue
                pickup_map[key] = {
                    "serial_number": str(serial_number).strip() if serial_number else None,
                    "main_device_barcode": str(main_device_barcode).strip() if main_device_barcode else None,
                }

        sns = []
        for r in rows:
            sn_value = (r.serial_number or "").strip() if r.serial_number else ""
            if not sn_value:
                pick = pickup_map.get(str(r.out_id)) or {}
                sn_value = str(pick.get("serial_number") or "").strip()
                if not sn_value:
                    sn_value = str(pick.get("main_device_barcode") or "").strip()
            if sn_value:
                sns.append(sn_value)
        sns = list({s for s in sns if s})

        lock_status = {
            InspectionStatusEnum.SUBMITTED,
            InspectionStatusEnum.UNDER_REVIEW,
            InspectionStatusEnum.APPROVED,
            InspectionStatusEnum.COMPLETED,
        }
        device_level_cond = and_(
            InspectionCheckItem.sector_id.isnot(None),
            InspectionCheckItem.band.isnot(None),
            or_(
                InspectionCheckItem.cell_id.is_(None),
                InspectionCheckItem.cell_id
                == (InspectionCheckItem.sector_id + "_" + InspectionCheckItem.band),
            ),
        )

        installed_locked_sns: set = set()
        if sns:
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

        out_ids = list({str(r.out_id) for r in rows if r and r.out_id})
        instance_ids = list({str(r.equipment_instance_id) for r in rows if r and r.equipment_instance_id})

        return_map: Dict[tuple, dict] = {}
        if out_ids and instance_ids:
            ret_rows = (
                db.query(
                    StockTransaction.related_transaction_id.label("out_id"),
                    StockTransaction.id.label("return_id"),
                    StockTransaction.document_number.label("return_document_number"),
                    StockTransaction.approval_status.label("return_status"),
                    StockTransaction.approval_comments.label("approval_comments"),
                    StockTransaction.created_at.label("created_at"),
                    StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
                    StockTransactionItem.quantity.label("quantity"),
                    StockTransactionItem.received_qty.label("received_qty"),
                )
                .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
                .filter(
                    StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                    StockTransaction.related_transaction_id.in_(out_ids),
                    StockTransaction.approval_status.in_(["pending_receive", "partially_received", "received", "rejected"]),
                    StockTransactionItem.equipment_instance_id.in_(instance_ids),
                )
                .order_by(desc(StockTransaction.created_at))
                .all()
            )
            for rr in ret_rows:
                key = (str(rr.out_id), str(rr.equipment_instance_id))
                if key in return_map:
                    continue
                qty = int(rr.quantity or 0)
                received = int(rr.received_qty or 0)
                status = str(rr.return_status or "")
                eff_received = qty if status == "received" else received
                return_map[key] = {
                    "return_transaction_id": str(rr.return_id),
                    "return_document_number": rr.return_document_number,
                    "return_status": status,
                    "quantity": qty,
                    "received_qty": eff_received,
                    "return_reject_reason": rr.approval_comments if status == "rejected" else None,
                }

        out_meta_map: Dict[str, dict] = {}
        if out_ids:
            has_map = _has_main_aux_map(db, out_ids)
            out_rows = db.query(StockTransaction).filter(StockTransaction.id.in_(out_ids)).all()
            for ot in out_rows:
                key = str(ot.id)
                flags = has_map.get(key, {"has_main": False, "has_aux": False})
                out_meta_map[key] = {
                    "source_tag": _stock_out_source_tag(ot),
                    "method_tag": _stock_out_method_tag(
                        has_main=bool(flags["has_main"]), has_aux=bool(flags["has_aux"])
                    ),
                }

        items_all = []
        for r in rows:
            out_id = str(r.out_id)
            sn = (r.serial_number or "").strip() if r.serial_number else ""
            main_device_barcode = None
            if not sn:
                pick = pickup_map.get(out_id) or {}
                pick_sn = str(pick.get("serial_number") or "").strip()
                pick_barcode = str(pick.get("main_device_barcode") or "").strip()
                if pick_sn:
                    sn = pick_sn
                if pick_barcode:
                    main_device_barcode = pick_barcode
                if not sn and pick_barcode:
                    sn = pick_barcode
            inst_id = str(r.equipment_instance_id or "")

            ret = return_map.get((out_id, inst_id))
            status_value = "picked"
            return_status = None
            return_tx_id = None
            return_doc = None
            is_returned = False
            if ret:
                return_status = ret.get("return_status")
                return_tx_id = ret.get("return_transaction_id")
                return_doc = ret.get("return_document_number")
                qty = int(ret.get("quantity") or 0)
                received_qty = int(ret.get("received_qty") or 0)
                if return_status == "received" or (qty > 0 and received_qty >= qty):
                    status_value = "returned"
                    is_returned = True
                elif return_status in {"pending_receive", "partially_received"}:
                    status_value = "pending_receive"
                elif return_status == "rejected":
                    status_value = "rejected"
            else:
                if sn and sn in installed_locked_sns:
                    status_value = "installed"

            group_counts[status_value] = int(group_counts.get(status_value, 0) or 0) + 1

            meta = out_meta_map.get(out_id, {})
            items_all.append(
                {
                    "item_type": "main",
                    "status_group": status_value,
                    "source_tag": meta.get("source_tag") or "其他",
                    "method_tag": meta.get("method_tag") or "未知",
                    "out_transaction_id": out_id,
                    "out_document_number": r.out_document_number,
                    "warehouse_id": r.warehouse_id,
                    "warehouse_name": r.warehouse_name,
                    "operation_time": to_utc_iso(r.operation_time) if r.operation_time else None,
                    "equipment_instance_id": r.equipment_instance_id,
                    "serial_number": sn,
                    "main_device_barcode": main_device_barcode,
                    "equipment_id": r.equipment_id,
                    "equipment_name": r.equipment_name,
                    "equipment_code": r.equipment_code,
                    "return_status": return_status,
                    "return_transaction_id": return_tx_id,
                    "return_document_number": return_doc,
                    "return_reject_reason": ret.get("return_reject_reason") if ret else None,
                    "is_returned": is_returned,
                }
            )

        if g:
            items_all = [it for it in items_all if it.get("status_group") == g]

        items_all.sort(key=lambda x: x.get("operation_time") or "", reverse=True)
        total = len(items_all)
        offset = (page - 1) * page_size
        items_page = items_all[offset : offset + page_size]
        has_more = offset + len(items_page) < total

        return {
            "items": items_page,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_more": has_more,
            "group_counts": group_counts,
        }

    # ===== aux =====
    group_counts["installed"] = 0  # 辅料不展示“已安装”

    query = (
        db.query(
            StockTransaction.id.label("out_id"),
            StockTransaction.document_number.label("out_document_number"),
            StockTransaction.operation_time.label("operation_time"),
            Warehouse.id.label("warehouse_id"),
            Warehouse.warehouse_name.label("warehouse_name"),
            Equipment.id.label("equipment_id"),
            Equipment.equipment_name.label("equipment_name"),
            Equipment.equipment_code.label("equipment_code"),
            Equipment.unit.label("unit"),
            func.sum(StockTransactionItem.quantity).label("out_qty"),
        )
        .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
        .join(Equipment, Equipment.id == StockTransactionItem.equipment_id)
        .outerjoin(Warehouse, Warehouse.id == StockTransaction.warehouse_id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            Equipment.category == EquipmentCategoryEnum.AUXILIARY,
            or_(StockTransaction.issued_to == current_user.id, legacy_pick_exists),
        )
        .group_by(
            StockTransaction.id,
            StockTransaction.document_number,
            StockTransaction.operation_time,
            Warehouse.id,
            Warehouse.warehouse_name,
            Equipment.id,
            Equipment.equipment_name,
            Equipment.equipment_code,
            Equipment.unit,
        )
    )

    if search:
        query = query.filter(
            or_(
                StockTransaction.document_number.like(like_contains),
                Equipment.equipment_name.like(like_contains),
                Equipment.equipment_code.like(like_contains),
            )
        )

    rows = query.order_by(desc(StockTransaction.operation_time)).all()
    out_ids = list({str(r.out_id) for r in rows if r and r.out_id})

    out_meta_map: Dict[str, dict] = {}
    if out_ids:
        has_map = _has_main_aux_map(db, out_ids)
        out_rows = db.query(StockTransaction).filter(StockTransaction.id.in_(out_ids)).all()
        for ot in out_rows:
            key = str(ot.id)
            flags = has_map.get(key, {"has_main": False, "has_aux": False})
            out_meta_map[key] = {
                "source_tag": _stock_out_source_tag(ot),
                "method_tag": _stock_out_method_tag(
                    has_main=bool(flags["has_main"]), has_aux=bool(flags["has_aux"])
                ),
            }

    aux_return_map: Dict[tuple, dict] = {}
    if out_ids:
        ret_rows = (
            db.query(
                StockTransaction.related_transaction_id.label("out_id"),
                StockTransaction.approval_status.label("return_status"),
                StockTransactionItem.equipment_id.label("equipment_id"),
                StockTransactionItem.quantity.label("quantity"),
                StockTransactionItem.received_qty.label("received_qty"),
            )
            .join(StockTransactionItem, StockTransactionItem.transaction_id == StockTransaction.id)
            .filter(
                StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                StockTransaction.related_transaction_id.in_(out_ids),
                StockTransaction.approval_status.in_(["pending_receive", "partially_received", "received"]),
                StockTransactionItem.equipment_instance_id.is_(None),
            )
            .all()
        )
        for rr in ret_rows:
            key = (str(rr.out_id), int(rr.equipment_id))
            if key not in aux_return_map:
                aux_return_map[key] = {"requested_qty": 0, "received_qty": 0}
            qty = int(rr.quantity or 0)
            if qty <= 0:
                continue
            status = str(rr.return_status or "")
            aux_return_map[key]["requested_qty"] += qty
            if status == "received":
                aux_return_map[key]["received_qty"] += qty
            else:
                aux_return_map[key]["received_qty"] += int(rr.received_qty or 0)

    items_all = []
    for r in rows:
        out_id = str(r.out_id)
        equipment_id = int(r.equipment_id)
        out_qty = int(r.out_qty or 0)
        ret = aux_return_map.get((out_id, equipment_id), {"requested_qty": 0, "received_qty": 0})

        requested = min(int(ret.get("requested_qty") or 0), out_qty)
        received = min(int(ret.get("received_qty") or 0), out_qty)
        pending = max(requested - received, 0)

        status_value = "picked"
        is_returned = False
        if out_qty > 0 and received >= out_qty:
            status_value = "returned"
            is_returned = True
        elif pending > 0:
            status_value = "pending_receive"

        group_counts[status_value] = int(group_counts.get(status_value, 0) or 0) + 1

        meta = out_meta_map.get(out_id, {})
        items_all.append(
            {
                "item_type": "aux",
                "status_group": status_value,
                "source_tag": meta.get("source_tag") or "其他",
                "method_tag": meta.get("method_tag") or "未知",
                "out_transaction_id": out_id,
                "out_document_number": r.out_document_number,
                "warehouse_id": r.warehouse_id,
                "warehouse_name": r.warehouse_name,
                "operation_time": to_utc_iso(r.operation_time) if r.operation_time else None,
                "equipment_id": equipment_id,
                "equipment_name": r.equipment_name,
                "equipment_code": r.equipment_code,
                "unit": r.unit,
                "quantity": out_qty,
                "is_returned": is_returned,
                "return_pending_qty": int(pending),
                "return_received_qty": int(received),
            }
        )

    if g:
        if g == "installed":
            items_all = []
        else:
            items_all = [it for it in items_all if it.get("status_group") == g]

    items_all.sort(key=lambda x: x.get("operation_time") or "", reverse=True)
    total = len(items_all)
    offset = (page - 1) * page_size
    items_page = items_all[offset : offset + page_size]
    has_more = offset + len(items_page) < total

    return {
        "items": items_page,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_more": has_more,
        "group_counts": group_counts,
    }


@router.post("/returns")
async def create_return_request(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """退库申请（新方案）：基于出库单明细，可选主设备SN与辅料数量。"""
    _ensure_not_surveyor(current_user)

    out_id = (payload.get("out_transaction_id") or "").strip() if isinstance(payload, dict) else ""
    return_warehouse_id = payload.get("return_warehouse_id") if isinstance(payload, dict) else None
    main_sns = payload.get("main_sns") if isinstance(payload, dict) else []
    aux_items = payload.get("aux_items") if isinstance(payload, dict) else []
    offline_document_id = payload.get("offline_document_id") if isinstance(payload, dict) else None
    offline_doc = _get_offline_document_for_use(db, current_user=current_user, offline_document_id=offline_document_id)

    if not out_id:
        raise HTTPException(status_code=400, detail="缺少 out_transaction_id")
    try:
        return_warehouse_id = int(return_warehouse_id)
    except Exception:
        raise HTTPException(status_code=400, detail="请选择退入仓库")

    return_wh = _ensure_active_warehouse(db, return_warehouse_id)

    out_trans = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment),
            joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
        )
        .filter(StockTransaction.id == out_id, StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT)
        .first()
    )
    if not out_trans:
        raise HTTPException(status_code=404, detail="出库单不存在")

    # 权限：仅允许退库自己领取的出库单
    can = out_trans.operator_id == current_user.id or out_trans.issued_to == current_user.id
    if not can:
        legacy_pick = db.query(PickupRecord.id).filter(
            PickupRecord.transaction_id == out_trans.id,
            PickupRecord.picker_id == current_user.id,
        ).first()
        can = legacy_pick is not None
    if not can:
        raise HTTPException(status_code=403, detail="无权限对该出库单发起退库")

    # 解析出库单明细：main_sn -> item / aux -> qty
    out_main_by_sn: Dict[str, StockTransactionItem] = {}
    out_aux_by_eid: Dict[int, int] = {}
    for it in out_trans.transaction_items or []:
        eq = it.equipment
        if not eq:
            continue
        cat = _enum_value(eq.category)
        if cat == EquipmentCategoryEnum.MAIN_DEVICE.value:
            sn = it.equipment_instance.serial_number if it.equipment_instance else None
            if sn:
                out_main_by_sn[str(sn).strip()] = it
        else:
            try:
                out_aux_by_eid[int(it.equipment_id)] = out_aux_by_eid.get(int(it.equipment_id), 0) + int(it.quantity or 0)
            except Exception:
                continue

    aux_reserved, main_reserved = _return_reserved_maps(db, out_trans.id)

    # 主设备去重
    picked_main_sns = []
    seen_main = set()
    for s in main_sns or []:
        sn = str(s or "").strip()
        if not sn or sn in seen_main:
            continue
        seen_main.add(sn)
        picked_main_sns.append(sn)

    aux_req_map: Dict[int, int] = {}
    for row in aux_items or []:
        if not isinstance(row, dict):
            continue
        try:
            eid = int(row.get("equipment_id"))
            qty = int(row.get("quantity") or 0)
        except Exception:
            continue
        if eid <= 0 or qty <= 0:
            continue
        aux_req_map[eid] = aux_req_map.get(eid, 0) + qty

    if not picked_main_sns and not aux_req_map:
        raise HTTPException(status_code=400, detail="请至少选择1个主设备SN或辅料数量")

    # 复用旧退库逻辑的“检查绑定”规则：若存在设备级检查绑定，需先解绑（或阻断）
    if picked_main_sns:
        blocked_bindings: List[dict] = []
        need_unbind_bindings: List[dict] = []
        for sn in picked_main_sns:
            try:
                bindings = _get_blocking_bindings(db, sn=sn, current_user=current_user)
            except Exception:
                bindings = {"need_unbind": [], "blocked": []}
            for b in (bindings.get("blocked") or []):
                try:
                    row = dict(b) if isinstance(b, dict) else {"detail": str(b)}
                except Exception:
                    row = {"detail": str(b)}
                row["sn"] = sn
                blocked_bindings.append(row)
            for b in (bindings.get("need_unbind") or []):
                try:
                    row = dict(b) if isinstance(b, dict) else {"detail": str(b)}
                except Exception:
                    row = {"detail": str(b)}
                row["sn"] = sn
                need_unbind_bindings.append(row)

        if blocked_bindings:
            raise HTTPException(
                status_code=400,
                detail={
                    "action": "unbind_blocked",
                    "message": "存在不可解绑的检查绑定，无法发起退库",
                    "blocked_bindings": blocked_bindings,
                },
            )
        if need_unbind_bindings:
            raise HTTPException(
                status_code=400,
                detail={
                    "action": "need_unbind",
                    "message": "存在设备级检查绑定，需先解绑并清理检查内容",
                    "need_unbind": need_unbind_bindings,
                },
            )

    ret_id = uuid.uuid4().hex
    ret_doc = _build_request_no("RET", current_user.id)
    ret_trans = StockTransaction(
        id=ret_id,
        transaction_type=TransactionTypeEnum.RETURN,
        warehouse_id=return_wh.id,
        operator_id=current_user.id,
        offline_document_id=offline_doc.id if offline_doc else None,
        related_transaction_id=out_trans.id,
        document_number=ret_doc,
        total_quantity=0,
        notes="退库申请",
        approval_status="pending_receive",
    )
    db.add(ret_trans)
    db.flush()

    total_qty = 0

    # 主设备行
    for sn in picked_main_sns:
        out_item = out_main_by_sn.get(sn)
        if not out_item:
            raise HTTPException(status_code=400, detail=f"主设备SN不在该出库单中：{sn}")
        if out_item.equipment_instance_id and str(out_item.equipment_instance_id) in main_reserved:
            raise HTTPException(status_code=400, detail=f"该主设备已存在退库申请：{sn}")

        inst = out_item.equipment_instance
        if inst and _enum_value(inst.status) == InventoryStatusEnum.RETURN_PENDING_RECEIVE.value:
            raise HTTPException(status_code=400, detail=f"设备已处于退库待收货：{sn}")

        db.add(
            StockTransactionItem(
                transaction_id=ret_id,
                equipment_instance_id=out_item.equipment_instance_id,
                equipment_id=out_item.equipment_id,
                quantity=1,
                received_qty=0,
            )
        )
        total_qty += 1

        # 标记主设备进入退库待收货
        if inst:
            inst.status = InventoryStatusEnum.RETURN_PENDING_RECEIVE
            inst.updated_at = datetime.now()

    # 辅料行
    for eid, qty in aux_req_map.items():
        out_qty = int(out_aux_by_eid.get(int(eid), 0))
        if out_qty <= 0:
            raise HTTPException(status_code=400, detail="辅料不在该出库单中")
        reserved = int(aux_reserved.get(int(eid), 0))
        max_returnable = max(out_qty - reserved, 0)
        if qty > max_returnable:
            raise HTTPException(status_code=400, detail="辅料数量超过可退上限")

        db.add(
            StockTransactionItem(
                transaction_id=ret_id,
                equipment_id=int(eid),
                quantity=int(qty),
                received_qty=0,
            )
        )
        total_qty += int(qty)

    ret_trans.total_quantity = total_qty
    db.commit()
    return {"return_transaction_id": ret_id, "document_number": ret_doc, "status": ret_trans.approval_status}


@router.post("/returns/by-sns")
async def create_return_request_by_sns(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按主设备 SN 批量发起退库申请（待仓库收货）。

    - 支持一次勾选多个 SN
    - 自动按“原出库单”分组生成一条或多条退库单
    - 权限以“当前设备归属(EquipmentInstance.issued_to)”为准，支持设备更换后的归属交接场景
    """
    _ensure_not_surveyor(current_user)

    sns = payload.get("sns") if isinstance(payload, dict) else []
    return_warehouse_id = payload.get("return_warehouse_id") if isinstance(payload, dict) else None
    offline_document_id = payload.get("offline_document_id") if isinstance(payload, dict) else None
    notes = (payload.get("notes") or "").strip() if isinstance(payload, dict) else ""
    work_order_id = (payload.get("work_order_id") or "").strip() if isinstance(payload, dict) else ""
    offline_doc = _get_offline_document_for_use(db, current_user=current_user, offline_document_id=offline_document_id)

    if not isinstance(sns, list) or not sns:
        raise HTTPException(status_code=400, detail="请至少选择1个主设备SN")

    # SN 去重
    picked = []
    seen = set()
    for s in sns:
        sn = str(s or "").strip()
        if not sn or sn in seen:
            continue
        seen.add(sn)
        picked.append(sn)
    if not picked:
        raise HTTPException(status_code=400, detail="请至少选择1个主设备SN")

    # 可选：统一退入仓库；不传则按原出库单 warehouse_id 回库
    default_return_wh = None
    if return_warehouse_id is not None and return_warehouse_id != "":
        try:
            default_return_wh = _ensure_active_warehouse(db, int(return_warehouse_id))
        except Exception:
            raise HTTPException(status_code=400, detail="请选择有效的退入仓库")

    # 预加载设备实例并校验“当前归属”
    inst_rows = db.query(EquipmentInstance).filter(EquipmentInstance.serial_number.in_(picked)).all()
    inst_by_sn = {str(i.serial_number).strip(): i for i in inst_rows if i and i.serial_number}

    missing = [sn for sn in picked if sn not in inst_by_sn]
    if missing:
        raise HTTPException(status_code=404, detail=f"设备SN不存在：{', '.join(missing[:10])}")

    forbidden = [sn for sn, inst in inst_by_sn.items() if getattr(inst, "issued_to", None) != current_user.id]
    if forbidden:
        raise HTTPException(status_code=403, detail=f"无权限退库（设备不在当前用户名下）：{', '.join(forbidden[:10])}")

    # 退库阻断：仍存在“当前绑定”的设备级检查项需要先解绑
    blocked_bindings: List[dict] = []
    need_unbind_bindings: List[dict] = []
    for sn in picked:
        try:
            bindings = _get_blocking_bindings(db, sn=sn, current_user=current_user)
        except Exception:
            bindings = {"need_unbind": [], "blocked": []}
        for b in (bindings.get("blocked") or []):
            try:
                row = dict(b) if isinstance(b, dict) else {"detail": str(b)}
            except Exception:
                row = {"detail": str(b)}
            row["sn"] = sn
            blocked_bindings.append(row)
        for b in (bindings.get("need_unbind") or []):
            try:
                row = dict(b) if isinstance(b, dict) else {"detail": str(b)}
            except Exception:
                row = {"detail": str(b)}
            row["sn"] = sn
            need_unbind_bindings.append(row)

    if blocked_bindings:
        raise HTTPException(
            status_code=400,
            detail={
                "action": "unbind_blocked",
                "message": "存在不可解绑的检查绑定，无法发起退库",
                "blocked_bindings": blocked_bindings,
            },
        )
    if need_unbind_bindings:
        raise HTTPException(
            status_code=400,
            detail={
                "action": "need_unbind",
                "message": "存在设备级检查绑定，需先解绑并清理检查内容",
                "need_unbind": need_unbind_bindings,
            },
        )

    # 解析每个 SN 对应的“最近一笔出库单”（允许历史多次出库/退库/再出库）
    inst_ids = [i.id for i in inst_rows]
    out_rows = (
        db.query(StockTransactionItem.equipment_instance_id, StockTransaction.id, StockTransaction.operation_time)
        .join(StockTransaction, StockTransaction.id == StockTransactionItem.transaction_id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransactionItem.equipment_instance_id.in_(inst_ids),
        )
        .order_by(desc(StockTransaction.operation_time))
        .all()
    )
    out_by_inst = {}
    for inst_id, out_id, _ in out_rows:
        if not inst_id or not out_id:
            continue
        if str(inst_id) in out_by_inst:
            continue
        out_by_inst[str(inst_id)] = str(out_id)

    missing_out = [sn for sn, inst in inst_by_sn.items() if str(inst.id) not in out_by_inst]
    if missing_out:
        raise HTTPException(status_code=400, detail=f"未找到可追溯的出库单：{', '.join(missing_out[:10])}")

    # 按出库单分组
    group: Dict[str, List[str]] = {}
    for sn in picked:
        inst = inst_by_sn.get(sn)
        if not inst:
            continue
        out_id = out_by_inst.get(str(inst.id))
        if not out_id:
            continue
        group.setdefault(out_id, []).append(sn)

    created = []
    now = datetime.now()

    # 逐出库单创建退库单
    for out_id, sns_group in group.items():
        out_trans = (
            db.query(StockTransaction)
            .options(
                joinedload(StockTransaction.warehouse),
                joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
                joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment),
            )
            .filter(StockTransaction.id == out_id, StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT)
            .first()
        )
        if not out_trans:
            raise HTTPException(status_code=404, detail=f"出库单不存在：{out_id}")

        return_wh = default_return_wh or _ensure_active_warehouse(db, int(out_trans.warehouse_id))

        # 去重
        sns_group = [s for s in dict.fromkeys(sns_group) if s]

        # 已存在退库申请：阻断
        _, main_reserved = _return_reserved_maps(db, out_trans.id)
        for sn in sns_group:
            inst = inst_by_sn.get(sn)
            if inst and str(inst.id) in main_reserved:
                raise HTTPException(status_code=400, detail=f"该主设备已存在退库申请：{sn}")
            if inst and _enum_value(inst.status) == InventoryStatusEnum.RETURN_PENDING_RECEIVE.value:
                raise HTTPException(status_code=400, detail=f"设备已处于退库待收货：{sn}")

        ret_id = uuid.uuid4().hex
        ret_doc = _build_request_no("RET", current_user.id)

        loc = {"_source": "batch_return_by_sns"}
        if work_order_id:
            loc["work_order_id"] = work_order_id

        ret_trans = StockTransaction(
            id=ret_id,
            transaction_type=TransactionTypeEnum.RETURN,
            warehouse_id=return_wh.id,
            operator_id=current_user.id,
            offline_document_id=offline_doc.id if offline_doc else None,
            related_transaction_id=out_trans.id,
            document_number=ret_doc,
            total_quantity=len(sns_group),
            notes=notes or ("设备更换退库申请" if work_order_id else "批量退库申请"),
            approval_status="pending_receive",
            scan_location=loc,
        )
        db.add(ret_trans)
        db.flush()

        for sn in sns_group:
            inst = inst_by_sn.get(sn)
            if not inst:
                continue
            db.add(
                StockTransactionItem(
                    transaction_id=ret_id,
                    equipment_instance_id=inst.id,
                    equipment_id=inst.equipment_id,
                    quantity=1,
                    received_qty=0,
                )
            )
            inst.status = InventoryStatusEnum.RETURN_PENDING_RECEIVE
            inst.updated_at = now

        created.append(
            {
                "out_transaction_id": out_trans.id,
                "out_document_number": out_trans.document_number,
                "return_transaction_id": ret_id,
                "return_document_number": ret_doc,
                "return_warehouse_id": return_wh.id,
                "return_warehouse_name": return_wh.warehouse_name if return_wh else None,
                "sns": sns_group,
                "status": ret_trans.approval_status,
            }
        )

    db.commit()
    return {"created_count": len(created), "created": created}


def _serialize_return_transaction(db: Session, t: StockTransaction) -> dict:
    out_trans = db.query(StockTransaction).options(joinedload(StockTransaction.warehouse)).filter(
        StockTransaction.id == t.related_transaction_id
    ).first() if t.related_transaction_id else None

    items = []
    for it in t.transaction_items or []:
        eq = it.equipment
        cat = _enum_value(eq.category) if eq else None
        is_main = cat == EquipmentCategoryEnum.MAIN_DEVICE.value
        sn = it.equipment_instance.serial_number if it.equipment_instance else None
        received_qty = int(getattr(it, "received_qty", 0) or 0)
        qty = int(it.quantity or 0)
        pending_qty = max(qty - received_qty, 0)
        items.append(
            {
                "item_id": it.id,
                "equipment_id": it.equipment_id,
                "equipment_name": eq.equipment_name if eq else None,
                "equipment_code": eq.equipment_code if eq else None,
                "unit": getattr(eq, "unit", None) if eq else None,
                "quantity": qty,
                "received_quantity": received_qty,
                "pending_quantity": pending_qty,
                "is_main_device": is_main,
                "serial_number": sn,
                "max_returnable": 0,
            }
        )

    return {
        "id": t.id,
        "document_number": t.document_number,
        "warehouse_id": t.warehouse_id,
        "warehouse_name": t.warehouse.warehouse_name if t.warehouse else None,
        "operator_id": t.operator_id,
        "operator_name": t.operator.full_name if t.operator and t.operator.full_name else (t.operator.username if t.operator else None),
        "status": t.approval_status,
        "created_at": to_utc_iso(t.created_at) if t.created_at else None,
        "operation_time": to_utc_iso(t.operation_time) if t.operation_time else None,
        "out_transaction_id": t.related_transaction_id,
        "out_document_number": out_trans.document_number if out_trans else None,
        "out_warehouse_id": out_trans.warehouse_id if out_trans else None,
        "out_warehouse_name": out_trans.warehouse.warehouse_name if out_trans and out_trans.warehouse else None,
        "items": items,
        "approval_comments": t.approval_comments,
    }


@router.get("/my-returns")
async def list_my_returns(
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_not_surveyor(current_user)

    try:
        page = int(page or 1)
    except Exception:
        page = 1
    page = max(1, page)

    try:
        page_size = int(page_size or 20)
    except Exception:
        page_size = 20
    page_size = max(1, min(page_size, 50))

    query = db.query(StockTransaction).options(
        joinedload(StockTransaction.warehouse),
        joinedload(StockTransaction.operator),
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment),
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
    ).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
        StockTransaction.operator_id == current_user.id,
    )

    if status_filter and status_filter != "all":
        query = query.filter(StockTransaction.approval_status == status_filter)

    total = query.count()
    rows = (
        query.order_by(desc(StockTransaction.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"records": [_serialize_return_transaction(db, t) for t in rows], "total": total}


def _out_is_flow_v2(out_trans: StockTransaction) -> bool:
    loc = out_trans.scan_location if isinstance(out_trans.scan_location, dict) else {}
    try:
        return int(loc.get("_stock_flow_version", 0) or 0) == 2
    except Exception:
        return False


@router.get("/returns")
async def list_return_workbench(
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
    """仓库侧退库收货工作台（新方案）。"""
    _ensure_stock_operator(current_user)

    try:
        skip = int(skip or 0)
    except Exception:
        skip = 0
    skip = max(0, skip)

    try:
        limit = int(limit or 50)
    except Exception:
        limit = 50
    limit = max(1, min(limit, 200))

    query = db.query(StockTransaction).options(
        joinedload(StockTransaction.warehouse),
        joinedload(StockTransaction.operator),
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment),
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
    ).filter(
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
    )

    managed_ids = _get_managed_warehouse_ids(db, current_user)
    if managed_ids is not None:
        query = query.filter(StockTransaction.warehouse_id.in_(list(managed_ids)))

    # 仓库筛选：支持单仓/多仓
    warehouse_id_list = []
    if warehouse_ids:
        for part in str(warehouse_ids).split(","):
            part = part.strip()
            if not part:
                continue
            try:
                warehouse_id_list.append(int(part))
            except Exception:
                continue
    if warehouse_id:
        try:
            warehouse_id_list.append(int(warehouse_id))
        except Exception:
            pass
    if warehouse_id_list:
        query = query.filter(StockTransaction.warehouse_id.in_(list(set(warehouse_id_list))))

    # 状态筛选：pending_receive 默认包含 partially_received（都需要继续收货）
    if status_filter and status_filter != "all":
        if status_filter == "pending_receive":
            query = query.filter(StockTransaction.approval_status.in_(["pending_receive", "partially_received"]))
        else:
            query = query.filter(StockTransaction.approval_status == status_filter)

    # SN 精确定位
    if sn:
        snv = str(sn).strip()
        if snv:
            query = (
                query.join(StockTransaction.transaction_items)
                .join(EquipmentInstance, StockTransactionItem.equipment_instance_id == EquipmentInstance.id)
                .filter(EquipmentInstance.serial_number == snv)
            )

    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        out_alias = aliased(StockTransaction)
        query = query.outerjoin(out_alias, StockTransaction.related_transaction_id == out_alias.id).filter(
            or_(
                StockTransaction.document_number.like(like),
                StockTransaction.scan_barcode.like(like),
                StockTransaction.approval_comments.like(like),
                out_alias.document_number.like(like),
            )
        )

    total = query.count()
    rows = query.order_by(desc(StockTransaction.created_at)).offset(skip).limit(limit).all()

    return {"records": [_serialize_return_transaction(db, t) for t in rows], "total": total}


@router.get("/returns/{return_id}")
async def get_return_detail(
    return_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_stock_operator(current_user)

    t = db.query(StockTransaction).options(
        joinedload(StockTransaction.warehouse),
        joinedload(StockTransaction.operator),
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment),
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
    ).filter(
        StockTransaction.id == return_id,
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="退库单不存在")

    managed_ids = _get_managed_warehouse_ids(db, current_user)
    if managed_ids is not None and t.warehouse_id not in managed_ids:
        raise HTTPException(status_code=403, detail="无权限查看该仓库的退库单")

    return {"record": _serialize_return_transaction(db, t)}


@router.post("/returns/{return_id}/receive")
async def receive_return_items(
    return_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """仓库收货确认（支持部分收货）。"""
    _ensure_warehouse_operator(current_user)

    main_sns = payload.get("main_sns") if isinstance(payload, dict) else []
    aux_items = payload.get("aux_items") if isinstance(payload, dict) else []
    receive_notes = (payload.get("receive_notes") or "").strip() if isinstance(payload, dict) else ""

    t = db.query(StockTransaction).options(
        joinedload(StockTransaction.warehouse),
        joinedload(StockTransaction.operator),
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment),
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
    ).filter(
        StockTransaction.id == return_id,
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="退库单不存在")
    if t.approval_status not in {"pending_receive", "partially_received"}:
        raise HTTPException(status_code=400, detail="退库单状态不可收货确认")

    managed_ids = _get_managed_warehouse_ids(db, current_user)
    if managed_ids is not None and t.warehouse_id not in managed_ids:
        raise HTTPException(status_code=403, detail="无权限处理该仓库的退库单")

    out_id = getattr(t, "related_transaction_id", None)
    if not out_id:
        raise HTTPException(status_code=400, detail="缺少关联出库单，无法收货")

    out_trans = db.query(StockTransaction).options(joinedload(StockTransaction.warehouse)).filter(
        StockTransaction.id == out_id,
        StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
    ).first()
    if not out_trans:
        raise HTTPException(status_code=404, detail="关联出库单不存在")

    source_warehouse_id = out_trans.warehouse_id
    target_warehouse_id = t.warehouse_id
    is_flow_v2 = _out_is_flow_v2(out_trans)

    # 规范化输入
    main_sn_list = []
    seen = set()
    for s in main_sns or []:
        sn = str(s or "").strip()
        if not sn or sn in seen:
            continue
        seen.add(sn)
        main_sn_list.append(sn)

    aux_receive_map: Dict[int, int] = {}
    for row in aux_items or []:
        if not isinstance(row, dict):
            continue
        try:
            eid = int(row.get("equipment_id"))
            qty = int(row.get("quantity") or 0)
        except Exception:
            continue
        if eid <= 0 or qty <= 0:
            continue
        aux_receive_map[eid] = aux_receive_map.get(eid, 0) + qty

    if not main_sn_list and not aux_receive_map:
        raise HTTPException(status_code=400, detail="请至少选择1个SN或填写辅料收货数量")

    # 建立退库单明细索引
    main_item_by_sn: Dict[str, StockTransactionItem] = {}
    aux_item_by_eid: Dict[int, StockTransactionItem] = {}
    for it in t.transaction_items or []:
        if it.equipment_instance_id and it.equipment_instance:
            main_item_by_sn[str(it.equipment_instance.serial_number or "").strip()] = it
        else:
            try:
                aux_item_by_eid[int(it.equipment_id)] = it
            except Exception:
                continue

    receive_requirements: Dict[int, int] = {}
    now = datetime.now()

    # 主设备收货
    main_items_to_receive: List[StockTransactionItem] = []
    for snv in main_sn_list:
        it = main_item_by_sn.get(snv)
        if not it:
            raise HTTPException(status_code=400, detail=f"退库单中不存在该SN：{snv}")
        pending_qty = max(int(it.quantity or 0) - int(getattr(it, "received_qty", 0) or 0), 0)
        if pending_qty <= 0:
            raise HTTPException(status_code=400, detail=f"该SN已收货：{snv}")
        main_items_to_receive.append(it)
        receive_requirements[int(it.equipment_id)] = receive_requirements.get(int(it.equipment_id), 0) + 1

    # 辅料收货
    for eid, qty in aux_receive_map.items():
        it = aux_item_by_eid.get(int(eid))
        if not it:
            raise HTTPException(status_code=400, detail="退库单中不存在该辅料")
        pending_qty = max(int(it.quantity or 0) - int(getattr(it, "received_qty", 0) or 0), 0)
        if qty > pending_qty:
            raise HTTPException(status_code=400, detail="辅料收货数量不能超过待收货数量")
        receive_requirements[int(it.equipment_id)] = receive_requirements.get(int(it.equipment_id), 0) + int(qty)

    # 库存回滚（按本次收货量）
    for equipment_id, qty in receive_requirements.items():
        qty = int(qty)
        if qty <= 0:
            continue

        if source_warehouse_id == target_warehouse_id:
            inv = db.query(Inventory).filter(
                and_(Inventory.warehouse_id == source_warehouse_id, Inventory.equipment_id == equipment_id)
            ).first()
            if not inv or int(inv.allocated_stock or 0) < qty:
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
                if not inv_src or int(inv_src.allocated_stock or 0) < qty:
                    raise HTTPException(status_code=400, detail="库存回滚失败：源仓已分配库存不足")
                inv_src.allocated_stock -= qty
            else:
                if (
                    not inv_src
                    or int(inv_src.allocated_stock or 0) < qty
                    or int(inv_src.current_stock or 0) < qty
                ):
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

    # 更新退库明细已收货数 + 主设备实例回库
    for it in main_items_to_receive:
        it.received_qty = int(getattr(it, "received_qty", 0) or 0) + 1
        inst = it.equipment_instance
        if inst:
            inst.status = InventoryStatusEnum.IN_STOCK
            inst.issued_to = None
            inst.issued_date = None
            inst.warehouse_id = target_warehouse_id
            inst.updated_at = now

    for eid, qty in aux_receive_map.items():
        it = aux_item_by_eid.get(int(eid))
        if not it:
            continue
        it.received_qty = int(getattr(it, "received_qty", 0) or 0) + int(qty)

    # 更新退库单状态
    any_received = any(int(getattr(it, "received_qty", 0) or 0) > 0 for it in (t.transaction_items or []))
    all_received = all(int(getattr(it, "received_qty", 0) or 0) >= int(it.quantity or 0) for it in (t.transaction_items or []))

    if all_received:
        t.approval_status = "received"
    elif any_received:
        t.approval_status = "partially_received"
    else:
        t.approval_status = "pending_receive"

    t.approved_by = current_user.id
    t.approved_at = now
    if receive_notes:
        t.approval_comments = receive_notes

    # 若已全部收货，标记老的 PickupRecord 已归还（兼容旧“我的设备”列表）
    # 仅当退库单包含主设备明细时才更新，避免“仅退辅料”把主设备误标为已退库
    if t.approval_status == "received" and out_trans.id and t.operator_id:
        returned_instance_ids = list(
            {
                str(getattr(it, "equipment_instance_id"))
                for it in (t.transaction_items or [])
                if getattr(it, "equipment_instance_id", None)
            }
        )
        if returned_instance_ids:
            pickup_rows = db.query(PickupRecord).filter(
                PickupRecord.transaction_id == out_trans.id,
                PickupRecord.picker_id == t.operator_id,
                PickupRecord.is_returned == False,
                PickupRecord.equipment_instance_id.in_(returned_instance_ids),
            ).all()
            for pr in pickup_rows:
                pr.is_returned = True
                pr.returned_at = now
                pr.return_notes = receive_notes or "仓库已收货确认"

            # 兼容：极少数历史数据 pickup_record 未关联 equipment_instance_id
            if not pickup_rows:
                pickup_record = db.query(PickupRecord).filter(
                    PickupRecord.transaction_id == out_trans.id,
                    PickupRecord.picker_id == t.operator_id,
                    PickupRecord.is_returned == False,
                ).order_by(desc(PickupRecord.pickup_time)).first()
                if pickup_record and not getattr(pickup_record, "equipment_instance_id", None):
                    pickup_record.is_returned = True
                    pickup_record.returned_at = now
                    pickup_record.return_notes = receive_notes or "仓库已收货确认"

    db.commit()
    return {"message": "收货确认成功", "return_status": t.approval_status}


@router.post("/returns/{return_id}/reject")
async def reject_return_request(
    return_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """仓库拒收：仅 pending_receive 且未发生部分收货。"""
    _ensure_warehouse_operator(current_user)

    reason = (payload.get("reason") or "").strip() if isinstance(payload, dict) else ""
    if not reason:
        raise HTTPException(status_code=400, detail="请填写拒收原因")

    t = db.query(StockTransaction).options(
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
    ).filter(
        StockTransaction.id == return_id,
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="退库单不存在")
    if t.approval_status != "pending_receive":
        raise HTTPException(status_code=400, detail="当前状态不可拒收")

    if any(int(getattr(it, "received_qty", 0) or 0) > 0 for it in (t.transaction_items or [])):
        raise HTTPException(status_code=400, detail="已发生部分收货，不能拒收")

    managed_ids = _get_managed_warehouse_ids(db, current_user)
    if managed_ids is not None and t.warehouse_id not in managed_ids:
        raise HTTPException(status_code=403, detail="无权限处理该仓库的退库单")

    now = datetime.now()
    t.approval_status = "rejected"
    t.approved_by = current_user.id
    t.approved_at = now
    t.approval_comments = reason

    # 设备回退到已出库状态
    for it in t.transaction_items or []:
        inst = it.equipment_instance
        if not inst:
            continue
        if _enum_value(inst.status) == InventoryStatusEnum.RETURN_PENDING_RECEIVE.value:
            inst.status = InventoryStatusEnum.ISSUED
            inst.updated_at = now

    db.commit()
    return {"message": "已拒收", "return_status": t.approval_status}


@router.post("/returns/{return_id}/cancel")
async def cancel_return_request(
    return_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """申请人取消退库：仅 pending_receive 且未发生部分收货。"""
    _ensure_not_surveyor(current_user)
    reason = (payload.get("reason") or "").strip() if isinstance(payload, dict) else ""

    t = db.query(StockTransaction).options(
        joinedload(StockTransaction.transaction_items).joinedload(StockTransactionItem.equipment_instance),
    ).filter(
        StockTransaction.id == return_id,
        StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="退库单不存在")
    if t.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限取消该退库单")
    if t.approval_status != "pending_receive":
        raise HTTPException(status_code=400, detail="当前状态不可取消")

    if any(int(getattr(it, "received_qty", 0) or 0) > 0 for it in (t.transaction_items or [])):
        raise HTTPException(status_code=400, detail="已发生部分收货，不能取消")

    now = datetime.now()
    t.approval_status = "canceled"
    if reason:
        t.approval_comments = reason

    for it in t.transaction_items or []:
        inst = it.equipment_instance
        if not inst:
            continue
        if _enum_value(inst.status) == InventoryStatusEnum.RETURN_PENDING_RECEIVE.value:
            inst.status = InventoryStatusEnum.ISSUED
            inst.updated_at = now

    db.commit()
    return {"message": "已取消", "return_status": t.approval_status}
