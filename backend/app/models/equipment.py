from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean, Enum, Float, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum
from datetime import datetime

class EquipmentCategoryEnum(str, enum.Enum):
    MAIN_DEVICE = "main_device"      # 主设备
    AUXILIARY = "auxiliary"           # 辅材

class EquipmentStatusEnum(str, enum.Enum):
    ACTIVE = "active"                # 启用
    INACTIVE = "inactive"            # 停用
    DISCONTINUED = "discontinued"     # 已停产

class InventoryStatusEnum(str, enum.Enum):
    IN_STOCK = "in_stock"            # 库存中
    ALLOCATED = "allocated"          # 已分配
    ISSUED = "issued"                # 已出库
    RETURNED = "returned"            # 已退库
    DAMAGED = "damaged"              # 损坏

class TransactionTypeEnum(str, enum.Enum):
    STOCK_IN = "stock_in"            # 入库
    STOCK_OUT = "stock_out"          # 出库
    TRANSFER = "transfer"            # 调拨
    RETURN = "return"                # 退库
    ADJUSTMENT = "adjustment"        # 调整
    DAMAGE = "damage"                # 报损

class Equipment(Base):
    """设备型号表"""
    __tablename__ = "equipment"
    
    id = Column(Integer, primary_key=True, index=True)
    equipment_code = Column(String(50), unique=True, index=True, nullable=False)  # 设备编码
    equipment_name = Column(String(100), nullable=False)  # 设备名称
    category = Column(Enum(EquipmentCategoryEnum), nullable=False)  # 设备类别
    model = Column(String(100))  # 型号
    brand = Column(String(50))  # 品牌
    specifications = Column(JSON)  # 技术规格参数
    unit = Column(String(20), default="台")  # 计量单位
    barcode_prefix = Column(String(10))  # 条码前缀
    description = Column(Text)  # 描述说明
    status = Column(Enum(EquipmentStatusEnum), default=EquipmentStatusEnum.ACTIVE)
    
    # 系统字段
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    creator = relationship("User", foreign_keys=[created_by])
    package_items = relationship("EquipmentPackageItem", back_populates="equipment")
    inventory_records = relationship("Inventory", back_populates="equipment")

class EquipmentPackage(Base):
    """设备套装配置表"""
    __tablename__ = "equipment_packages"
    
    id = Column(Integer, primary_key=True, index=True)
    package_code = Column(String(50), unique=True, index=True, nullable=False)  # 套装编码
    package_name = Column(String(100), nullable=False)  # 套装名称
    main_equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)  # 主设备
    site_type = Column(String(50))  # 适用站点类型
    description = Column(Text)  # 套装描述
    is_template = Column(Boolean, default=True)  # 是否为模板
    status = Column(Enum(EquipmentStatusEnum), default=EquipmentStatusEnum.ACTIVE)
    
    # 系统字段  
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    main_equipment = relationship("Equipment", foreign_keys=[main_equipment_id])
    creator = relationship("User", foreign_keys=[created_by])
    package_items = relationship("EquipmentPackageItem", back_populates="package", cascade="all, delete-orphan")

class EquipmentPackageItem(Base):
    """套装明细表"""
    __tablename__ = "equipment_package_items"
    
    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(Integer, ForeignKey("equipment_packages.id"), nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)  # 数量
    is_required = Column(Boolean, default=True)  # 是否必需
    notes = Column(String(200))  # 备注说明
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    
    # 关系
    package = relationship("EquipmentPackage", back_populates="package_items")
    equipment = relationship("Equipment", back_populates="package_items")

