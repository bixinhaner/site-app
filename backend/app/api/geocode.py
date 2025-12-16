from fastapi import APIRouter, HTTPException, Query
import requests

from app.core.config import settings

router = APIRouter()


@router.get("/geo/baidu-reverse")
def baidu_reverse_geocode(
    lat: float = Query(..., description="纬度"),
    lng: float = Query(..., description="经度"),
):
    """
    使用百度地图 Web 服务进行逆地理解析（仅用于测试）。

    前端只需要传入 GCJ-02 坐标（如 uni.getLocation type='gcj02' 返回的），
    后端会以 coordtype=gcj02ll 请求百度接口。
    """
    ak = settings.BAIDU_MAP_AK
    if not ak:
        raise HTTPException(
            status_code=500,
            detail="BAIDU_MAP_AK 未配置，请在后端环境变量或 .env 中设置",
        )

    params = {
        "ak": ak,
        "output": "json",
        # 目前前端测试页面与原生插件都返回 wgs84 坐标，这里按 wgs84ll 处理
        "coordtype": "wgs84ll",
        "location": f"{lat},{lng}",
    }

    try:
        resp = requests.get(
            "https://api.map.baidu.com/reverse_geocoding/v3/",
            params=params,
            timeout=5.0,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Baidu API 请求失败: {exc}",
        ) from exc

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Baidu API HTTP错误: {resp.text[:200]}",
        )

    data = resp.json()
    if data.get("status") != 0:
        # 百度错误信息通常在 msg 或 message 中
        msg = data.get("msg") or data.get("message") or "Unknown error"
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
        "location": result.get("location") or {"lat": lat, "lng": lng},
        "raw": data,
    }
