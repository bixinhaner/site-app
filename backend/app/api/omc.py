from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.system_config import SystemConfig
from app.services.omc_client import load_omc_config, OmcClient

router = APIRouter()


class OmcConfigPayload(BaseModel):
  base_url: str
  username: str
  password: Optional[str] = None
  timeout_seconds: Optional[int] = 10


class OmcConfigResponse(BaseModel):
  base_url: Optional[str] = None
  username: Optional[str] = None
  timeout_seconds: int = 10


class OmcTestResponse(BaseModel):
  success: bool
  message: str


def _ensure_admin(user: User) -> None:
  if user.role != "admin":
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="Only admin can manage OMC configuration",
    )


def _load_omc_config(db: Session) -> OmcConfigResponse:
  row = db.query(SystemConfig).filter(SystemConfig.key == "omc_api").first()
  if not row or not row.value:
    return OmcConfigResponse()
  data = row.value or {}
  return OmcConfigResponse(
    base_url=data.get("base_url"),
    username=data.get("username"),
    timeout_seconds=int(data.get("timeout_seconds") or 10),
  )


@router.get("/config", response_model=OmcConfigResponse)
async def get_omc_config(
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  获取 OMC API 配置（仅 admin 可见）。
  """
  _ensure_admin(current_user)
  return _load_omc_config(db)


@router.put("/config", response_model=OmcConfigResponse)
async def update_omc_config(
  payload: OmcConfigPayload,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  更新 OMC API 配置（仅 admin 可修改）。
  """
  _ensure_admin(current_user)

  raw_url = (payload.base_url or "").strip()
  # 若用户未包含协议，默认加上 http://
  if "://" not in raw_url:
    raw_url = f"http://{raw_url}"
  base_url = raw_url.rstrip("/")
  username = payload.username.strip()
  new_password = (payload.password or "").strip()
  timeout = payload.timeout_seconds or 10

  row = db.query(SystemConfig).filter(SystemConfig.key == "omc_api").first()
  if not row:
    data = {
      "base_url": base_url,
      "username": username,
      "password": new_password,
      "timeout_seconds": timeout,
    }
    row = SystemConfig(key="omc_api", value=data)
    db.add(row)
  else:
    data = row.value or {}
    data["base_url"] = base_url
    data["username"] = username
    data["timeout_seconds"] = timeout
    # 只有在传入非空 password 时才更新存储的密码
    if new_password:
      data["password"] = new_password
    row.value = data
    # JSON 字段需要显式标记已修改，SQLAlchemy 才会持久化变更
    flag_modified(row, "value")

  db.commit()

  return OmcConfigResponse(
    base_url=base_url,
    username=username,
    timeout_seconds=timeout,
  )


@router.post("/test", response_model=OmcTestResponse)
async def test_omc_connection(
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  使用当前配置测试与 OMC API 的连通性（仅 admin）。

  - 会尝试调用 /northboundApi/v1/access/token 获取 Token
  - 成功则返回 success=True；失败则返回具体错误信息
  """
  _ensure_admin(current_user)

  cfg = load_omc_config(db)
  if not cfg:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="未找到有效的 OMC 配置，请先保存配置后再测试。",
    )

  try:
    # 使用当前配置尝试获取 Token，用于同时验证连通性和账号密码是否正确
    client = OmcClient(
      base_url=cfg["base_url"],
      username=cfg["username"],
      password=cfg["password"],
      timeout_seconds=cfg.get("timeout_seconds", 10),
    )
    token = client._get_access_token()  # noqa: SLF001
    preview = token[:16] + "..." if token else ""
    return OmcTestResponse(
      success=True,
      message=f"与 OMC 连通成功，账号密码校验通过，Token 前缀: {preview}",
    )
  except Exception as exc:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"连接 OMC 或校验账号失败: {exc}",
    ) from exc
