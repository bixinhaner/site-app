from __future__ import annotations

import os

from fastapi import FastAPI, Header, HTTPException, Query, status
import requests

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
DEFAULT_LANGUAGE = "en"
TOKEN_HEADER = "X-Geo-Relay-Token"

app = FastAPI(
    title="Geo Relay",
    description="用于境外服务器代发 Google 逆地理请求的轻量 Relay 服务",
    version="1.0.0",
)


def _require_token(token: str | None) -> None:
    expected = str(os.getenv("GEO_RELAY_TOKEN", "") or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GEO_RELAY_TOKEN 未配置（为安全起见必须配置）",
        )
    if token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid relay token")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/geo/google-reverse")
def google_reverse(
    lat: float = Query(..., description="纬度"),
    lng: float = Query(..., description="经度"),
    language: str = Query(DEFAULT_LANGUAGE, description="语言（默认 en）"),
    relay_token: str | None = Header(None, alias=TOKEN_HEADER),
):
    _require_token(relay_token)

    api_key = str(os.getenv("GOOGLE_MAPS_API_KEY", "") or "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_MAPS_API_KEY 未配置")

    params = {
        "key": api_key,
        "latlng": f"{lat},{lng}",
        "language": language or DEFAULT_LANGUAGE,
    }

    try:
        resp = requests.get(GOOGLE_GEOCODE_URL, params=params, timeout=5.0)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Google API 请求失败: {exc}") from exc

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Google API HTTP错误: {resp.text[:200]}")

    # 直接返回 Google 原始 JSON，由调用方负责解析/缓存
    return resp.json()

