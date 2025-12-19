from datetime import datetime, timedelta, time as dt_time, timezone

try:
    from zoneinfo import ZoneInfo  # type: ignore
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from fastapi import APIRouter, Depends, HTTPException, Query, status
import requests
from sqlalchemy import func
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
GOOGLE_PROVIDER = "google_geocode_v1"
GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_DEFAULT_LANGUAGE = "en"
GOOGLE_RELAY_TOKEN_HEADER = "X-Geo-Relay-Token"


def _compose_cache_key(provider: str, coord_key: str) -> str:
    return f"{provider}:{coord_key}"


def _is_within_china(lat: float, lng: float) -> bool:
    """
    粗略判断坐标是否在中国境内（常见的 out_of_china 边界判断）。

    注意：该判断是“近似”的，不能覆盖所有边界情况。
    - 境内：优先走 Baidu（更贴合国内地址）
    - 境外：走 Google（Baidu 对部分境外坐标会返回 240）
    """
    return not (lng < 72.004 or lng > 137.8347 or lat < 0.8293 or lat > 55.8271)

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

_metrics = {
    "requests": 0,
    "hit_l1": 0,
    "hit_l2": 0,
    "negative_hit": 0,
    "breaker_hit": 0,
    "baidu_call": 0,
    "google_call": 0,
    "google_direct_call": 0,
    "google_relay_call": 0,
    "l2_write": 0,
    "breaker_set": 0,
}


def get_geocode_metrics() -> dict:
    return dict(_metrics)


def _metric_inc(key: str) -> None:
    try:
        _metrics[key] = int(_metrics.get(key, 0)) + 1
    except Exception:
        _metrics[key] = 1


def _touch_hit(db: Session, provider: str, coord_key: str) -> None:
    now = datetime.utcnow()
    try:
        db.query(GeocodeCache).filter(
            GeocodeCache.provider == provider,
            GeocodeCache.coord_key == coord_key,
        ).update(
            {
                GeocodeCache.hit_count: func.coalesce(GeocodeCache.hit_count, 0) + 1,
                GeocodeCache.last_hit_at: now,
            },
            synchronize_session=False,
        )
        db.commit()
    except Exception:
        db.rollback()


def _normalize_coord_key(lat: float, lng: float, *, grid_step_units: int = 3) -> tuple[str, float, float]:
    """
    将经纬度归一化为缓存 Key（提升缓存命中率）。

    说明：
    - 这里采用“固定经纬度网格”的方式做近似：先把经纬度按 1e-4 度量化，再按 grid_step_units 进行分桶。
    - 默认 grid_step_units=3，即 0.0003° 网格，约等于 30m 量级（随纬度会有少量偏差）。
    """
    scale = 10000  # 1e-4 度
    step = max(1, int(grid_step_units))

    lat_units = int(round(float(lat) * scale / step)) * step
    lng_units = int(round(float(lng) * scale / step)) * step

    lat_norm = lat_units / scale
    lng_norm = lng_units / scale

    # 避免 -0.0000
    if abs(lat_norm) < 1 / scale:
        lat_norm = 0.0
    if abs(lng_norm) < 1 / scale:
        lng_norm = 0.0

    lat_str = f"{lat_norm:.4f}"
    lng_str = f"{lng_norm:.4f}"
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
    _metric_inc("breaker_set")
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


def _load_l2_cache(db: Session, provider: str, coord_key: str) -> tuple[dict | None, int | None]:
    now = datetime.utcnow()
    row = db.query(GeocodeCache).filter(
        GeocodeCache.provider == provider,
        GeocodeCache.coord_key == coord_key,
    ).first()
    if not row:
        return None, None

    if row.expires_at and row.expires_at > now:
        # 命中 L2：记录命中次数
        row.hit_count = int(row.hit_count or 0) + 1
        row.last_hit_at = now
        try:
            db.commit()
        except Exception:
            db.rollback()
        ttl = int((row.expires_at - now).total_seconds())
        return row.payload, max(1, ttl)

    # 过期：清理
    try:
        db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
    return None, None


def _save_l2_cache(db: Session, provider: str, coord_key: str, lat_norm: float, lng_norm: float, payload: dict) -> None:
    expires_at = datetime.utcnow() + timedelta(seconds=SUCCESS_TTL_SECONDS)
    row = db.query(GeocodeCache).filter(
        GeocodeCache.provider == provider,
        GeocodeCache.coord_key == coord_key,
    ).first()

    if not row:
        row = GeocodeCache(
            provider=provider,
            coord_key=coord_key,
            coordtype=BAIDU_COORDTYPE,
            latitude=lat_norm,
            longitude=lng_norm,
            address=str(payload.get("address") or ""),
            sematic_description=str(payload.get("sematic_description") or ""),
            payload=payload,
            expires_at=expires_at,
        )
        db.add(row)
    else:
        row.coordtype = BAIDU_COORDTYPE
        row.latitude = lat_norm
        row.longitude = lng_norm
        row.address = str(payload.get("address") or "")
        row.sematic_description = str(payload.get("sematic_description") or "")
        row.payload = payload
        row.expires_at = expires_at
        flag_modified(row, "payload")

    db.commit()
    _metric_inc("l2_write")


