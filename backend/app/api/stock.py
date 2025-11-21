from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
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

router = APIRouter()

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
            "last_updated_at": inv.last_updated_at.isoformat() if inv.last_updated_at else None
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
            "operation_time": trans.operation_time.isoformat() if trans.operation_time else None,
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
    
    if not barcode:
        raise HTTPException(status_code=400, detail="条码不能为空")
    
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
                "picked_at": existing_pickup.pickup_time.isoformat() if existing_pickup.pickup_time else None
            }

    # 若设备实例已被他人领料，则禁止重复领料
    if equipment_instance and equipment_instance.issued_to and equipment_instance.issued_to != current_user.id:
        raise HTTPException(status_code=403, detail="设备已被其他用户领料，无法重复领料")
    
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
    
    # 4. 检查库存是否足够
    shortage_items = []
    for item in package.package_items:
        inventory = db.query(Inventory).filter(
            and_(
                Inventory.equipment_id == item.equipment_id,
                Inventory.available_stock >= item.quantity
            )
        ).first()
        
        if not inventory or inventory.available_stock < item.quantity:
            shortage_items.append({
                "equipment_name": item.equipment.equipment_name,
                "required": item.quantity,
                "available": inventory.available_stock if inventory else 0
            })
    
    if shortage_items:
        return {
            "action": "insufficient_stock",
            "shortage_items": shortage_items
        }
    
    # 5. 执行出库操作
    transaction_id = str(uuid.uuid4())
    document_number = f"OUT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_user.id}"
    
    # 创建出库记录
    transaction = StockTransaction(
        id=transaction_id,
        transaction_type=TransactionTypeEnum.STOCK_OUT,
        warehouse_id=1,  # 默认仓库
        work_order_id=work_order_id,
        package_id=package.id,
        operator_id=current_user.id,
        scan_barcode=barcode,
        scan_time=datetime.now(),
        scan_location=gps_location,
        document_number=document_number,
        total_quantity=sum([item.quantity for item in package.package_items]),
        notes=f"扫码出库 - {package.package_name}"
    )
    db.add(transaction)
    
    # 创建明细和更新库存
    checkout_items = []
    for item in package.package_items:
        # 创建出库明细
        transaction_item = StockTransactionItem(
            transaction_id=transaction_id,
            equipment_id=item.equipment_id,
            quantity=item.quantity,
        )
        db.add(transaction_item)
        
        # 更新库存
        inventory = db.query(Inventory).filter(
            Inventory.equipment_id == item.equipment_id
        ).first()
        
        if inventory:
            inventory.available_stock -= item.quantity
            inventory.allocated_stock += item.quantity
        
        checkout_items.append({
            "equipment_name": item.equipment.equipment_name,
            "equipment_code": item.equipment.equipment_code,
            "quantity": item.quantity,
            "unit": item.equipment.unit
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
        "pickup_time": datetime.now().isoformat()
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取我的领料记录"""
    query = db.query(PickupRecord).filter(PickupRecord.picker_id == current_user.id)
    
    if start_date:
        query = query.filter(PickupRecord.pickup_time >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(PickupRecord.pickup_time <= datetime.fromisoformat(end_date))
    
    records = query.order_by(desc(PickupRecord.pickup_time)).all()
    
    result = []
    for record in records:
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
            "pickup_time": record.pickup_time.isoformat() if record.pickup_time else None,
            "is_confirmed": record.is_confirmed,
            "is_returned": record.is_returned,
            "returned_at": record.returned_at.isoformat() if record.returned_at else None,
            "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
            "work_order_id": record.work_order_id
        })
    
    return {"pickup_records": result}

# ===== 归还管理 =====

@router.post("/return-pickup")
async def return_equipment_pickup(
    return_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """归还领料：将未归还的领料记录标记为已归还，并把设备实例状态恢复为在库。

    入参支持：
    - pickup_record_id: 直接指定领料记录ID（优先）
    - serial_number: 通过SN定位当前用户的活动领料记录
    - warehouse_id: 可选，归还入库的仓库，未提供则不修改仓库或采用默认1（如存在）
    - notes: 可选归还备注
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

    # 标记归还
    pickup_record.is_returned = True
    pickup_record.returned_at = datetime.now()
    pickup_record.return_notes = notes

    # 设备实例回库处理
    equipment_instance = None
    if pickup_record.equipment_instance_id:
        equipment_instance = db.query(EquipmentInstance).filter(
            EquipmentInstance.id == pickup_record.equipment_instance_id
        ).first()
    elif pickup_record.serial_number:
        equipment_instance = db.query(EquipmentInstance).filter(
            EquipmentInstance.serial_number == pickup_record.serial_number
        ).first()

    if equipment_instance:
        # 将设备置回在库，并清空领料信息
        equipment_instance.status = InventoryStatusEnum.IN_STOCK
        equipment_instance.issued_to = None
        equipment_instance.issued_date = None
        # 归还仓库逻辑：优先使用传入的 warehouse_id；如未提供且仓库1存在则设为1
        if warehouse_id is not None:
            equipment_instance.warehouse_id = warehouse_id
        else:
            # 若当前无仓库，尝试设为1（容错）
            if equipment_instance.warehouse_id is None:
                default_wh = db.query(Warehouse).filter(Warehouse.id == 1).first()
                if default_wh:
                    equipment_instance.warehouse_id = 1
        equipment_instance.updated_at = datetime.now()

    db.commit()

    return {
        "message": "归还成功",
        "pickup_record_id": pickup_record.id,
        "serial_number": pickup_record.serial_number,
        "returned_at": pickup_record.returned_at.isoformat() if pickup_record.returned_at else None
    }

# ===== 入库管理 =====

@router.post("/stock-in")
async def create_stock_in(
    stock_in_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建入库单"""
    if current_user.role not in ["admin", "warehouse_manager"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
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
                last_updated_by=current_user.id
            )
            db.add(new_inventory)
    
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
        query = query.filter(StockTransaction.operation_time >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(StockTransaction.operation_time <= datetime.fromisoformat(end_date))
    
    # 非管理员只能查看自己的记录
    if current_user.role not in ["admin", "warehouse_manager"]:
        query = query.filter(StockTransaction.operator_id == current_user.id)
    
    transactions = query.order_by(desc(StockTransaction.operation_time)).offset(skip).limit(limit).all()
    
    result = []
    for trans in transactions:
        # 获取明细
        items = []
        for item in trans.transaction_items:
            serial_number = item.equipment_instance.serial_number if item.equipment_instance else None
            items.append({
                "equipment_name": item.equipment.equipment_name,
                "equipment_code": item.equipment.equipment_code,
                "quantity": item.quantity,
                "unit": item.equipment.unit,
                "serial_number": serial_number,
            })
        
        result.append({
            "id": trans.id,
            "document_number": trans.document_number,
            "transaction_type": trans.transaction_type,
            "warehouse_id": trans.warehouse_id,
            "operator_name": trans.operator.full_name if trans.operator else None,
            "operation_time": trans.operation_time.isoformat() if trans.operation_time else None,
            "total_quantity": trans.total_quantity,
            "approval_status": trans.approval_status,
            "scan_barcode": trans.scan_barcode,
            "notes": trans.notes,
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
    
    if current_user.role not in ["admin", "warehouse_manager"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
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
                            main_inv.current_stock += extra.current_stock
                            main_inv.available_stock += extra.available_stock
                            db.delete(extra)
                    # 然后再加上本次导入的 1 台
                    main_inv.current_stock += 1
                    main_inv.available_stock += 1
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
            "import_date": record.import_date.isoformat() if record.import_date else None,
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
            "error_message": detail.error_message
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
                "created_at": existing.created_at.isoformat() if existing.created_at else None
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取设备实例列表"""
    query = db.query(EquipmentInstance).filter(EquipmentInstance.equipment_id == equipment_id)
    
    if status:
        query = query.filter(EquipmentInstance.status == status)
    
    instances = query.order_by(desc(EquipmentInstance.created_at)).all()
    
    result = []
    for instance in instances:
        result.append({
            "id": instance.id,
            "serial_number": instance.serial_number,
            "barcode": instance.barcode,
            "mac_address": instance.mac_address,
            "imei": instance.imei,
            "firmware_version": instance.firmware_version,
            "hardware_version": instance.hardware_version,
            "manufacture_date": instance.manufacture_date.isoformat() if instance.manufacture_date else None,
            "warranty_start_date": instance.warranty_start_date.isoformat() if instance.warranty_start_date else None,
            "warranty_end_date": instance.warranty_end_date.isoformat() if instance.warranty_end_date else None,
            "vendor": instance.vendor,
            "batch_number": instance.batch_number,
            "quality_status": instance.quality_status,
            "status": instance.status,
            "location": instance.location,
            "warehouse_name": instance.warehouse.warehouse_name if instance.warehouse else None,
            "created_at": instance.created_at.isoformat() if instance.created_at else None
        })
    
    return {"instances": result}
