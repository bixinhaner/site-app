import json
import hashlib
import time
from typing import Dict, Optional

import requests
from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig
from app.services.omc_runtime import (
  acquire_omc_request_slot,
  configure_omc_runtime,
  normalize_omc_runtime_config,
  runtime_stats,
  token_cache,
)


class OmcClient:
  """
  OMC API 客户端（基于 requests，同步调用）。

  使用 API 用户名和密码获取访问 Token：
  - POST /northboundApi/v1/access/token，body 包含 username/password
  - 其他接口通过 Authorization 头携带该 Token
  """

  def __init__(
    self,
    base_url: str,
    username: str,
    password: str,
    timeout_seconds: int = 10,
    rate_limit_per_minute: Optional[int] = None,
    rate_limit_burst: Optional[int] = None,
    token_ttl_seconds: Optional[int] = None,
    source: str = "api_poll",
  ):
    self.base_url = base_url.rstrip("/")
    self.username = username
    self.password = password
    self.timeout = timeout_seconds
    self.source = source or "api_poll"
    runtime_config = normalize_omc_runtime_config(
      {
        "rate_limit_per_minute": rate_limit_per_minute,
        "rate_limit_burst": rate_limit_burst,
        "token_ttl_seconds": token_ttl_seconds,
      }
    )
    configure_omc_runtime(runtime_config)
    self.token_ttl_seconds = runtime_config["token_ttl_seconds"]
    self.session = requests.Session()

  def _build_url(self, path: str) -> str:
    return f"{self.base_url}/{path.lstrip('/')}"

  def _token_cache_key(self) -> str:
    raw = f"{self.base_url}|{self.username}|{self.password}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

  @staticmethod
  def _endpoint_label(path: str) -> str:
    normalized = "/" + path.strip("/")
    if normalized.endswith("/access/token"):
      return "/northboundApi/v1/access/token"
    if normalized.endswith("/device/group"):
      return "/northboundApi/v1/device/group"
    if normalized.endswith("/device/query"):
      return "/northboundApi/v1/device/query"
    if "/enodeb/infos/status/" in normalized:
      return "/northboundApi/v1/enodeb/infos/status/{sn}"
    if "/device/parameters/cellname/" in normalized:
      return "/northboundApi/v1/device/parameters/cellname/{sn}"
    return normalized

  def _record_request(
    self,
    *,
    method: str,
    endpoint: str,
    status_code: Optional[int],
    success: bool,
    started_at: float,
    wait_seconds: float,
    error: Optional[str] = None,
  ) -> None:
    runtime_stats.record_request(
      source=self.source,
      method=method,
      endpoint=endpoint,
      status_code=status_code,
      success=success,
      duration_seconds=time.monotonic() - started_at,
      wait_seconds=wait_seconds,
      error=error,
    )

  def _get_access_token(self, force_refresh: bool = False) -> str:
    """
    通过用户名/密码获取访问 Token。
    """
    cache_key = self._token_cache_key()
    if not force_refresh:
      cached = token_cache.get(cache_key)
      if cached:
        return cached

    url = self._build_url("northboundApi/v1/access/token")
    payload = {"username": self.username, "password": self.password}
    endpoint = "/northboundApi/v1/access/token"
    wait_seconds = acquire_omc_request_slot()
    started_at = time.monotonic()
    status_code = None
    success = False
    error = None
    try:
      resp = self.session.post(url, json=payload, timeout=self.timeout)
      status_code = resp.status_code
      try:
        resp.raise_for_status()
      except Exception as exc:
        error = str(exc)
        raise RuntimeError(f"请求 OMC Token 失败: {url} ({exc})") from exc

      try:
        data = resp.json()
      except json.JSONDecodeError:
        text = resp.text or ""
        error = f"OMC Token 接口返回非 JSON 响应: {text[:200]}"
        raise RuntimeError(error)
      # 文档中的 Response 示例被截图嵌入，这里做尽量宽松的兼容解析：
      # 常见几种形式：
      # 1) { "code": 0, "data": { "token": "xxx" } }
      # 2) { "code": 200, "data": "xxx" }
      # 3) { "token": "xxx" }
      if not isinstance(data, dict):
        error = f"OMC Token 接口响应格式异常: {data}"
        raise RuntimeError(error)

      inner = data.get("data", data)
      token = None
      if isinstance(inner, str):
        token = inner
      elif isinstance(inner, dict):
        token = inner.get("token") or inner.get("accessToken") or inner.get("access_token")
      # 若内层没找到，再尝试从最外层直接取
      if not token:
        token = data.get("token") or data.get("accessToken") or data.get("access_token")

      if not token:
        error = f"无法从 OMC Token 响应中解析 token: {data}"
        raise RuntimeError(error)
      token = str(token)
      token_cache.set(cache_key, token, self.token_ttl_seconds)
      success = True
      return token
    except Exception as exc:
      error = error or str(exc)
      if isinstance(exc, RuntimeError):
        raise
      raise RuntimeError(f"请求 OMC Token 失败: {url} ({exc})") from exc
    finally:
      self._record_request(
        method="POST",
        endpoint=endpoint,
        status_code=status_code,
        success=success,
        started_at=started_at,
        wait_seconds=wait_seconds,
        error=error,
      )

  def _request(self, method: str, path: str) -> Dict:
    return self._authorized_json_request(method, path, allow_404=True)

  def _authorized_json_request(
    self,
    method: str,
    path: str,
    *,
    json_payload: Optional[Dict] = None,
    allow_404: bool = False,
  ) -> Dict:
    url = self._build_url(path)
    endpoint = self._endpoint_label(path)
    last_exc: Optional[Exception] = None

    for attempt in range(2):
      token = self._get_access_token(force_refresh=attempt > 0)
      headers = {"Authorization": token}
      wait_seconds = acquire_omc_request_slot()
      started_at = time.monotonic()
      status_code = None
      success = False
      error = None
      try:
        resp = self.session.request(
          method,
          url,
          json=json_payload,
          headers=headers,
          timeout=self.timeout,
        )
        status_code = resp.status_code
        if status_code == 401 and attempt == 0:
          token_cache.invalidate(self._token_cache_key())
          error = "OMC token expired or unauthorized; refreshed once"
          continue
        # 对 404 做降级处理：视为设备不存在/离线，返回空数据而不是抛异常
        if allow_404 and status_code == 404:
          success = True
          return {"code": 404, "data": {}}
        resp.raise_for_status()
        try:
          data = resp.json()
        except json.JSONDecodeError as exc:
          text = resp.text or ""
          error = f"OMC 返回非 JSON 响应: {text[:200]}"
          last_exc = RuntimeError(error)
          raise last_exc from exc
        if isinstance(data, dict):
          try:
            business_code = int(data.get("code"))
          except (TypeError, ValueError):
            business_code = None
          if business_code == 401 and attempt == 0:
            token_cache.invalidate(self._token_cache_key())
            error = "OMC business token invalid; refreshed once"
            continue
          if business_code is not None and business_code not in (0, 200):
            error = f"OMC business error code={business_code}: {data.get('message') or data.get('msg') or ''}"
            return data
        success = True
        return data
      except Exception as exc:
        last_exc = exc
        error = error or str(exc)
        if status_code == 401 and attempt == 0:
          continue
        raise RuntimeError(f"请求 OMC 接口失败: {url} ({exc})") from exc
      finally:
        self._record_request(
          method=method,
          endpoint=endpoint,
          status_code=status_code,
          success=success,
          started_at=started_at,
          wait_seconds=wait_seconds,
          error=error,
        )

    raise RuntimeError(f"请求 OMC 接口失败: {url} ({last_exc})")

  # === 封装的业务接口 ===

  def get_enodeb_status(self, sn: str) -> Dict:
    """
    获取设备在线状态:
    GET /northboundApi/v1/enodeb/infos/status/{sn}
    """
    path = f"northboundApi/v1/enodeb/infos/status/{sn}"
    return self._request("GET", path)

  def get_device_groups(self) -> Dict:
    """
    获取 OMC 设备分组:
    GET /northboundApi/v1/device/group
    """
    path = "northboundApi/v1/device/group"
    return self._authorized_json_request("GET", path)

  def query_devices(
    self,
    *,
    group_id: int,
    page_size: int,
    page_no: int = 0,
    search_text: Optional[str] = None,
    is_gnb: int = 0,
  ) -> Dict:
    """
    批量查询 OMC 设备快照:
    POST /northboundApi/v1/device/query
    """
    path = "northboundApi/v1/device/query"
    payload = {
      "groupId": int(group_id),
      "pageSize": int(page_size),
      "pageNo": int(page_no),
      "isGnb": int(is_gnb),
    }
    if search_text:
      payload["searchText"] = str(search_text)
    return self._authorized_json_request("POST", path, json_payload=payload)

  def set_cell_name(self, sn: str, cell_name: str, sync_flag: int = 0) -> Dict:
    """
    修改设备小区名:
    PUT /northboundApi/v1/device/parameters/cellname/{sn}
    body: {\"cellName\": \"xxx\", \"syncFlag\": 0}
    """
    path = f"northboundApi/v1/device/parameters/cellname/{sn}"
    payload = {"cellName": cell_name, "syncFlag": sync_flag}
    try:
      return self._authorized_json_request("PUT", path, json_payload=payload)
    except Exception as exc:
      raise RuntimeError(f"修改小区名失败: {self._build_url(path)} ({exc})") from exc


