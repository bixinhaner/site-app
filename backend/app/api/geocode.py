from datetime import datetime, timedelta, time as dt_time, timezone

try:
    from zoneinfo import ZoneInfo  # type: ignore
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from fastapi import APIRouter, Depends, HTTPException, Query, status
import requests
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.database import get_db
from app.models.geocode_cache import GeocodeCache
from app.models.system_config import SystemConfig
from app.utils.ttl_cache import TtlLruCache

router = APIRouter()

BAIDU_COORDTYPE = "wgs84ll"
BAIDU_PROVIDER = "baidu_reverse_v3"

if ZoneInfo is not None:
    try:
        BEIJING_TZ = ZoneInfo("Asia/Shanghai")
    except Exception:  # pragma: no cover
        BEIJING_TZ = timezone(timedelta(hours=8))
else:  # pragma: no cover
    BEIJING_TZ = timezone(timedelta(hours=8))

SUCCESS_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 天
NEGATIVE_TTL_SECONDS = 60  # 1 分钟

_l1_cache: TtlLruCache[dict] = TtlLruCache(max_size=10000, default_ttl_seconds=SUCCESS_TTL_SECONDS)
_negative_cache: TtlLruCache[str] = TtlLruCache(max_size=2000, default_ttl_seconds=NEGATIVE_TTL_SECONDS)


def _normalize_coord_key(lat: float, lng: float, precision: int = 4) -> tuple[str, float, float]:
    lat_norm = round(float(lat), precision)
    lng_norm = round(float(lng), precision)

    # 避免 -0.0000
    if abs(lat_norm) < 10 ** (-precision):
        lat_norm = 0.0
    if abs(lng_norm) < 10 ** (-precision):
        lng_norm = 0.0

    lat_str = f"{lat_norm:.{precision}f}"
    lng_str = f"{lng_norm:.{precision}f}"
    return f"{BAIDU_COORDTYPE}:{lat_str},{lng_str}", lat_norm, lng_norm


def _load_baidu_reverse_state(db: Session) -> dict:
    row = db.query(SystemConfig).filter(SystemConfig.key == "baidu_reverse_state").first()
    if not row or not row.value:
        return {}
    if isinstance(row.value, dict):
        return row.value
    return {}


def _save_baidu_reverse_state(db: Session, data: dict) -> None:
    row = db.query(SystemConfig).filter(SystemConfig.key == "baidu_reverse_state").first()
    if not row:
        row = SystemConfig(key="baidu_reverse_state", value=data)
        db.add(row)
    else:
        row.value = data
        flag_modified(row, "value")
    db.commit()


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=BEIJING_TZ)
        return dt.astimezone(BEIJING_TZ)
    except Exception:
        return None


def _next_day_0010_beijing() -> datetime:
    now_bj = datetime.now(BEIJING_TZ)
    next_day = now_bj.date() + timedelta(days=1)
    return datetime.combine(next_day, dt_time(0, 10), tzinfo=BEIJING_TZ)


def _check_circuit_breaker(db: Session) -> tuple[bool, datetime | None, str | None]:
    state = _load_baidu_reverse_state(db)
    disabled_until_raw = state.get("disabled_until") if isinstance(state, dict) else None
    reason = state.get("reason") if isinstance(state, dict) else None
    if not disabled_until_raw:
        return False, None, None

    disabled_until = _parse_iso_datetime(str(disabled_until_raw))
    if not disabled_until:
        return False, None, None

    now_bj = datetime.now(BEIJING_TZ)
    if now_bj < disabled_until:
        return True, disabled_until, str(reason) if reason else None

    # 已过期：自动解除熔断
    _save_baidu_reverse_state(db, {})
    return False, None, None


def _set_quota_circuit_breaker(db: Session, reason: str) -> datetime:
    disabled_until = _next_day_0010_beijing()
    state = {
        "disabled_until": disabled_until.isoformat(),
        "reason": reason,
        "updated_at": datetime.now(BEIJING_TZ).isoformat(),
    }
    _save_baidu_reverse_state(db, state)
    return disabled_until


def _is_quota_exceeded(resp_status_code: int | None, payload: dict | None) -> bool:
    if resp_status_code == 429:
        return True
    if not payload:
        return False
    status_code = payload.get("status")
    if status_code == 4:
        return True
    msg = str(payload.get("msg") or payload.get("message") or "").lower()
    keywords = ["配额", "quota", "qps", "并发", "too many", "limit"]
    return any(k in msg for k in keywords)


def _load_l2_cache(db: Session, coord_key: str) -> tuple[dict | None, int | None]:
    now = datetime.utcnow()
    row = db.query(GeocodeCache).filter(
        GeocodeCache.provider == BAIDU_PROVIDER,
        GeocodeCache.coord_key == coord_key,
    ).first()
    if not row:
        return None, None

    if row.expires_at and row.expires_at > now:
        ttl = int((row.expires_at - now).total_seconds())
        return row.payload, max(1, ttl)

    # 过期：清理
    try:
        db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
    return None, None


