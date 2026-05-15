from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.models.equipment import EquipmentStatusEnum, Warehouse
from app.models.user import User
from app.services.authz_service import user_has_any_role_or_permission


def has_global_inventory_scope(user: Optional[User]) -> bool:
    return user_has_any_role_or_permission(
        user,
        role_codes=["admin", "manager"],
        permission_codes=["inventory:warehouse:all"],
    )


def get_managed_warehouse_ids(db: Session, user: Optional[User]) -> Optional[Set[int]]:
    """返回当前用户可管理的仓库集合；全局范围返回 None。"""
    if not user:
        return set()
    if has_global_inventory_scope(user):
        return None
    rows = (
        db.query(Warehouse.id)
        .filter(
            Warehouse.manager_id == user.id,
            Warehouse.status == EquipmentStatusEnum.ACTIVE,
        )
        .all()
    )
    return {int(row[0]) for row in rows if row and row[0] is not None}


def build_inventory_access_profile(db: Session, user: Optional[User]) -> Dict[str, object]:
    managed_ids = get_managed_warehouse_ids(db, user)
    if managed_ids is None:
        return {
            "inventory_scope": "all",
            "managed_warehouse_ids": [],
            "managed_warehouse_count": 0,
            "has_managed_warehouses": False,
        }
    managed_list = sorted(int(x) for x in managed_ids)
    return {
        "inventory_scope": "managed" if managed_list else "self",
        "managed_warehouse_ids": managed_list,
        "managed_warehouse_count": len(managed_list),
        "has_managed_warehouses": len(managed_list) > 0,
    }
