from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, aliased

from app.models.equipment import (
    Equipment,
    EquipmentCategoryEnum,
    EquipmentInstance,
    EquipmentStatusEnum,
    Inventory,
    InventoryStatusEnum,
    StockTransaction,
    StockTransactionItem,
    TransactionTypeEnum,
    Warehouse,
)
from app.models.inspection import InspectionCheckItem, SiteInspection
from app.models.site import Site
from app.models.user import User
from app.utils.timezone import to_utc_iso


MAIN_STATUS_KEYS = (
    "in_stock",
    "issued",
    "pending_inspection",
    "inspected",
    "return_pending_receive",
    "abnormal",
)

ABNORMAL_STATUSES = {
    InventoryStatusEnum.DAMAGED.value,
    InventoryStatusEnum.REPAIRING.value,
    InventoryStatusEnum.SCRAPPED.value,
}


def _enum_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").strip().lower()


def _main_status_bucket(value: Any) -> str:
    status = _enum_value(value)
    if status in {InventoryStatusEnum.IN_STOCK.value, InventoryStatusEnum.RETURNED.value}:
        return "in_stock"
    if status in {
        InventoryStatusEnum.ISSUED.value,
        InventoryStatusEnum.PENDING_ISSUE.value,
        InventoryStatusEnum.ALLOCATED.value,
    }:
        return "issued"
    if status == InventoryStatusEnum.PENDING_INSPECTION.value:
        return "pending_inspection"
    if status == InventoryStatusEnum.INSPECTED.value:
        return "inspected"
    if status == InventoryStatusEnum.RETURN_PENDING_RECEIVE.value:
        return "return_pending_receive"
    if status in ABNORMAL_STATUSES or status:
        return "abnormal"
    return "abnormal"


def _empty_main_counts() -> Dict[str, int]:
    counts = {key: 0 for key in MAIN_STATUS_KEYS}
    counts["device_total"] = 0
    return counts


def _add_main_count(counts: Dict[str, int], bucket: str, quantity: int = 1) -> None:
    counts[bucket] = int(counts.get(bucket, 0) or 0) + quantity
    counts["device_total"] = int(counts.get("device_total", 0) or 0) + quantity


def _merge_main_counts(target: Dict[str, int], source: Dict[str, int]) -> None:
    for key in (*MAIN_STATUS_KEYS, "device_total"):
        target[key] = int(target.get(key, 0) or 0) + int(source.get(key, 0) or 0)


def _latest_stock_out_subquery(db: Session):
    return (
        db.query(
            StockTransactionItem.equipment_instance_id.label("equipment_instance_id"),
            StockTransaction.warehouse_id.label("warehouse_id"),
            StockTransaction.document_number.label("document_number"),
            StockTransaction.operation_time.label("operation_time"),
            func.row_number()
            .over(
                partition_by=StockTransactionItem.equipment_instance_id,
                order_by=(
                    StockTransaction.operation_time.desc(),
                    StockTransactionItem.id.desc(),
                ),
            )
            .label("row_no"),
        )
        .join(
            StockTransaction,
            StockTransaction.id == StockTransactionItem.transaction_id,
        )
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            StockTransactionItem.equipment_instance_id.isnot(None),
        )
        .subquery()
    )


def _load_main_instance_rows(db: Session) -> List[dict]:
    latest_out = _latest_stock_out_subquery(db)
    current_warehouse = aliased(Warehouse)
    source_warehouse = aliased(Warehouse)
    issuer = aliased(User)

    rows = (
        db.query(
            EquipmentInstance,
            Equipment,
            current_warehouse,
            source_warehouse,
            issuer,
            latest_out.c.document_number,
            latest_out.c.operation_time,
        )
        .join(Equipment, Equipment.id == EquipmentInstance.equipment_id)
        .outerjoin(current_warehouse, current_warehouse.id == EquipmentInstance.warehouse_id)
        .outerjoin(
            latest_out,
            and_(
                latest_out.c.equipment_instance_id == EquipmentInstance.id,
                latest_out.c.row_no == 1,
            ),
        )
        .outerjoin(source_warehouse, source_warehouse.id == latest_out.c.warehouse_id)
        .outerjoin(issuer, issuer.id == EquipmentInstance.issued_to)
        .filter(
            Equipment.category == EquipmentCategoryEnum.MAIN_DEVICE,
            or_(
                EquipmentInstance.is_voided.is_(False),
                EquipmentInstance.is_voided.is_(None),
            ),
        )
        .all()
    )

    result = []
    for instance, equipment, current_wh, source_wh, issued_to, out_no, out_time in rows:
        warehouse = current_wh or source_wh
        result.append(
            {
                "instance": instance,
                "equipment_id": equipment.id,
                "equipment_code": equipment.equipment_code,
                "equipment_name": equipment.equipment_name,
                "unit": equipment.unit or "台",
                "warehouse_id": warehouse.id if warehouse else None,
                "warehouse_code": warehouse.warehouse_code if warehouse else None,
                "warehouse_name": warehouse.warehouse_name if warehouse else None,
                "status": _enum_value(instance.status),
                "status_bucket": _main_status_bucket(instance.status),
                "issued_to_name": (
                    (issued_to.full_name or issued_to.username) if issued_to else None
                ),
                "latest_stock_out_document": out_no,
                "latest_stock_out_time": out_time,
            }
        )
    return result