class EquipmentInstance(Base):
    """设备实例表（带条码）"""
    __tablename__ = "equipment_instances"
    
    id = Column(String(32), primary_key=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    package_id = Column(Integer, ForeignKey("equipment_packages.id"))  # 所属套装
    barcode = Column(String(100), unique=True, index=True, nullable=False)  # 设备条码
    serial_number = Column(String(100), unique=True, nullable=False, index=True)  # 序列号（主设备必填）
    batch_number = Column(String(50))  # 批次号
    status = Column(Enum(InventoryStatusEnum), default=InventoryStatusEnum.IN_STOCK)
    
    # 新增设备属性字段
    mac_address = Column(String(17))  # MAC地址 (AA:BB:CC:DD:EE:FF)
    imei = Column(String(20))  # IMEI号
    firmware_version = Column(String(50))  # 固件版本
    hardware_version = Column(String(50))  # 硬件版本
    manufacture_date = Column(DateTime)  # 生产日期
    warranty_start_date = Column(DateTime)  # 保修开始日期
    warranty_end_date = Column(DateTime)  # 保修截止日期
    vendor = Column(String(100))  # 供应商
    quality_status = Column(String(20), default="good")  # 质量状态: good, defective, repair_needed
    
    # 位置信息
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    location = Column(String(100))  # 库位
    
    # 入库信息
    received_date = Column(DateTime)  # 入库日期
    received_by = Column(Integer, ForeignKey("users.id"))
    
    # 出库信息
    issued_date = Column(DateTime)  # 出库日期
    issued_to = Column(Integer, ForeignKey("users.id"))  # 领料人
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    equipment = relationship("Equipment")
    package = relationship("EquipmentPackage")
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])
    receiver = relationship("User", foreign_keys=[received_by])
    issuer = relationship("User", foreign_keys=[issued_to])

class Warehouse(Base):
    """仓库表"""
    __tablename__ = "warehouses"
    
    id = Column(Integer, primary_key=True, index=True)
    warehouse_code = Column(String(50), unique=True, index=True, nullable=False)
    warehouse_name = Column(String(100), nullable=False)
    address = Column(Text)
    contact_person = Column(String(50))
    contact_phone = Column(String(20))
    manager_id = Column(Integer, ForeignKey("users.id"))  # 仓库管理员
    status = Column(Enum(EquipmentStatusEnum), default=EquipmentStatusEnum.ACTIVE)
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    manager = relationship("User", foreign_keys=[manager_id])
    inventory_records = relationship("Inventory", back_populates="warehouse")

class Inventory(Base):
    """库存统计表"""
    __tablename__ = "inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    
    # 库存数量
    current_stock = Column(Integer, default=0)  # 当前库存
    available_stock = Column(Integer, default=0)  # 可用库存
    reserved_stock = Column(Integer, default=0)  # 预留库存
    allocated_stock = Column(Integer, default=0)  # 已分配库存
    
    # 库存控制
    min_stock = Column(Integer, default=0)  # 最低库存预警
    max_stock = Column(Integer, default=1000)  # 最大库存
    
    # 最后更新
    last_updated_by = Column(Integer, ForeignKey("users.id"))
    last_updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    
    # 关系
    warehouse = relationship("Warehouse", back_populates="inventory_records")
    equipment = relationship("Equipment", back_populates="inventory_records")
    updater = relationship("User", foreign_keys=[last_updated_by])

class StockTransaction(Base):
    """出入库记录表"""
    __tablename__ = "stock_transactions"
    
    id = Column(String(32), primary_key=True)
    transaction_type = Column(Enum(TransactionTypeEnum), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    
    # 关联信息
    package_id = Column(Integer, ForeignKey("equipment_packages.id"))  # 关联套装
    
    # 操作信息
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    operation_time = Column(DateTime, server_default=func.now())
    
    # 扫码信息
    scan_barcode = Column(String(100))  # 扫描的条码
    scan_time = Column(DateTime)  # 扫描时间
    scan_location = Column(JSON)  # 扫描位置（GPS）
    
    # 单据信息
    document_number = Column(String(50), unique=True, index=True)  # 单据编号
    total_quantity = Column(Integer, default=0)  # 总数量
    notes = Column(Text)  # 备注
    
    # 审批状态
    approval_status = Column(String(20), default="pending")  # pending, approved, rejected
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    approval_comments = Column(Text)
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    warehouse = relationship("Warehouse")
    package = relationship("EquipmentPackage")
    operator = relationship("User", foreign_keys=[operator_id])
    approver = relationship("User", foreign_keys=[approved_by])
    transaction_items = relationship("StockTransactionItem", back_populates="transaction", cascade="all, delete-orphan")

class StockTransactionItem(Base):
    """出入库明细表"""
    __tablename__ = "stock_transaction_items"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(32), ForeignKey("stock_transactions.id"), nullable=False)
    equipment_instance_id = Column(String(32), ForeignKey("equipment_instances.id"))  # 具体设备实例
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)  # 设备型号
    
    # 数量
    quantity = Column(Integer, nullable=False)
    
    # 批次信息
    batch_number = Column(String(50))
    expiry_date = Column(DateTime)  # 过期日期（如适用）
    
    # 位置信息
    from_location = Column(String(100))  # 源库位
    to_location = Column(String(100))    # 目标库位
    
    # 质检信息
    quality_status = Column(String(20), default="good")  # good, damaged, defective
    quality_notes = Column(Text)
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    
    # 关系
    transaction = relationship("StockTransaction", back_populates="transaction_items")
    equipment_instance = relationship("EquipmentInstance")
    equipment = relationship("Equipment")