def load_omc_config(db: Session) -> Optional[dict]:
  row = db.query(SystemConfig).filter(SystemConfig.key == "omc_api").first()
  if not row or not row.value:
    return None
  data = row.value or {}
  base_url = (data.get("base_url") or "").strip()
  username = (data.get("username") or "").strip()
  password = (data.get("password") or "").strip()
  timeout = int(data.get("timeout_seconds") or 10)
  runtime_config = normalize_omc_runtime_config(data)
  from app.services.omc_inventory import normalize_inventory_snapshot_config
  inventory_config = normalize_inventory_snapshot_config(data)
  if not base_url or not username or not password:
    return None
  return {
    "base_url": base_url,
    "username": username,
    "password": password,
    "timeout_seconds": timeout,
    **runtime_config,
    **inventory_config,
  }


def get_omc_manual_confirm_enabled(db: Session) -> bool:
  """
  获取“开站设备状态手工确认”开关。

  该开关存储在 system_config.key = "omc_api" 的 JSON 中，
  与 OMC base_url/username/password 是否配置无关。
  """
  row = db.query(SystemConfig).filter(SystemConfig.key == "omc_api").first()
  if not row or not row.value:
    return False
  data = row.value or {}
  return bool(data.get("manual_confirm_enabled") or False)


def get_omc_client(db: Session, source: str = "api_poll") -> Optional[OmcClient]:
  cfg = load_omc_config(db)
  if not cfg:
    return None
  return OmcClient(
    base_url=cfg["base_url"],
    username=cfg.get("username"),
    password=cfg.get("password"),
    timeout_seconds=cfg.get("timeout_seconds", 10),
    rate_limit_per_minute=cfg.get("rate_limit_per_minute"),
    rate_limit_burst=cfg.get("rate_limit_burst"),
    token_ttl_seconds=cfg.get("token_ttl_seconds"),
    source=source,
  )