def _provider_label(provider: str) -> str:
    if provider == BAIDU_PROVIDER:
        return "Baidu"
    if provider == GOOGLE_PROVIDER:
        return "Google"
    return provider


def _is_baidu_app_disabled(detail: str | None) -> bool:
    text = str(detail or "")
    return "APP 服务被禁用" in text


def _google_component_value(components: list[dict], type_name: str) -> str:
    for comp in components:
        types = comp.get("types") or []
        if type_name in types:
            return str(comp.get("long_name") or comp.get("short_name") or "")
    return ""


def _build_google_address_component(components: list[dict]) -> dict:
    country = _google_component_value(components, "country")
    province = _google_component_value(components, "administrative_area_level_1")

    city = _google_component_value(components, "locality")
    if not city:
        city = _google_component_value(components, "postal_town")
    if not city:
        city = _google_component_value(components, "administrative_area_level_2")

    district = _google_component_value(components, "sublocality_level_1")
    if not district:
        district = _google_component_value(components, "sublocality")
    if not district:
        district = _google_component_value(components, "administrative_area_level_3")
    if not district:
        district = _google_component_value(components, "neighborhood")

    street = _google_component_value(components, "route")
    street_number = _google_component_value(components, "street_number")

    return {
        "country": country,
        "province": province,
        "city": city,
        "district": district,
        "street": street,
        "street_number": street_number,
    }


def _fetch_baidu_payload(
    *,
    db: Session,
    ak: str,
    lat_norm: float,
    lng_norm: float,
    lat_raw: float,
    lng_raw: float,
    negative_cache_key: str,
) -> dict:
    params = {
        "ak": ak,
        "output": "json",
        "coordtype": BAIDU_COORDTYPE,
        "location": f"{lat_norm},{lng_norm}",
    }

    try:
        _metric_inc("baidu_call")
        resp = requests.get(
            "https://api.map.baidu.com/reverse_geocoding/v3/",
            params=params,
            timeout=5.0,
        )
    except requests.RequestException as exc:
        _negative_cache.set(negative_cache_key, f"请求异常: {exc}", ttl_seconds=NEGATIVE_TTL_SECONDS)
        raise HTTPException(
            status_code=502,
            detail=f"Baidu API 请求失败: {exc}",
        ) from exc

    if resp.status_code != 200:
        _negative_cache.set(
            negative_cache_key,
            f"HTTP错误: {resp.status_code}",
            ttl_seconds=NEGATIVE_TTL_SECONDS,
        )
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Baidu API HTTP错误: {resp.text[:200]}",
        )

    data = resp.json()
    if data.get("status") != 0:
        msg = data.get("msg") or data.get("message") or "Unknown error"
        if _is_quota_exceeded(resp.status_code, data):
            disabled_until = _set_quota_circuit_breaker(db, str(msg))
            until_text = disabled_until.strftime("%Y-%m-%d %H:%M")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Baidu API 配额/并发超限，已暂停至 {until_text}（北京时间）",
            )
        _negative_cache.set(negative_cache_key, f"业务错误: {msg}", ttl_seconds=NEGATIVE_TTL_SECONDS)
        raise HTTPException(
            status_code=502,
            detail=f"Baidu API 业务错误: {msg}",
        )

    result = data.get("result", {}) or {}
    address = result.get("formatted_address") or ""
    sematic_desc = result.get("sematic_description") or ""
    address_component = result.get("addressComponent") or {}

    return {
        "address": address,
        "sematic_description": sematic_desc,
        "address_component": address_component,
        "location": result.get("location") or {"lat": lat_raw, "lng": lng_raw},
        "raw": data,
    }