def _active_inventory_rows(db: Session, category: EquipmentCategoryEnum):
    return (
        db.query(Inventory, Equipment, Warehouse)
        .join(Equipment, Equipment.id == Inventory.equipment_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .filter(
            Equipment.category == category,
            Warehouse.status == EquipmentStatusEnum.ACTIVE,
        )
        .all()
    )


def _matches_keyword(row: dict, keyword: str) -> bool:
    if not keyword:
        return True
    normalized = keyword.casefold()
    values = (
        row.get("equipment_code"),
        row.get("equipment_name"),
        row.get("warehouse_code"),
        row.get("warehouse_name"),
        getattr(row.get("instance"), "serial_number", None),
    )
    return any(normalized in str(value or "").casefold() for value in values)


def _main_zero_inventory_rows(db: Session) -> List[dict]:
    result = []
    for inventory, equipment, warehouse in _active_inventory_rows(
        db, EquipmentCategoryEnum.MAIN_DEVICE
    ):
        if int(inventory.current_stock or 0) > 0 or int(inventory.allocated_stock or 0) > 0:
            continue
        result.append(
            {
                "equipment_id": equipment.id,
                "equipment_code": equipment.equipment_code,
                "equipment_name": equipment.equipment_name,
                "unit": equipment.unit or "台",
                "warehouse_id": warehouse.id,
                "warehouse_code": warehouse.warehouse_code,
                "warehouse_name": warehouse.warehouse_name,
            }
        )
    return result


def _main_child(
    *,
    key: str,
    equipment_id: int,
    equipment_code: str,
    equipment_name: str,
    unit: str,
    warehouse_id: Optional[int],
    warehouse_code: Optional[str],
    warehouse_name: Optional[str],
) -> dict:
    return {
        "key": key,
        "row_type": "child",
        "equipment_id": equipment_id,
        "equipment_code": equipment_code,
        "equipment_name": equipment_name,
        "unit": unit,
        "warehouse_id": warehouse_id,
        "warehouse_code": warehouse_code,
        "warehouse_name": warehouse_name,
        **_empty_main_counts(),
    }


def get_main_inventory_overview(
    db: Session,
    *,
    view_mode: str,
    keyword: str = "",
    warehouse_id: Optional[int] = None,
    status_filter: str = "",
    include_zero: bool = False,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    all_rows = _load_main_instance_rows(db)
    summary = _empty_main_counts()
    for row in all_rows:
        _add_main_count(summary, row["status_bucket"])

    filtered = []
    for row in all_rows:
        if warehouse_id is not None and row["warehouse_id"] != warehouse_id:
            continue
        if status_filter and row["status_bucket"] != status_filter:
            continue
        if not _matches_keyword(row, keyword):
            continue
        filtered.append(row)

    zero_rows = _main_zero_inventory_rows(db)
    hidden_zero_record_count = len(zero_rows)
    included_zero_rows = []
    if include_zero and not status_filter:
        for row in zero_rows:
            if warehouse_id is not None and row["warehouse_id"] != warehouse_id:
                continue
            if not _matches_keyword(row, keyword):
                continue
            included_zero_rows.append(row)

    if view_mode == "warehouse":
        grouped: Dict[str, dict] = {}

        def ensure_group(row: dict) -> dict:
            warehouse_key = str(row.get("warehouse_id") or "unassigned")
            group = grouped.get(warehouse_key)
            if group is None:
                group = {
                    "key": f"warehouse-{warehouse_key}",
                    "row_type": "group",
                    "warehouse_id": row.get("warehouse_id"),
                    "warehouse_code": row.get("warehouse_code"),
                    "warehouse_name": row.get("warehouse_name"),
                    "equipment_count": 0,
                    "children": [],
                    **_empty_main_counts(),
                }
                grouped[warehouse_key] = group
            return group

        child_maps: Dict[str, Dict[int, dict]] = defaultdict(dict)
        for row in filtered:
            group = ensure_group(row)
            child = child_maps[group["key"]].get(row["equipment_id"])
            if child is None:
                child = _main_child(
                    key=f"warehouse-{row.get('warehouse_id') or 'unassigned'}-equipment-{row['equipment_id']}",
                    equipment_id=row["equipment_id"],
                    equipment_code=row["equipment_code"],
                    equipment_name=row["equipment_name"],
                    unit=row["unit"],
                    warehouse_id=row["warehouse_id"],
                    warehouse_code=row["warehouse_code"],
                    warehouse_name=row["warehouse_name"],
                )
                child_maps[group["key"]][row["equipment_id"]] = child
                group["children"].append(child)
            _add_main_count(child, row["status_bucket"])
            _add_main_count(group, row["status_bucket"])

        for row in included_zero_rows:
            group = ensure_group(row)
            if row["equipment_id"] not in child_maps[group["key"]]:
                child = _main_child(
                    key=f"warehouse-{row['warehouse_id']}-equipment-{row['equipment_id']}",
                    equipment_id=row["equipment_id"],
                    equipment_code=row["equipment_code"],
                    equipment_name=row["equipment_name"],
                    unit=row["unit"],
                    warehouse_id=row["warehouse_id"],
                    warehouse_code=row["warehouse_code"],
                    warehouse_name=row["warehouse_name"],
                )
                child_maps[group["key"]][row["equipment_id"]] = child
                group["children"].append(child)

        items = list(grouped.values())
        for group in items:
            group["children"].sort(
                key=lambda child: (-child["device_total"], child["equipment_code"])
            )
            group["equipment_count"] = len(group["children"])
        items.sort(
            key=lambda group: (-group["device_total"], group["warehouse_name"] or "")
        )
    else:
        grouped = {}

        def ensure_group(row: dict) -> dict:
            equipment_key = str(row["equipment_id"])
            group = grouped.get(equipment_key)
            if group is None:
                group = {
                    "key": f"equipment-{equipment_key}",
                    "row_type": "group",
                    "equipment_id": row["equipment_id"],
                    "equipment_code": row["equipment_code"],
                    "equipment_name": row["equipment_name"],
                    "unit": row["unit"],
                    "warehouse_count": 0,
                    "unassigned_count": 0,
                    "children": [],
                    **_empty_main_counts(),
                }
                grouped[equipment_key] = group
            return group

        child_maps: Dict[str, Dict[str, dict]] = defaultdict(dict)
        for row in filtered:
            group = ensure_group(row)
            warehouse_key = str(row.get("warehouse_id") or "unassigned")
            child = child_maps[group["key"]].get(warehouse_key)
            if child is None:
                child = _main_child(
                    key=f"equipment-{row['equipment_id']}-warehouse-{warehouse_key}",
                    equipment_id=row["equipment_id"],
                    equipment_code=row["equipment_code"],
                    equipment_name=row["equipment_name"],
                    unit=row["unit"],
                    warehouse_id=row["warehouse_id"],
                    warehouse_code=row["warehouse_code"],
                    warehouse_name=row["warehouse_name"],
                )
                child_maps[group["key"]][warehouse_key] = child
                group["children"].append(child)
            _add_main_count(child, row["status_bucket"])
            _add_main_count(group, row["status_bucket"])

        for row in included_zero_rows:
            group = ensure_group(row)
            warehouse_key = str(row["warehouse_id"])
            if warehouse_key not in child_maps[group["key"]]:
                child = _main_child(
                    key=f"equipment-{row['equipment_id']}-warehouse-{warehouse_key}",
                    equipment_id=row["equipment_id"],
                    equipment_code=row["equipment_code"],
                    equipment_name=row["equipment_name"],
                    unit=row["unit"],
                    warehouse_id=row["warehouse_id"],
                    warehouse_code=row["warehouse_code"],
                    warehouse_name=row["warehouse_name"],
                )
                child_maps[group["key"]][warehouse_key] = child
                group["children"].append(child)

        items = list(grouped.values())
        for group in items:
            group["children"].sort(
                key=lambda child: (
                    -child["device_total"],
                    child["warehouse_name"] or "",
                )
            )
            group["warehouse_count"] = sum(
                1 for child in group["children"] if child.get("warehouse_id") is not None
            )
            group["unassigned_count"] = sum(
                1 for child in group["children"] if child.get("warehouse_id") is None
            )
        items.sort(key=lambda group: (-group["device_total"], group["equipment_code"]))

    equipment_ids = {
        child["equipment_id"]
        for item in items
        for child in item.get("children", [])
    }
    warehouse_ids = {
        child["warehouse_id"]
        for item in items
        for child in item.get("children", [])
        if child.get("warehouse_id") is not None
    }
    record_count = sum(len(item.get("children", [])) for item in items)

    total = len(items)
    start = max(page - 1, 0) * page_size
    paged_items = items[start : start + page_size]
    return {
        "category": EquipmentCategoryEnum.MAIN_DEVICE.value,
        "view_mode": view_mode,
        "summary": summary,
        "meta": {
            "equipment_count": len(equipment_ids),
            "warehouse_count": len(warehouse_ids),
            "record_count": record_count,
            "hidden_zero_record_count": hidden_zero_record_count if not include_zero else 0,
        },
        "items": paged_items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _latest_binding_map(db: Session, serial_numbers: Iterable[str]) -> Dict[str, dict]:
    serials = [str(sn).strip() for sn in serial_numbers if str(sn or "").strip()]
    if not serials:
        return {}

    result: Dict[str, dict] = {}
    for offset in range(0, len(serials), 500):
        chunk = serials[offset : offset + 500]
        timestamp_expr = func.coalesce(
            InspectionCheckItem.updated_at,
            InspectionCheckItem.checked_at,
            InspectionCheckItem.created_at,
        )
        rows = (
            db.query(
                InspectionCheckItem.equipment_sn,
                InspectionCheckItem.sector_id,
                InspectionCheckItem.band,
                InspectionCheckItem.cell_id,
                Site.id.label("site_id"),
                Site.site_code,
                Site.site_name,
                timestamp_expr.label("binding_at"),
            )
            .join(SiteInspection, SiteInspection.id == InspectionCheckItem.inspection_id)
            .join(Site, Site.id == SiteInspection.site_id)
            .filter(
                InspectionCheckItem.equipment_sn.in_(chunk),
                InspectionCheckItem.is_active.is_(True),
            )
            .order_by(timestamp_expr.desc(), InspectionCheckItem.id.desc())
            .all()
        )
        for row in rows:
            sn = str(row.equipment_sn or "").strip()
            if sn and sn not in result:
                result[sn] = {
                    "site_id": row.site_id,
                    "site_code": row.site_code,
                    "site_name": row.site_name,
                    "sector_id": row.sector_id,
                    "band": row.band,
                    "cell_id": row.cell_id,
                    "binding_at": to_utc_iso(row.binding_at) if row.binding_at else None,
                }
    return result


def get_main_inventory_instances(
    db: Session,
    *,
    equipment_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    status_filter: str = "",
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    rows = _load_main_instance_rows(db)
    base_rows = []
    for row in rows:
        if equipment_id is not None and row["equipment_id"] != equipment_id:
            continue
        if warehouse_id is not None and row["warehouse_id"] != warehouse_id:
            continue
        base_rows.append(row)

    binding_map = _latest_binding_map(
        db, [row["instance"].serial_number for row in base_rows]
    )
    normalized_keyword = keyword.casefold().strip()
    if normalized_keyword:
        keyword_rows = []
        for row in base_rows:
            instance = row["instance"]
            binding = binding_map.get(instance.serial_number, {})
            values = (
                instance.serial_number,
                row["equipment_code"],
                row["equipment_name"],
                row["warehouse_name"],
                row["issued_to_name"],
                binding.get("site_code"),
                binding.get("site_name"),
            )
            if any(
                normalized_keyword in str(value or "").casefold() for value in values
            ):
                keyword_rows.append(row)
        base_rows = keyword_rows

    summary = _empty_main_counts()
    for row in base_rows:
        _add_main_count(summary, row["status_bucket"])

    if status_filter:
        base_rows = [
            row for row in base_rows if row["status_bucket"] == status_filter
        ]

    def status_time(row: dict) -> datetime:
        instance = row["instance"]
        return (
            instance.updated_at
            or instance.issued_date
            or instance.received_date
            or instance.created_at
            or datetime.min
        )

    base_rows.sort(
        key=lambda row: (status_time(row), row["instance"].serial_number),
        reverse=True,
    )
    total = len(base_rows)
    start = max(page - 1, 0) * page_size
    paged = base_rows[start : start + page_size]
    items = []
    for row in paged:
        instance = row["instance"]
        binding = binding_map.get(instance.serial_number, {})
        items.append(
            {
                "id": instance.id,
                "serial_number": instance.serial_number,
                "equipment_id": row["equipment_id"],
                "equipment_code": row["equipment_code"],
                "equipment_name": row["equipment_name"],
                "warehouse_id": row["warehouse_id"],
                "warehouse_name": row["warehouse_name"],
                "status": row["status"],
                "status_bucket": row["status_bucket"],
                "issued_to_name": row["issued_to_name"],
                "site_id": binding.get("site_id"),
                "site_code": binding.get("site_code"),
                "site_name": binding.get("site_name"),
                "sector_id": binding.get("sector_id"),
                "band": binding.get("band"),
                "cell_id": binding.get("cell_id"),
                "status_time": (
                    to_utc_iso(status_time(row))
                    if status_time(row) != datetime.min
                    else None
                ),
                "latest_stock_out_document": row["latest_stock_out_document"],
            }
        )
    return {
        "summary": summary,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _auxiliary_outstanding_map(db: Session) -> Dict[tuple, int]:
    out_rows = (
        db.query(
            StockTransaction.id.label("out_id"),
            StockTransaction.warehouse_id.label("warehouse_id"),
            StockTransactionItem.equipment_id.label("equipment_id"),
            func.sum(StockTransactionItem.quantity).label("quantity"),
        )
        .join(
            StockTransactionItem,
            StockTransactionItem.transaction_id == StockTransaction.id,
        )
        .join(Equipment, Equipment.id == StockTransactionItem.equipment_id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT,
            Equipment.category == EquipmentCategoryEnum.AUXILIARY,
            StockTransactionItem.equipment_instance_id.is_(None),
        )
        .group_by(
            StockTransaction.id,
            StockTransaction.warehouse_id,
            StockTransactionItem.equipment_id,
        )
        .all()
    )
    if not out_rows:
        return {}

    out_ids = [str(row.out_id) for row in out_rows]
    returned_by_out: Dict[tuple, int] = defaultdict(int)
    return_rows = (
        db.query(
            StockTransaction.related_transaction_id.label("out_id"),
            StockTransaction.approval_status.label("return_status"),
            StockTransactionItem.equipment_id.label("equipment_id"),
            StockTransactionItem.quantity.label("quantity"),
            StockTransactionItem.received_qty.label("received_qty"),
        )
        .join(
            StockTransactionItem,
            StockTransactionItem.transaction_id == StockTransaction.id,
        )
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
            StockTransaction.related_transaction_id.in_(out_ids),
            StockTransaction.approval_status.in_(
                ["pending_receive", "partially_received", "received"]
            ),
            StockTransactionItem.equipment_instance_id.is_(None),
        )
        .all()
    )
    for row in return_rows:
        quantity = int(row.quantity or 0)
        received = (
            quantity
            if str(row.return_status or "") == "received"
            else min(int(row.received_qty or 0), quantity)
        )
        returned_by_out[(str(row.out_id), int(row.equipment_id))] += received

    result: Dict[tuple, int] = defaultdict(int)
    for row in out_rows:
        equipment_id = int(row.equipment_id)
        out_quantity = int(row.quantity or 0)
        returned = min(
            returned_by_out.get((str(row.out_id), equipment_id), 0),
            out_quantity,
        )
        result[(int(row.warehouse_id), equipment_id)] += max(
            out_quantity - returned,
            0,
        )
    return dict(result)


def _auxiliary_rows(db: Session) -> List[dict]:
    outstanding_map = _auxiliary_outstanding_map(db)
    result = []
    known_keys = set()
    for inventory, equipment, warehouse in _active_inventory_rows(
        db, EquipmentCategoryEnum.AUXILIARY
    ):
        key = (int(warehouse.id), int(equipment.id))
        known_keys.add(key)
        current_stock = int(inventory.current_stock or 0)
        allocated_stock = int(outstanding_map.get(key, 0) or 0)
        min_stock = int(inventory.min_stock or 0)
        result.append(
            {
                "inventory_id": inventory.id,
                "equipment_id": equipment.id,
                "equipment_code": equipment.equipment_code,
                "equipment_name": equipment.equipment_name,
                "unit": equipment.unit or "",
                "warehouse_id": warehouse.id,
                "warehouse_code": warehouse.warehouse_code,
                "warehouse_name": warehouse.warehouse_name,
                "current_stock": current_stock,
                "allocated_stock": allocated_stock,
                "min_stock": min_stock,
                "is_zero_stock": current_stock <= 0,
                "needs_restock": min_stock > 0 and current_stock <= min_stock,
                "reorder_configured": min_stock > 0,
                "last_updated_at": (
                    to_utc_iso(inventory.last_updated_at)
                    if inventory.last_updated_at
                    else None
                ),
            }
        )

    missing_keys = set(outstanding_map) - known_keys
    if missing_keys:
        equipment_map = {
            equipment.id: equipment
            for equipment in db.query(Equipment)
            .filter(
                Equipment.id.in_({key[1] for key in missing_keys}),
                Equipment.category == EquipmentCategoryEnum.AUXILIARY,
            )
            .all()
        }
        warehouse_map = {
            warehouse.id: warehouse
            for warehouse in db.query(Warehouse)
            .filter(
                Warehouse.id.in_({key[0] for key in missing_keys}),
                Warehouse.status == EquipmentStatusEnum.ACTIVE,
            )
            .all()
        }
        for warehouse_id, equipment_id in missing_keys:
            equipment = equipment_map.get(equipment_id)
            warehouse = warehouse_map.get(warehouse_id)
            if not equipment or not warehouse:
                continue
            result.append(
                {
                    "inventory_id": None,
                    "equipment_id": equipment.id,
                    "equipment_code": equipment.equipment_code,
                    "equipment_name": equipment.equipment_name,
                    "unit": equipment.unit or "",
                    "warehouse_id": warehouse.id,
                    "warehouse_code": warehouse.warehouse_code,
                    "warehouse_name": warehouse.warehouse_name,
                    "current_stock": 0,
                    "allocated_stock": int(
                        outstanding_map.get((warehouse_id, equipment_id), 0) or 0
                    ),
                    "min_stock": 0,
                    "is_zero_stock": True,
                    "needs_restock": False,
                    "reorder_configured": False,
                    "last_updated_at": None,
                }
            )
    return result


def _aux_status(row: dict) -> str:
    if row["needs_restock"]:
        return "needs_restock"
    if row["is_zero_stock"]:
        return "zero_stock"
    return "stocked"


def get_auxiliary_inventory_overview(
    db: Session,
    *,
    view_mode: str,
    keyword: str = "",
    warehouse_id: Optional[int] = None,
    status_filter: str = "",
    include_zero: bool = False,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    all_rows = _auxiliary_rows(db)
    equipment_ids = {row["equipment_id"] for row in all_rows}
    warehouse_ids = {row["warehouse_id"] for row in all_rows}
    configured_by_equipment: Dict[int, bool] = defaultdict(bool)
    for row in all_rows:
        configured_by_equipment[row["equipment_id"]] = (
            configured_by_equipment[row["equipment_id"]]
            or row["reorder_configured"]
        )
    summary = {
        "equipment_type_count": len(equipment_ids),
        "warehouse_count": len(warehouse_ids),
        "inventory_record_count": len(all_rows),
        "stocked_record_count": sum(1 for row in all_rows if row["current_stock"] > 0),
        "zero_stock_record_count": sum(1 for row in all_rows if row["is_zero_stock"]),
        "needs_restock_count": sum(1 for row in all_rows if row["needs_restock"]),
        "unconfigured_reorder_type_count": sum(
            1 for equipment_id in equipment_ids if not configured_by_equipment[equipment_id]
        ),
    }

    normalized_keyword = keyword.casefold().strip()
    filtered = []
    for row in all_rows:
        if warehouse_id is not None and row["warehouse_id"] != warehouse_id:
            continue
        if normalized_keyword and not any(
            normalized_keyword in str(value or "").casefold()
            for value in (
                row["equipment_code"],
                row["equipment_name"],
                row["warehouse_code"],
                row["warehouse_name"],
            )
        ):
            continue
        row_status = _aux_status(row)
        if status_filter == "unconfigured" and configured_by_equipment[
            row["equipment_id"]
        ]:
            continue
        if status_filter and status_filter != "unconfigured" and row_status != status_filter:
            continue
        filtered.append(row)

    def visible_child(row: dict) -> bool:
        return (
            include_zero
            or status_filter in {"zero_stock", "needs_restock", "unconfigured"}
            or row["current_stock"] > 0
            or row["allocated_stock"] > 0
        )

    if view_mode == "warehouse":
        grouped: Dict[int, dict] = {}
        for row in filtered:
            if not visible_child(row):
                continue
            group = grouped.get(row["warehouse_id"])
            if group is None:
                group = {
                    "key": f"warehouse-{row['warehouse_id']}",
                    "row_type": "group",
                    "warehouse_id": row["warehouse_id"],
                    "warehouse_code": row["warehouse_code"],
                    "warehouse_name": row["warehouse_name"],
                    "equipment_count": 0,
                    "stocked_equipment_count": 0,
                    "zero_stock_equipment_count": 0,
                    "children": [],
                }
                grouped[row["warehouse_id"]] = group
            group["equipment_count"] += 1
            if row["current_stock"] > 0:
                group["stocked_equipment_count"] += 1
            else:
                group["zero_stock_equipment_count"] += 1
            group["children"].append(
                {
                    "key": f"warehouse-{row['warehouse_id']}-equipment-{row['equipment_id']}",
                    "row_type": "child",
                    **row,
                    "stock_status": _aux_status(row),
                }
            )
        items = [group for group in grouped.values() if group["children"]]
        for group in items:
            group["children"].sort(
                key=lambda child: (-child["current_stock"], child["equipment_code"])
            )
        items.sort(key=lambda group: group["warehouse_name"])
    else:
        grouped = {}
        for row in filtered:
            if not visible_child(row):
                continue
            group = grouped.get(row["equipment_id"])
            if group is None:
                group = {
                    "key": f"equipment-{row['equipment_id']}",
                    "row_type": "group",
                    "equipment_id": row["equipment_id"],
                    "equipment_code": row["equipment_code"],
                    "equipment_name": row["equipment_name"],
                    "unit": row["unit"],
                    "warehouse_count": 0,
                    "zero_stock_warehouse_count": 0,
                    "current_stock": 0,
                    "allocated_stock": 0,
                    "needs_restock_count": 0,
                    "children": [],
                }
                grouped[row["equipment_id"]] = group
            group["warehouse_count"] += 1
            group["current_stock"] += row["current_stock"]
            group["allocated_stock"] += row["allocated_stock"]
            group["needs_restock_count"] += int(row["needs_restock"])
            if row["is_zero_stock"]:
                group["zero_stock_warehouse_count"] += 1
            group["children"].append(
                {
                    "key": f"equipment-{row['equipment_id']}-warehouse-{row['warehouse_id']}",
                    "row_type": "child",
                    **row,
                    "stock_status": _aux_status(row),
                }
            )
        items = [
            group
            for group in grouped.values()
            if group["children"]
            or include_zero
            or group["current_stock"] > 0
            or group["allocated_stock"] > 0
        ]
        for group in items:
            if group["needs_restock_count"]:
                group["stock_status"] = "needs_restock"
            elif group["zero_stock_warehouse_count"]:
                group["stock_status"] = "partial_zero"
            else:
                group["stock_status"] = "stocked"
            group["children"].sort(
                key=lambda child: (-child["current_stock"], child["warehouse_name"])
            )
        items.sort(key=lambda group: (-group["current_stock"], group["equipment_code"]))

    displayed_equipment_ids = {
        child["equipment_id"]
        for item in items
        for child in item.get("children", [])
    }
    displayed_warehouse_ids = {
        child["warehouse_id"]
        for item in items
        for child in item.get("children", [])
    }
    record_count = sum(len(item.get("children", [])) for item in items)
    total = len(items)
    start = max(page - 1, 0) * page_size
    return {
        "category": EquipmentCategoryEnum.AUXILIARY.value,
        "view_mode": view_mode,
        "summary": summary,
        "meta": {
            "equipment_count": len(displayed_equipment_ids),
            "warehouse_count": len(displayed_warehouse_ids),
            "record_count": record_count,
        },
        "items": items[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_auxiliary_inventory_details(
    db: Session,
    *,
    equipment_id: int,
    mode: str,
    keyword: str = "",
    warehouse_id: Optional[int] = None,
    include_zero: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    equipment = (
        db.query(Equipment)
        .filter(
            Equipment.id == equipment_id,
            Equipment.category == EquipmentCategoryEnum.AUXILIARY,
        )
        .first()
    )
    if not equipment:
        raise ValueError("auxiliary_not_found")

    inventory_rows = [
        row for row in _auxiliary_rows(db) if row["equipment_id"] == equipment_id
    ]
    summary = {
        "equipment_id": equipment.id,
        "equipment_code": equipment.equipment_code,
        "equipment_name": equipment.equipment_name,
        "unit": equipment.unit or "",
        "current_stock": sum(row["current_stock"] for row in inventory_rows),
        "allocated_stock": sum(row["allocated_stock"] for row in inventory_rows),
        "warehouse_count": len(inventory_rows),
    }

    normalized_keyword = keyword.casefold().strip()
    if mode == "distribution":
        items = []
        for row in inventory_rows:
            if warehouse_id is not None and row["warehouse_id"] != warehouse_id:
                continue
            if (
                normalized_keyword
                and normalized_keyword not in row["warehouse_name"].casefold()
            ):
                continue
            if (
                not include_zero
                and row["current_stock"] <= 0
                and row["allocated_stock"] <= 0
            ):
                continue
            items.append({**row, "stock_status": _aux_status(row)})
        items.sort(key=lambda row: (-row["current_stock"], row["warehouse_name"]))
    else:
        warehouse = aliased(Warehouse)
        issued_to = aliased(User)
        query = (
            db.query(StockTransactionItem, StockTransaction, warehouse, issued_to)
            .join(
                StockTransaction,
                StockTransaction.id == StockTransactionItem.transaction_id,
            )
            .outerjoin(warehouse, warehouse.id == StockTransaction.warehouse_id)
            .outerjoin(issued_to, issued_to.id == StockTransaction.issued_to)
            .filter(StockTransactionItem.equipment_id == equipment_id)
        )
        if mode == "outbound":
            query = query.filter(
                StockTransaction.transaction_type == TransactionTypeEnum.STOCK_OUT
            )
        if warehouse_id is not None:
            query = query.filter(StockTransaction.warehouse_id == warehouse_id)
        rows = query.order_by(StockTransaction.operation_time.desc()).all()
        stock_out_ids = list({
            str(transaction.id)
            for _item, transaction, _warehouse, _owner in rows
            if _enum_value(transaction.transaction_type)
            == TransactionTypeEnum.STOCK_OUT.value
        })
        returned_by_out: Dict[str, int] = defaultdict(int)
        if stock_out_ids:
            return_rows = (
                db.query(
                    StockTransaction.related_transaction_id,
                    StockTransaction.approval_status,
                    StockTransactionItem.quantity,
                    StockTransactionItem.received_qty,
                )
                .join(
                    StockTransactionItem,
                    StockTransactionItem.transaction_id == StockTransaction.id,
                )
                .filter(
                    StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                    StockTransaction.related_transaction_id.in_(stock_out_ids),
                    StockTransaction.approval_status.in_(
                        ["pending_receive", "partially_received", "received"]
                    ),
                    StockTransactionItem.equipment_id == equipment_id,
                    StockTransactionItem.equipment_instance_id.is_(None),
                )
                .all()
            )
            for out_id, return_status, quantity, received_qty in return_rows:
                return_quantity = int(quantity or 0)
                effective_received = (
                    return_quantity
                    if _enum_value(return_status) == "received"
                    else min(int(received_qty or 0), return_quantity)
                )
                returned_by_out[str(out_id)] += effective_received

        items = []
        detail_rows = []
        if mode == "outbound":
            grouped_rows: Dict[str, dict] = {}
            for item, transaction, source_warehouse, owner in rows:
                transaction_key = str(transaction.id)
                grouped_row = grouped_rows.get(transaction_key)
                if grouped_row is None:
                    grouped_row = {
                        "item": item,
                        "transaction": transaction,
                        "warehouse": source_warehouse,
                        "owner": owner,
                        "quantity": 0,
                    }
                    grouped_rows[transaction_key] = grouped_row
                grouped_row["quantity"] += int(item.quantity or 0)
            detail_rows = [
                (
                    row["item"],
                    row["transaction"],
                    row["warehouse"],
                    row["owner"],
                    row["quantity"],
                )
                for row in grouped_rows.values()
            ]
        else:
            detail_rows = [
                (item, transaction, source_warehouse, owner, int(item.quantity or 0))
                for item, transaction, source_warehouse, owner in rows
            ]

        for item, transaction, source_warehouse, owner, quantity in detail_rows:
            is_stock_out = (
                _enum_value(transaction.transaction_type)
                == TransactionTypeEnum.STOCK_OUT.value
            )
            returned_quantity = (
                min(returned_by_out.get(str(transaction.id), 0), quantity)
                if is_stock_out
                else 0
            )
            pending_quantity = (
                max(quantity - returned_quantity, 0) if is_stock_out else 0
            )
            owner_name = (owner.full_name or owner.username) if owner else None
            search_values = (
                transaction.document_number,
                transaction.material_request_no,
                transaction.issue_draft_no,
                source_warehouse.warehouse_name if source_warehouse else None,
                owner_name,
            )
            if normalized_keyword and not any(
                normalized_keyword in str(value or "").casefold()
                for value in search_values
            ):
                continue
            if mode == "outbound" and pending_quantity <= 0:
                continue
            items.append(
                {
                    "transaction_item_id": item.id,
                    "transaction_id": transaction.id,
                    "transaction_type": _enum_value(transaction.transaction_type),
                    "document_number": transaction.document_number,
                    "material_request_id": transaction.material_request_id,
                    "material_request_no": transaction.material_request_no,
                    "issue_draft_id": transaction.issue_draft_id,
                    "issue_draft_no": transaction.issue_draft_no,
                    "warehouse_id": source_warehouse.id if source_warehouse else None,
                    "warehouse_name": (
                        source_warehouse.warehouse_name
                        if source_warehouse
                        else None
                    ),
                    "issued_to_name": owner_name,
                    "quantity": quantity,
                    "returned_quantity": returned_quantity,
                    "pending_quantity": pending_quantity,
                    "operation_time": (
                        to_utc_iso(transaction.operation_time)
                        if transaction.operation_time
                        else None
                    ),
                    "approval_status": _enum_value(transaction.approval_status),
                }
            )

    total = len(items)
    start = max(page - 1, 0) * page_size
    return {
        "mode": mode,
        "summary": summary,
        "items": items[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
