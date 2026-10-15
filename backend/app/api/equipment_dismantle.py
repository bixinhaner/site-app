"""设备拆除/移机接口：解绑已验收站点上的设备，供新站点重新派单绑定。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.authz import require_permission
from app.core.database import get_db
from app.models.user import User
from app.services.equipment_dismantle_service import execute_dismantle, preview_dismantle

DISMANTLE_PERMISSION = "inventory:dismantle:write"

router = APIRouter()


@router.post("/preview")
async def dismantle_preview(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(DISMANTLE_PERMISSION)),
):
    """按 SN 列表预览当前绑定站点与能否拆除，不写入任何数据。"""
    try:
        return preview_dismantle(db, payload.get("sns"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("")
async def dismantle_execute(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(DISMANTLE_PERMISSION)),
):
    """拆除/移机：整批校验通过后写入解绑记录并回退设备状态；任一 SN 不满足条件则整批不处理。"""
    try:
        result = execute_dismantle(
            db,
            raw_sns=payload.get("sns"),
            reason=payload.get("reason"),
            operator_id=current_user.id,
        )
    except ValueError as exc:
        # 校验在写入前完成，无需回滚；勿在此 rollback，否则会使 current_user 过期，操作日志中间件读取时报错
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return {"message": "拆除成功", **result}