def _fetch_google_payload(
    *,
    api_key: str,
    lat_norm: float,
    lng_norm: float,
    lat_raw: float,
    lng_raw: float,
    negative_cache_key: str,
) -> dict:
    relay_url = str(getattr(settings, "GOOGLE_GEOCODE_RELAY_URL", "") or "").strip()
    relay_token = str(getattr(settings, "GOOGLE_GEOCODE_RELAY_TOKEN", "") or "").strip()

    # 优先走 Relay：用于部署在中国境内的后端无法直连 Google 的场景
    if relay_url:
        params = {
            "lat": f"{lat_norm}",
            "lng": f"{lng_norm}",
            "language": GOOGLE_DEFAULT_LANGUAGE,
        }
        headers = {GOOGLE_RELAY_TOKEN_HEADER: relay_token} if relay_token else {}

        try:
            _metric_inc("google_call")
            _metric_inc("google_relay_call")
            resp = requests.get(relay_url, params=params, headers=headers, timeout=5.0)
        except requests.RequestException as exc:
            _negative_cache.set(negative_cache_key, f"Relay请求异常: {exc}", ttl_seconds=NEGATIVE_TTL_SECONDS)
            raise HTTPException(status_code=502, detail=f"Google Relay 请求失败: {exc}") from exc

        if resp.status_code in (401, 403):
            _negative_cache.set(negative_cache_key, f"Relay鉴权失败: {resp.status_code}", ttl_seconds=NEGATIVE_TTL_SECONDS)
            raise HTTPException(status_code=502, detail=f"Google Relay 鉴权失败（{resp.status_code}），请检查 Token 与防火墙白名单")

        if resp.status_code != 200:
            _negative_cache.set(negative_cache_key, f"RelayHTTP错误: {resp.status_code}", ttl_seconds=NEGATIVE_TTL_SECONDS)
            raise HTTPException(status_code=resp.status_code, detail=f"Google Relay HTTP错误: {resp.text[:200]}")

        try:
            data = resp.json()
        except ValueError as exc:
            body_snippet = (resp.text or "")[:200]
            _negative_cache.set(
                negative_cache_key,
                f"Relay JSON解析失败: {exc}; body={body_snippet}",
                ttl_seconds=NEGATIVE_TTL_SECONDS,
            )
            raise HTTPException(status_code=502, detail="Google Relay 返回非 JSON 响应") from exc

        if not isinstance(data, dict):
            _negative_cache.set(
                negative_cache_key,
                f"Relay 返回格式错误: {type(data)}",
                ttl_seconds=NEGATIVE_TTL_SECONDS,
            )
            raise HTTPException(status_code=502, detail="Google Relay 返回格式错误")

        data = data or {}
    else:
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_MAPS_API_KEY 未配置（或配置 GOOGLE_GEOCODE_RELAY_URL 走境外 Relay）",
            )

        params = {
            "key": api_key,
            "latlng": f"{lat_norm},{lng_norm}",
            "language": GOOGLE_DEFAULT_LANGUAGE,
        }

        try:
            _metric_inc("google_call")
            _metric_inc("google_direct_call")
            resp = requests.get(GOOGLE_GEOCODE_URL, params=params, timeout=5.0)
        except requests.RequestException as exc:
            _negative_cache.set(negative_cache_key, f"请求异常: {exc}", ttl_seconds=NEGATIVE_TTL_SECONDS)
            raise HTTPException(status_code=502, detail=f"Google API 请求失败: {exc}") from exc

        if resp.status_code != 200:
            _negative_cache.set(negative_cache_key, f"HTTP错误: {resp.status_code}", ttl_seconds=NEGATIVE_TTL_SECONDS)
            raise HTTPException(status_code=resp.status_code, detail=f"Google API HTTP错误: {resp.text[:200]}")

        try:
            data = resp.json()
        except ValueError as exc:
            body_snippet = (resp.text or "")[:200]
            _negative_cache.set(
                negative_cache_key,
                f"JSON解析失败: {exc}; body={body_snippet}",
                ttl_seconds=NEGATIVE_TTL_SECONDS,
            )
            raise HTTPException(status_code=502, detail="Google API 返回非 JSON 响应") from exc

        if not isinstance(data, dict):
            _negative_cache.set(
                negative_cache_key,
                f"返回格式错误: {type(data)}",
                ttl_seconds=NEGATIVE_TTL_SECONDS,
            )
            raise HTTPException(status_code=502, detail="Google API 返回格式错误")

        data = data or {}

    status_text = str(data.get("status") or "")

    if status_text == "ZERO_RESULTS":
        # 无结果：也返回 200，并写入缓存，避免重复打第三方
        return {
            "address": "",
            "sematic_description": "",
            "address_component": {},
            "location": {"lat": lat_raw, "lng": lng_raw},
            "raw": data,
        }

    if status_text != "OK":
        msg = data.get("error_message") or status_text or "Unknown error"
        _negative_cache.set(negative_cache_key, f"业务错误: {msg}", ttl_seconds=NEGATIVE_TTL_SECONDS)
        raise HTTPException(status_code=502, detail=f"Google API 业务错误: {msg}")

    results = data.get("results") or []
    best = results[0] if results else {}
    address = best.get("formatted_address") or ""
    components = best.get("address_components") or []
    address_component = _build_google_address_component(components) if components else {}
    geometry = best.get("geometry") or {}
    location = geometry.get("location") or {"lat": lat_raw, "lng": lng_raw}

    return {
        "address": address,
        "sematic_description": "",
        "address_component": address_component,
        "location": location,
        "raw": data,
    }


