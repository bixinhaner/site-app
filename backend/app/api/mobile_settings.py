from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.system_config import SystemConfig


router = APIRouter()


class LocationModeResponse(BaseModel):
  """移动端定位模式响应模型。"""

  mode: str


class LocationModePayload(BaseModel):
  """更新定位模式的请求载荷。"""

  mode: str


def _normalize_mode(mode: str) -> str:
  value = (mode or "").strip().lower()
  if value not in ("native", "baidu"):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="mode 仅支持 'native' 或 'baidu'",
    )
  return value


def _get_location_mode(db: Session) -> str:
  """
  从 SystemConfig 读取当前移动端定位模式。

  - 默认值为 'baidu'
  - 若存储值非法，则回退到默认值
  """
  row = db.query(SystemConfig).filter(SystemConfig.key == "mobile_location_mode").first()
  if not row or not row.value:
    return "baidu"

  data = row.value or {}
  mode = str(data.get("mode") or "").strip().lower()
  if mode not in ("native", "baidu"):
    return "baidu"
  return mode


def _require_admin_or_manager(user: User) -> None:
  if user.role not in ("admin", "manager"):
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="只有管理员或项目经理可以修改定位模式",
    )


@router.get("/location-mode", response_model=LocationModeResponse)
async def get_location_mode(
  db: Session = Depends(get_db),
):
  """
  获取当前移动端定位模式。

  - 返回值示例：{"mode": "baidu"} 或 {"mode": "native"}
  - 该接口对所有客户端开放，不强制登录，仅用于读取配置
  """
  mode = _get_location_mode(db)
  return LocationModeResponse(mode=mode)


@router.put("/location-mode", response_model=LocationModeResponse)
async def update_location_mode(
  payload: LocationModePayload,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  更新移动端定位模式（仅管理员/项目经理可修改）。

  - mode 仅支持 'native' 或 'baidu'
  - 配置存储在 SystemConfig(key='mobile_location_mode') 中，value 为 JSON：
    {"mode": "baidu"}
  """
  _require_admin_or_manager(current_user)

  mode = _normalize_mode(payload.mode)

  row = db.query(SystemConfig).filter(SystemConfig.key == "mobile_location_mode").first()
  if not row:
    row = SystemConfig(key="mobile_location_mode", value={"mode": mode})
    db.add(row)
  else:
    data = row.value or {}
    data["mode"] = mode
    row.value = data
    flag_modified(row, "value")

  db.commit()

  return LocationModeResponse(mode=mode)