def _save_l2_cache(db: Session, coord_key: str, lat_norm: float, lng_norm: float, payload: dict) -> None:
    expires_at = datetime.utcnow() + timedelta(seconds=SUCCESS_TTL_SECONDS)
    row = db.query(GeocodeCache).filter(
        GeocodeCache.provider == BAIDU_PROVIDER,
        GeocodeCache.coord_key == coord_key,
    ).first()

    if not row:
        row = GeocodeCache(
            provider=BAIDU_PROVIDER,
            coord_key=coord_key,
            coordtype=BAIDU_COORDTYPE,
            latitude=lat_norm,
            longitude=lng_norm,
            payload=payload,
            expires_at=expires_at,
        )
        db.add(row)
    else:
        row.coordtype = BAIDU_COORDTYPE
        row.latitude = lat_norm
        row.longitude = lng_norm
        row.payload = payload
        row.expires_at = expires_at
        flag_modified(row, "payload")

    db.commit()


@router.get("/geo/baidu-reverse")
def baidu_reverse_geocode(
    lat: float = Query(..., description="纬度"),
    lng: float = Query(..., description="经度"),
    db: Session = Depends(get_db),
):
    """
    使用百度地图 Web 服务进行逆地理解析（供移动端 Baidu 模式调用）。

    - 坐标系：当前按 wgs84ll 处理（与 uni.getLocation type='wgs84' 一致）
    - 缓存：命中则直接返回（不消耗百度配额）
    - 熔断：识别到“配额/并发超限”后，暂停调用至次日 00:10（北京时间）
    """
    ak = settings.BAIDU_MAP_AK
    if not ak:
        raise HTTPException(
            status_code=500,
            detail="BAIDU_MAP_AK 未配置，请在后端环境变量或 .env 中设置",
        )

    coord_key, lat_norm, lng_norm = _normalize_coord_key(lat, lng, precision=4)

    # L1 内存缓存
    cached = _l1_cache.get(coord_key)
    if cached:
        return cached

    # L2 SQLite 缓存
    cached_l2, ttl_l2 = _load_l2_cache(db, coord_key)
    if cached_l2:
        _l1_cache.set(coord_key, cached_l2, ttl_seconds=ttl_l2)
        return cached_l2

    # 熔断：仅在缓存未命中时生效
    disabled, disabled_until, reason = _check_circuit_breaker(db)
    if disabled and disabled_until:
        until_text = disabled_until.strftime("%Y-%m-%d %H:%M")
        detail = f"百度逆地理服务已暂停至 {until_text}（北京时间）"
        if reason:
            detail = f"{detail}，原因：{reason}"
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

    # 负缓存：避免短时间重试风暴
    cached_error = _negative_cache.get(coord_key)
    if cached_error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Baidu API 暂不可用（已缓存失败）：{cached_error}",
        )

    params = {
        "ak": ak,
        "output": "json",
        "coordtype": BAIDU_COORDTYPE,
        "location": f"{lat_norm},{lng_norm}",
    }

    try:
        resp = requests.get(
            "https://api.map.baidu.com/reverse_geocoding/v3/",
            params=params,
            timeout=5.0,
        )
    except requests.RequestException as exc:
        _negative_cache.set(coord_key, f"请求异常: {exc}", ttl_seconds=NEGATIVE_TTL_SECONDS)
        raise HTTPException(
            status_code=502,
            detail=f"Baidu API 请求失败: {exc}",
        ) from exc

    if resp.status_code != 200:
        _negative_cache.set(
            coord_key,
            f"HTTP错误: {resp.status_code}",
            ttl_seconds=NEGATIVE_TTL_SECONDS,
        )
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Baidu API HTTP错误: {resp.text[:200]}",
        )

    data = resp.json()
    if data.get("status") != 0:
        # 百度错误信息通常在 msg 或 message 中
        msg = data.get("msg") or data.get("message") or "Unknown error"
        if _is_quota_exceeded(resp.status_code, data):
            disabled_until = _set_quota_circuit_breaker(db, str(msg))
            until_text = disabled_until.strftime("%Y-%m-%d %H:%M")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Baidu API 配额/并发超限，已暂停至 {until_text}（北京时间）",
            )
        _negative_cache.set(coord_key, f"业务错误: {msg}", ttl_seconds=NEGATIVE_TTL_SECONDS)
        raise HTTPException(
            status_code=502,
            detail=f"Baidu API 业务错误: {msg}",
        )

    result = data.get("result", {}) or {}
    address = result.get("formatted_address") or ""
    sematic_desc = result.get("sematic_description") or ""
    address_component = result.get("addressComponent") or {}

    payload = {
        "address": address,
        "sematic_description": sematic_desc,
        "address_component": address_component,
        "location": result.get("location") or {"lat": lat, "lng": lng},
        "raw": data,
    }

    # 写穿：仅在真实调用百度成功时写入 SQLite 缓存（命中缓存不会写表）
    _save_l2_cache(db, coord_key, lat_norm, lng_norm, payload)
    _l1_cache.set(coord_key, payload)

    return payload
