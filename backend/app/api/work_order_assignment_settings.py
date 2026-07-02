from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.authz_service import user_has_any_role_or_permission
from app.services.subcontractor_assignment_service import (
    load_work_order_assignment_settings,
    save_work_order_assignment_settings,
)

router = APIRouter()


class WorkOrderAssignmentSettingsPayload(BaseModel):
    config_version: int = Field(1, ge=1)
    subcontractor_category_id: Optional[int] = None
    auto_sync_site_subcontractor_on_assignment: bool = False


def _ensure_manage_access(user: User) -> None:
    if user_has_any_role_or_permission(
        user,
        role_codes=["admin"],
        permission_codes=["authz:manage:all"],
    ):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有权限管理员可以管理工单指派联动配置")


@router.get("/workorder-assignment-settings", response_model=WorkOrderAssignmentSettingsPayload)
def get_work_order_assignment_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_manage_access(current_user)
    return load_work_order_assignment_settings(db)


@router.put("/workorder-assignment-settings", response_model=WorkOrderAssignmentSettingsPayload)
def update_work_order_assignment_settings(
    payload: WorkOrderAssignmentSettingsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_manage_access(current_user)
    try:
        return save_work_order_assignment_settings(db, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
