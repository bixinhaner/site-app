from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.work_order_execution_settings import (
    EffectiveWorkOrderExecutionSettingsResponse,
    WorkOrderExecutionSettingsPayload,
    WorkOrderExecutionSettingsUpdatePayload,
)
from app.services.authz_service import user_has_permission
from app.services.work_order_execution_settings_service import (
    build_work_order_execution_settings_from_payload,
    get_effective_work_order_execution_settings,
    get_work_order_execution_settings_version,
    load_work_order_execution_settings,
    save_work_order_execution_settings,
)


router = APIRouter()


def _ensure_read_access(current_user: User) -> None:
    if user_has_permission(current_user, 'authz:manage:all'):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='只有权限管理员可以查看 Web 工单执行配置')


def _ensure_write_access(current_user: User) -> None:
    if user_has_permission(current_user, 'authz:manage:all'):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='只有权限管理员可以修改 Web 工单执行配置')


@router.get('/workorder-execution-settings', response_model=WorkOrderExecutionSettingsPayload)
def get_workorder_execution_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_read_access(current_user)
    return load_work_order_execution_settings(db)


@router.put('/workorder-execution-settings', response_model=WorkOrderExecutionSettingsPayload)
def update_workorder_execution_settings(
    payload: WorkOrderExecutionSettingsUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_write_access(current_user)
    current_settings = load_work_order_execution_settings(db)
    version_before = get_work_order_execution_settings_version(current_settings)

    if payload.config_version is not None and int(payload.config_version) != version_before:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='配置已被其他人更新，请刷新后重试',
        )

    version_after = version_before + 1
    next_settings = build_work_order_execution_settings_from_payload(
        payload,
        version_after=version_after,
    )
    return save_work_order_execution_settings(db, next_settings)


@router.get(
    '/workorder-execution-settings/effective',
    response_model=EffectiveWorkOrderExecutionSettingsResponse,
)
def get_effective_workorder_execution_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_effective_work_order_execution_settings(db, current_user)