def _reverse_geocode_with_provider(
    *,
    provider: str,
    coord_key: str,
    lat_norm: float,
    lng_norm: float,
    lat_raw: float,
    lng_raw: float,
    db: Session,
) -> dict:
    cache_key = _compose_cache_key(provider, coord_key)

    cached = _l1_cache.get(cache_key)
    if cached:
        _metric_inc("hit_l1")
        _touch_hit(db, provider, coord_key)
        return cached

    cached_l2, ttl_l2 = _load_l2_cache(db, provider, coord_key)
    if cached_l2:
        _metric_inc("hit_l2")
        _l1_cache.set(cache_key, cached_l2, ttl_seconds=ttl_l2)
        return cached_l2

    # Baidu 熔断：仅在缓存未命中时生效
    if provider == BAIDU_PROVIDER:
        disabled, disabled_until, reason = _check_circuit_breaker(db)
        if disabled and disabled_until:
            _metric_inc("breaker_hit")
            until_text = disabled_until.strftime("%Y-%m-%d %H:%M")
            detail = f"百度逆地理服务已暂停至 {until_text}（北京时间）"
            if reason:
                detail = f"{detail}，原因：{reason}"
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

    # 负缓存：避免短时间重试风暴（不落库）
    cached_error = _negative_cache.get(cache_key)
    if cached_error:
        _metric_inc("negative_hit")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{_provider_label(provider)} API 暂不可用（已缓存失败）：{cached_error}",
        )

    if provider == BAIDU_PROVIDER:
        ak = settings.BAIDU_MAP_AK
        if not ak:
            raise HTTPException(status_code=500, detail="BAIDU_MAP_AK 未配置，请在后端环境变量或 .env 中设置")
        payload = _fetch_baidu_payload(
            db=db,
            ak=ak,
            lat_norm=lat_norm,
            lng_norm=lng_norm,
            lat_raw=lat_raw,
            lng_raw=lng_raw,
            negative_cache_key=cache_key,
        )
    elif provider == GOOGLE_PROVIDER:
        payload = _fetch_google_payload(
            api_key=settings.GOOGLE_MAPS_API_KEY,
            lat_norm=lat_norm,
            lng_norm=lng_norm,
            lat_raw=lat_raw,
            lng_raw=lng_raw,
            negative_cache_key=cache_key,
        )
    else:
        raise HTTPException(status_code=500, detail=f"不支持的逆地理 Provider: {provider}")

    # 写穿：仅在真实调用第三方成功时写入 SQLite 缓存（命中缓存不会写表）
    _save_l2_cache(db, provider, coord_key, lat_norm, lng_norm, payload)
    _l1_cache.set(cache_key, payload)
    return payload


@router.get("/geo/baidu-reverse")
def baidu_reverse_geocode(
    lat: float = Query(..., description="纬度"),
    lng: float = Query(..., description="经度"),
    db: Session = Depends(get_db),
):
    """
    逆地理解析（移动端 Baidu 模式调用的后端代理接口）。

    - 坐标系：当前按 wgs84ll 处理（与 uni.getLocation type='wgs84' 一致）
    - 国内坐标：优先走 Baidu（更贴合国内地址）
    - 境外坐标：走 Google（Baidu 对部分境外坐标会返回 240）
    - 缓存：L1 内存 + L2 SQLite（按约 30m 网格归一化；命中则直接返回，不消耗第三方配额）
    - 熔断：仅对 Baidu 生效（识别到“配额/并发超限”后暂停至次日 00:10 北京时间）
    """
    _metric_inc("requests")
    coord_key, lat_norm, lng_norm = _normalize_coord_key(lat, lng)
    preferred = BAIDU_PROVIDER if _is_within_china(lat_norm, lng_norm) else GOOGLE_PROVIDER

    try:
        return _reverse_geocode_with_provider(
            provider=preferred,
            coord_key=coord_key,
            lat_norm=lat_norm,
            lng_norm=lng_norm,
            lat_raw=lat,
            lng_raw=lng,
            db=db,
        )
    except HTTPException as exc:
        # 兜底：若因 Baidu 区域限制返回 “APP 服务被禁用”，则回退到 Google
        if preferred == BAIDU_PROVIDER and _is_baidu_app_disabled(str(exc.detail)):
            return _reverse_geocode_with_provider(
                provider=GOOGLE_PROVIDER,
                coord_key=coord_key,
                lat_norm=lat_norm,
                lng_norm=lng_norm,
                lat_raw=lat,
                lng_raw=lng,
                db=db,
            )
        raise