def parse_online_flag(payload: Dict) -> bool:
  """
  从 /enodeb/infos/status 返回结果中解析在线状态。

  文档示例:
  {
    "code": 0,
    "data": {
      "connectionStatus": "on" | "off" | "Off",
      ...
    }
  }
  """
  data = payload.get("data") or {}
  conn = str(data.get("connectionStatus") or "").strip().lower()
  return conn == "on"


def parse_activated_flag(payload: Dict) -> bool:
  """
  从 /enodeb/infos/status 返回结果中解析“设备已激活”状态。

  业务约定:
  - 使用 cellStatus 字段判断设备是否激活
  - 当 cellStatus 第一个数字为 "1" 时视为已激活
    例如: "1,0" -> 激活;  "0,1" -> 未激活
  """
  data = payload.get("data") or {}
  raw = str(data.get("cellStatus") or "").strip()
  if not raw:
    return False
  first = raw.split(",")[0].strip()
  return first == "1"


def is_success_status_payload(payload: Dict) -> bool:
  """
  判定 OMC /enodeb/infos/status 等接口的业务响应是否“成功”。

  约定:
  - 未提供 code 字段视为成功
  - code 在 {0, 200} 视为成功
  - 其他 code 视为业务失败（例如 402: no device operation permission）
  """
  if not isinstance(payload, dict):
    return False
  code = payload.get("code")
  if code is None:
    return True
  try:
    code_int = int(code)
  except (TypeError, ValueError):
    return False
  return code_int in (0, 200)
