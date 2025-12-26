from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_serializer
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.geocode_cache import GeocodeCache
from app.models.system_config import SystemConfig
from app.models.user import User
from app.utils.timezone import to_utc_iso


router = APIRouter()


def _ensure_admin_or_manager(user: User) -> None:
    if user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问")


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    将数据库取出的 naive datetime 视为 UTC，并规范为 tz-aware UTC。
    FastAPI 序列化 tz-aware datetime 时会带上 +00:00，从而让前端按浏览器本地时区展示。
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_iso_datetime(value: str, tzinfo) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tzinfo)
        return dt.astimezone(tzinfo)
    except Exception:
        return None


class CircuitBreakerInfo(BaseModel):
    disabled: bool = False
    disabled_until: Optional[str] = None
    reason: Optional[str] = None


class GeocodeCacheEntry(BaseModel):
    provider: str
    coord_key: str
    coordtype: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    sematic_description: Optional[str] = None
    hit_count: int = 0
    last_hit_at: Optional[datetime] = None
    expires_at: datetime
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    @field_serializer("last_hit_at", "expires_at", "updated_at", "created_at")
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)


class GeocodeCacheEntriesResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[GeocodeCacheEntry]


class GeocodeCacheStatsResponse(BaseModel):
    total_entries: int
    active_entries: int
    circuit_breaker: CircuitBreakerInfo
    metrics: dict


@router.get("/geocode-cache/entries", response_model=GeocodeCacheEntriesResponse)
def list_geocode_cache_entries(
    q: Optional[str] = Query(None, description="搜索坐标或地址（模糊匹配）"),
    include_expired: bool = Query(False, description="是否包含已过期缓存"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin_or_manager(current_user)

    query = db.query(GeocodeCache)
    now = datetime.utcnow()
    if not include_expired:
        query = query.filter(GeocodeCache.expires_at > now)

    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                GeocodeCache.coord_key.like(pattern),
                GeocodeCache.address.like(pattern),
            )
        )

    total = query.count()

    # 排序：最近命中优先，其次更新时间
    sort_key = func.coalesce(GeocodeCache.last_hit_at, GeocodeCache.updated_at, GeocodeCache.created_at)
    query = query.order_by(sort_key.desc())

    rows = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        GeocodeCacheEntry(
            provider=row.provider,
            coord_key=row.coord_key,
            coordtype=row.coordtype,
            latitude=row.latitude,
            longitude=row.longitude,
            address=row.address,
            sematic_description=row.sematic_description,
            hit_count=int(row.hit_count or 0),
            last_hit_at=_as_utc(row.last_hit_at),
            expires_at=_as_utc(row.expires_at),
            updated_at=_as_utc(row.updated_at),
            created_at=_as_utc(row.created_at),
        )
        for row in rows
    ]

    return GeocodeCacheEntriesResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/geocode-cache/stats", response_model=GeocodeCacheStatsResponse)
def geocode_cache_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin_or_manager(current_user)

    total_entries = db.query(GeocodeCache).count()
    now = datetime.utcnow()
    active_entries = db.query(GeocodeCache).filter(GeocodeCache.expires_at > now).count()

    # 熔断状态（读取 SystemConfig）
    tz_bj = timezone(timedelta(hours=8))
    breaker = CircuitBreakerInfo(disabled=False)

    row = db.query(SystemConfig).filter(SystemConfig.key == "baidu_reverse_state").first()
    if row and isinstance(row.value, dict) and row.value.get("disabled_until"):
        disabled_until = _parse_iso_datetime(str(row.value.get("disabled_until")), tz_bj)
        reason = row.value.get("reason")
        if disabled_until and datetime.now(tz_bj) < disabled_until:
            breaker.disabled = True
            breaker.disabled_until = to_utc_iso(disabled_until)
            breaker.reason = str(reason) if reason else None

    # 进程内统计（命中/调用次数等）
    try:
        from app.api.geocode import get_geocode_metrics

        metrics = get_geocode_metrics()
    except Exception:
        metrics = {}

    return GeocodeCacheStatsResponse(
        total_entries=total_entries,
        active_entries=active_entries,
        circuit_breaker=breaker,
        metrics=metrics,
    )