class PickupRecord(Base):
    """领料记录表"""
    __tablename__ = "pickup_records"
    
    id = Column(String(32), primary_key=True)
    transaction_id = Column(String(32), ForeignKey("stock_transactions.id"), nullable=False)
    work_order_id = Column(String(32), ForeignKey("work_orders.id"), nullable=False)
    package_id = Column(Integer, ForeignKey("equipment_packages.id"), nullable=False)
    
    # 领料人信息
    picker_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pickup_time = Column(DateTime, server_default=func.now())
    
    # 扫码信息
    main_device_barcode = Column(String(100), nullable=False)  # 主设备条码
    serial_number = Column(String(100))  # 设备序列号
    mac_address_1 = Column(String(50))  # MAC地址1
    mac_address_2 = Column(String(50))  # MAC地址2
    equipment_instance_id = Column(String(32), ForeignKey("equipment_instances.id"))  # 关联设备实例
    scan_location = Column(JSON)  # GPS位置
    scan_ip = Column(String(45))  # 扫描IP
    
    # 确认信息
    is_confirmed = Column(Boolean, default=False)  # 是否确认领料
    confirmed_at = Column(DateTime)
    confirmation_notes = Column(Text)
    
    # 归还信息
    is_returned = Column(Boolean, default=False)
    returned_at = Column(DateTime)
    return_notes = Column(Text)
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    transaction = relationship("StockTransaction")
    package = relationship("EquipmentPackage")
    picker = relationship("User", foreign_keys=[picker_id])
    equipment_instance = relationship("EquipmentInstance", foreign_keys=[equipment_instance_id])

class SNImportRecord(Base):
    """SN导入记录表"""
    __tablename__ = "sn_import_records"
    
    id = Column(String(32), primary_key=True)
    file_name = Column(String(255), nullable=False)  # 导入文件名
    import_date = Column(DateTime, server_default=func.now())  # 导入日期
    equipment_type_id = Column(Integer, ForeignKey("equipment.id"))  # 设备类型
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))  # 目标仓库
    
    # 统计信息
    total_count = Column(Integer, default=0)  # 总数量
    success_count = Column(Integer, default=0)  # 成功数量
    failed_count = Column(Integer, default=0)  # 失败数量
    duplicate_count = Column(Integer, default=0)  # 重复数量
    
    # 导入详情
    import_details = Column(JSON)  # 详细导入结果（成功/失败明细）
    error_summary = Column(JSON)  # 错误汇总
    
    # 状态信息
    status = Column(String(20), default="processing")  # processing, completed, failed
    import_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text)  # 备注
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    equipment_type = relationship("Equipment", foreign_keys=[equipment_type_id])
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])
    importer = relationship("User", foreign_keys=[import_by])

class SNImportDetail(Base):
    """SN导入明细表"""
    __tablename__ = "sn_import_details"
    
    id = Column(Integer, primary_key=True, index=True)
    import_record_id = Column(String(32), ForeignKey("sn_import_records.id"), nullable=False)
    line_number = Column(Integer)  # Excel行号
    
    # 导入的数据
    serial_number = Column(String(100), index=True)
    mac_address = Column(String(17))
    imei = Column(String(20))
    firmware_version = Column(String(50))
    hardware_version = Column(String(50))
    manufacture_date = Column(DateTime)
    warranty_start_date = Column(DateTime)
    warranty_end_date = Column(DateTime)
    vendor = Column(String(100))
    batch_number = Column(String(50))
    
    # 导入结果
    import_status = Column(String(20))  # success, failed, duplicate
    error_message = Column(Text)  # 错误信息
    equipment_instance_id = Column(String(32), ForeignKey("equipment_instances.id"))  # 关联的设备实例
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    
    # 关系
    import_record = relationship("SNImportRecord")
    equipment_instance = relationship("EquipmentInstance")