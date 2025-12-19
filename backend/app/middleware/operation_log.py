import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs

from app.core.database import SessionLocal
from app.models.operation_log import OperationLog

_MAX_REQ_BODY_CAPTURE_BYTES = 64 * 1024
_MAX_ERR_BODY_CAPTURE_BYTES = 32 * 1024

_SENSITIVE_KEYS = {
    "password",
    "current_password",
    "new_password",
    "old_password",
    "access_token",
    "refresh_token",
    "token",
    "authorization",
}


def _redact(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            key = str(k or "")
            lk = key.lower()
            if lk in _SENSITIVE_KEYS or "password" in lk or lk.endswith("_token"):
                out[key] = "[REDACTED]"
            else:
                out[key] = _redact(v)
        return out
    return value


def _headers_to_dict(headers) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in headers or []:
        try:
            key = k.decode("latin-1").lower()
        except Exception:
            key = str(k).lower()
        try:
            val = v.decode("latin-1")
        except Exception:
            val = str(v)
        if key not in out:
            out[key] = val
    return out


def _parse_query_params(query_string: bytes) -> Dict[str, Any]:
    if not query_string:
        return {}
    try:
        qs = query_string.decode("utf-8", errors="replace")
    except Exception:
        qs = ""
    parsed = parse_qs(qs, keep_blank_values=True)
    out: Dict[str, Any] = {}
    for k, v in parsed.items():
        if not v:
            out[k] = ""
        elif len(v) == 1:
            out[k] = v[0]
        else:
            out[k] = v
    return out


def _parse_request_body(body: bytes, content_type: str, truncated: bool) -> Any:
    if not body:
        return None

    ct = (content_type or "").lower()
    note = None
    if truncated:
        note = f"body truncated (captured {_MAX_REQ_BODY_CAPTURE_BYTES} bytes)"

    if "multipart/form-data" in ct:
        return {"_note": "multipart omitted", "captured_bytes": len(body), "truncated": truncated}

    if "application/x-www-form-urlencoded" in ct:
        try:
            s = body.decode("utf-8", errors="replace")
            parsed = parse_qs(s, keep_blank_values=True)
            out: Dict[str, Any] = {}
            for k, v in parsed.items():
                if not v:
                    out[k] = ""
                elif len(v) == 1:
                    out[k] = v[0]
                else:
                    out[k] = v
            if note:
                out["_note"] = note
            return out
        except Exception:
            return {"_raw": body.decode("utf-8", errors="replace"), "_note": note or "form parse failed"}

    if "application/json" in ct:
        try:
            obj = json.loads(body.decode("utf-8", errors="replace"))
            if note and isinstance(obj, dict) and "_note" not in obj:
                obj["_note"] = note
            return obj
        except Exception:
            return {"_raw": body.decode("utf-8", errors="replace"), "_note": note or "invalid json"}

    # Other: keep small text only
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        text = "<unreadable>"
    if note:
        return {"_raw": text, "_note": note}
    return {"_raw": text}


def _infer_client(headers: Dict[str, str]) -> str:
    raw = (headers.get("x-client") or "").strip()
    if raw:
        return raw

    ua = (headers.get("user-agent") or "").lower()
    if "uni-app" in ua or "hbuilder" in ua:
        return "uniapp"
    if "mozilla" in ua:
        return "web-admin"
    return "unknown"


def _infer_module(scope: dict, path: str) -> str:
    route = scope.get("route")
    tags = getattr(route, "tags", None)
    if isinstance(tags, list) and tags:
        return str(tags[0])

    p = path or ""
    if p.startswith("/api/users"):
        return "用户管理"
    if p.startswith("/api/sites"):
        return "站点管理"
    if p.startswith("/api/inspections"):
        return "检查管理"
    if p.startswith("/api/work-orders"):
        return "工单管理"
    if p.startswith("/api/stock"):
        return "库存管理"
    if p.startswith("/api/equipment"):
        return "设备管理"
    if p.startswith("/api/site-surveys"):
        return "站点勘察"
    if p.startswith("/api/system"):
        return "系统配置"
    if p.startswith("/api/omc"):
        return "OMC配置"
    if p.startswith("/api/auth"):
        return "认证"
    if p.startswith("/api/operation-logs"):
        return "操作日志"
    return "系统"


def _infer_action(method: str, path: str) -> str:
    p = (path or "").rstrip("/")
    last = p.split("/")[-1] if p else ""
    m = (method or "").upper()

    special = {
        "login": "登录",
        "logout": "退出登录",
        "refresh": "刷新令牌",
        "change-password": "修改密码",
        "export": "导出",
        "export-pdf": "导出",
        "export-batch": "导出",
        "import": "导入",
        "import-excel": "导入",
        "upload": "上传",
        "photos": "上传/管理照片",
        "accept": "接单",
        "recall": "撤回",
        "complete": "完工提交",
        "submit": "提交",
        "approve": "审核通过",
        "reject": "审核驳回",
        "cleanup": "清理",
        "backup": "备份",
        "restore": "恢复",
        "settings": "配置",
    }
    if last in special:
        return special[last]

    if last.endswith("template"):
        return "下载模板"

    if "export" in last:
        return "导出"
    if "import" in last:
        return "导入"

    if m == "GET":
        return "查询"
    if m == "POST":
        return "创建"
    if m in ("PUT", "PATCH"):
        return "更新"
    if m == "DELETE":
        return "删除"
    return m or "未知"


def _infer_object_type_and_id(path: str, path_params: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    p = path or ""
    object_type: Optional[str] = None
    if p.startswith("/api/users"):
        object_type = "用户"
    elif p.startswith("/api/sites"):
        object_type = "站点"
    elif p.startswith("/api/inspections"):
        object_type = "检查"
    elif p.startswith("/api/work-orders"):
        object_type = "工单"
    elif p.startswith("/api/site-surveys"):
        object_type = "勘察"
    elif p.startswith("/api/stock"):
        object_type = "库存"
    elif p.startswith("/api/equipment"):
        object_type = "设备"
    elif p.startswith("/api/system"):
        object_type = "系统"
    elif p.startswith("/api/omc"):
        object_type = "OMC"
    elif p.startswith("/api/auth"):
        object_type = "认证"
    elif p.startswith("/api/operation-logs"):
        object_type = "操作日志"

    params = path_params or {}
    if not params:
        return object_type, None

    for key in (
        "id",
        "site_id",
        "work_order_id",
        "inspection_id",
        "survey_id",
        "user_id",
        "photo_id",
        "item_id",
        "log_id",
    ):
        if key in params and params.get(key) is not None:
            return object_type, str(params.get(key))

    first_val = next(iter(params.values()))
    return object_type, str(first_val) if first_val is not None else None


def _build_desc(
    username: Optional[str],
    module: Optional[str],
    action: Optional[str],
    object_type: Optional[str],
    object_id: Optional[str],
    object_name: Optional[str],
    is_success: bool,
) -> str:
    actor = username or "匿名用户"
    mod = module or "系统"
    act = action or "操作"

    target = ""
    if object_type or object_id or object_name:
        parts = []
        if object_type:
            parts.append(str(object_type))
        if object_name:
            parts.append(f"名称:{object_name}")
        if object_id:
            parts.append(f"ID:{object_id}")
        target = "（" + "，".join(parts) + "）"

    result = "成功" if is_success else "失败"
    return f"{actor} 在【{mod}】{act}{target} - {result}"


def _resolve_user_by_username(db, username: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    try:
        from app.models.user import User

        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None, username, None
        return user.id, user.username, user.role
    except Exception:
        return None, username, None


def _resolve_object_name(db, object_type: Optional[str], object_id: Optional[str]) -> Optional[str]:
    if not object_type or not object_id:
        return None
    try:
        if object_type == "站点":
            from app.models.site import Site

            sid = int(object_id)
            s = db.query(Site).filter(Site.id == sid).first()
            if not s:
                return None
            label = s.site_name or s.site_code
            if s.site_name and s.site_code:
                label = f"{s.site_name}({s.site_code})"
            return label

        if object_type == "用户":
            from app.models.user import User

            uid = int(object_id)
            u = db.query(User).filter(User.id == uid).first()
            if not u:
                return None
            return u.full_name or u.username

        if object_type == "工单":
            from app.models.work_order import WorkOrder

            wo = db.query(WorkOrder).filter(WorkOrder.id == object_id).first()
            if not wo:
                return None
            return wo.title
    except Exception:
        return None
    return None


def _extract_error_message(status_code: int, resp_headers: Dict[str, str], resp_body: bytes, truncated: bool) -> Optional[str]:
    if status_code < 400:
        return None

    ct = (resp_headers.get("content-type") or "").lower()
    if not resp_body:
        return f"HTTP {status_code}"

    if "application/json" in ct:
        try:
            data = json.loads(resp_body.decode("utf-8", errors="replace"))
            if isinstance(data, dict):
                detail = data.get("detail")
                if detail is not None:
                    if isinstance(detail, str):
                        msg = detail
                    else:
                        try:
                            msg = json.dumps(detail, ensure_ascii=False)
                        except Exception:
                            msg = str(detail)
                    if truncated:
                        msg += " ...(truncated)"
                    return msg
            if isinstance(data, str):
                msg = data
            else:
                msg = json.dumps(data, ensure_ascii=False)
            if truncated:
                msg += " ...(truncated)"
            return msg
        except Exception:
            pass

    text = resp_body.decode("utf-8", errors="replace")
    if truncated:
        text += " ...(truncated)"
    return text


def _should_skip(path: str, method: str) -> bool:
    p = path or ""
    if not p.startswith("/api"):
        return True
    if (method or "").upper() == "OPTIONS":
        return True
    # 轨迹上报接口由业务接口本身写入日志，避免中间件重复写入
    if p.rstrip("/") == "/api/operation-logs/track":
        return True
    if p.startswith("/uploads"):
        return True
    m = (method or "").upper()
    # 方案A：不记录普通GET（避免 dashboard 等页面打开产生大量“查询”噪音）
    if m == "GET":
        last = p.rstrip("/").split("/")[-1]
        # 仅保留少量关键 GET（文件导出/模板下载等），其余查询由前端按“功能动作”上报
        if "export" not in last and not last.endswith("template"):
            return True
    return False


def _write_operation_log(log_data: Dict[str, Any]) -> None:
    try:
        with SessionLocal() as db:
            username = log_data.get("username")
            user_id = log_data.get("user_id")
            user_role = log_data.get("user_role")

            if username and user_id is None:
                user_id2, username2, role2 = _resolve_user_by_username(db, username)
                log_data["user_id"] = user_id2
                log_data["username"] = username2 or username
                log_data["user_role"] = user_role or role2

            object_type = log_data.get("object_type")
            object_id = log_data.get("object_id")
            object_name = _resolve_object_name(db, object_type, object_id)
            log_data["object_name"] = object_name

            if not log_data.get("operation_desc"):
                log_data["operation_desc"] = _build_desc(
                    username=log_data.get("username"),
                    module=log_data.get("module"),
                    action=log_data.get("action"),
                    object_type=object_type,
                    object_id=object_id,
                    object_name=object_name,
                    is_success=bool(log_data.get("is_success")),
                )

            row = OperationLog(**log_data)
            db.add(row)
            db.commit()
    except Exception:
        return


class OperationLogMiddleware:
    """
    操作日志（功能动作级）中间件

    说明：
    - 以 ASGI receive/send 包装方式捕获请求体与响应状态，避免 BaseHTTPMiddleware 读取 body 的坑
    - 记录在响应结束后异步写入 SQLite，不阻塞请求返回
    - 自动排除密码/令牌字段（仅针对请求参数/请求体）
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method") or ""
        path = scope.get("path") or ""
        if _should_skip(path, method):
            await self.app(scope, receive, send)
            return

        start = time.monotonic()

        captured_req = bytearray()
        req_truncated = False

        status_code: Optional[int] = None
        resp_headers_raw = []
        captured_err_resp = bytearray()
        err_resp_truncated = False

        logged = False

        async def receive_wrapper():
            nonlocal req_truncated
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"") or b""
                if body:
                    remain = _MAX_REQ_BODY_CAPTURE_BYTES - len(captured_req)
                    if remain > 0:
                        captured_req.extend(body[:remain])
                    if len(body) > remain:
                        req_truncated = True
            return message

        async def schedule_log_write(final_status: int):
            nonlocal logged
            if logged:
                return
            logged = True

            elapsed_ms = int((time.monotonic() - start) * 1000)
            _ = elapsed_ms

            headers = _headers_to_dict(scope.get("headers") or [])
            state = scope.get("state") or {}
            raw_user = None
            try:
                raw_user = state.get("raw_user")
            except Exception:
                raw_user = None

            ip = None
            try:
                ip = scope.get("client")[0] if scope.get("client") else None
            except Exception:
                ip = None

            ua = headers.get("user-agent")
            content_type = headers.get("content-type") or ""

            query_params = _redact(_parse_query_params(scope.get("query_string") or b""))
            path_params = _redact(dict(scope.get("path_params") or {}))

            body_obj = _parse_request_body(bytes(captured_req), content_type, req_truncated)
            body_obj = _redact(body_obj)

            user_id = getattr(raw_user, "id", None) if raw_user else None
            username = getattr(raw_user, "username", None) if raw_user else None
            user_role = getattr(raw_user, "role", None) if raw_user else None

            if not username and isinstance(body_obj, dict):
                candidate = body_obj.get("username") or (body_obj.get("user") or {}).get("username")
                if isinstance(candidate, str) and candidate.strip():
                    username = candidate.strip()

            module = _infer_module(scope, path)
            action = _infer_action(method, path)
            object_type, object_id = _infer_object_type_and_id(path, path_params)

            resp_headers = _headers_to_dict(resp_headers_raw)
            error_message = _extract_error_message(
                status_code=final_status,
                resp_headers=resp_headers,
                resp_body=bytes(captured_err_resp),
                truncated=err_resp_truncated,
            )

            log_data = {
                "id": uuid.uuid4().hex,
                "occurred_at": datetime.now(timezone.utc),
                "user_id": user_id,
                "username": username,
                "user_role": user_role,
                "client": _infer_client(headers),
                "ip": ip,
                "user_agent": ua,
                "request_method": method,
                "request_path": path,
                "query_params": query_params,
                "path_params": path_params,
                "request_body": body_obj,
                "module": module,
                "action": action,
                "object_type": object_type,
                "object_id": object_id,
                "status_code": final_status,
                "is_success": final_status < 400,
                "error_message": error_message,
            }

            asyncio.create_task(asyncio.to_thread(_write_operation_log, log_data))

        async def send_wrapper(message):
            nonlocal status_code, resp_headers_raw, err_resp_truncated
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 200)
                resp_headers_raw = message.get("headers") or []

            if message.get("type") == "http.response.body":
                # 仅捕获错误响应体，便于提取 detail
                if status_code is not None and status_code >= 400:
                    body = message.get("body", b"") or b""
                    if body:
                        remain = _MAX_ERR_BODY_CAPTURE_BYTES - len(captured_err_resp)
                        if remain > 0:
                            captured_err_resp.extend(body[:remain])
                        if len(body) > remain:
                            err_resp_truncated = True

                if not message.get("more_body", False):
                    await schedule_log_write(status_code or 500)

            await send(message)

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except Exception:
            # 若异常未被内部处理（未发送响应），仍记录一条 500
            if status_code is None and not logged:
                await schedule_log_write(500)
            raise
