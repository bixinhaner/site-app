from __future__ import annotations

from typing import Iterable

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from starlette.concurrency import run_in_threadpool

from app.api.auth import get_current_user
from app.core.config import settings
from app.models.user import User

router = APIRouter()


def _ensure_admin(user: User) -> None:
    # 当前仅 admin 可访问（manager 不再自动等同 admin）
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can access Mock OMC",
        )


_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _filter_request_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    filtered: dict[str, str] = {}
    for k, v in headers:
        lk = k.lower()
        if lk in _HOP_BY_HOP_HEADERS:
            continue
        # 不向内网服务透传前端的认证信息
        if lk == "authorization":
            continue
        if lk == "host":
            continue
        filtered[k] = v
    return filtered


def _filter_response_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    filtered: dict[str, str] = {}
    for k, v in headers:
        lk = k.lower()
        if lk in _HOP_BY_HOP_HEADERS:
            continue
        # requests 会自动解压 gzip 等内容，但 headers 仍可能保留 content-encoding，需移除避免浏览器重复解压
        if lk == "content-encoding":
            continue
        if lk == "content-length":
            continue
        filtered[k] = v
    return filtered


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_mock_omc(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Mock-OMC 反向代理（浏览器无法直连 9000 时使用）。

    - 对外暴露：/api/mock-omc/*
    - 内部转发：settings.MOCK_OMC_BASE_URL（默认 http://127.0.0.1:9000）
    - 权限：仅 admin/manager
    """
    _ensure_admin(current_user)

    base = (settings.MOCK_OMC_BASE_URL or "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mock OMC base url is not configured",
        )

    # 防御性处理：避免双斜杠导致路径解析异常
    safe_path = (path or "").lstrip("/")
    target_url = f"{base}/{safe_path}" if safe_path else f"{base}/"

    body = await request.body()
    params = list(request.query_params.multi_items())
    headers = _filter_request_headers(request.headers.items())
    timeout = settings.MOCK_OMC_TIMEOUT_SECONDS or 10

    def _do_request():
        return requests.request(
            method=request.method,
            url=target_url,
            params=params,
            data=body if body else None,
            headers=headers,
            timeout=timeout,
        )

    try:
        resp = await run_in_threadpool(_do_request)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Mock OMC unavailable: {exc}",
        ) from exc

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=_filter_response_headers(resp.headers.items()),
    )
