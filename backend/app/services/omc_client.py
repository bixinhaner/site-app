import json
from typing import Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig


class OmcClient:
  """
  OMC API 客户端（基于 requests，同步调用）。

  使用 API 用户名和密码获取访问 Token：
  - POST /northboundApi/v1/access/token，body 包含 username/password
  - 其他接口通过 Authorization 头携带该 Token
  """

  def __init__(self, base_url: str, username: str, password: str, timeout_seconds: int = 10):
    self.base_url = base_url.rstrip("/")
    self.username = username
    self.password = password
    self.timeout = timeout_seconds
    self.session = requests.Session()

  def _build_url(self, path: str) -> str:
    return f"{self.base_url}/{path.lstrip('/')}"

  def _get_access_token(self) -> str:
    """
    通过用户名/密码获取访问 Token。
    """
    url = self._build_url("northboundApi/v1/access/token")
    payload = {"username": self.username, "password": self.password}
    try:
      resp = self.session.post(url, json=payload, timeout=self.timeout)
      resp.raise_for_status()
    except Exception as exc:
      raise RuntimeError(f"请求 OMC Token 失败: {url} ({exc})") from exc

    try:
      data = resp.json()
    except json.JSONDecodeError:
      text = resp.text or ""
      raise RuntimeError(f"OMC Token 接口返回非 JSON 响应: {text[:200]}")
    # 文档中的 Response 示例被截图嵌入，这里做尽量宽松的兼容解析：
    # 常见几种形式：
    # 1) { "code": 0, "data": { "token": "xxx" } }
    # 2) { "code": 200, "data": "xxx" }
    # 3) { "token": "xxx" }
    if not isinstance(data, dict):
      raise RuntimeError(f"OMC Token 接口响应格式异常: {data}")

    code = data.get("code")
    # 如果带有 code 且不是“成功”的常见值，仍然先尝试解析 token，找不到再报错

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
      raise RuntimeError(f"无法从 OMC Token 响应中解析 token: {data}")
    return str(token)

  def _request(self, method: str, path: str) -> Dict:
    url = self._build_url(path)
    token = self._get_access_token()
    headers = {"Authorization": token}
    try:
      resp = self.session.request(method, url, headers=headers, timeout=self.timeout)
      # 对 404 做降级处理：视为设备不存在/离线，返回空数据而不是抛异常
      if resp.status_code == 404:
        return {"code": 404, "data": {}}
      resp.raise_for_status()
    except Exception as exc:
      raise RuntimeError(f"请求 OMC 接口失败: {url} ({exc})") from exc

    try:
      return resp.json()
    except json.JSONDecodeError:
      text = resp.text or ""
      raise RuntimeError(f"OMC 返回非 JSON 响应: {text[:200]}")

  # === 封装的业务接口 ===

  def get_enodeb_status(self, sn: str) -> Dict:
    """
    获取设备在线状态:
    GET /northboundApi/v1/enodeb/infos/status/{sn}
    """
    path = f"northboundApi/v1/enodeb/infos/status/{sn}"
    return self._request("GET", path)

  def set_cell_name(self, sn: str, cell_name: str, sync_flag: int = 0) -> Dict:
    """
    修改设备小区名:
    PUT /northboundApi/v1/device/parameters/cellname/{sn}
    body: {\"cellName\": \"xxx\", \"syncFlag\": 0}
    """
    path = f"northboundApi/v1/device/parameters/cellname/{sn}"
    payload = {"cellName": cell_name, "syncFlag": sync_flag}
    url = self._build_url(path)
    token = self._get_access_token()
    headers = {"Authorization": token}
    try:
      resp = self.session.put(url, json=payload, headers=headers, timeout=self.timeout)
      resp.raise_for_status()
      return resp.json()
    except Exception as exc:
      raise RuntimeError(f"修改小区名失败: {url} ({exc})") from exc


def load_omc_config(db: Session) -> Optional[dict]:
  row = db.query(SystemConfig).filter(SystemConfig.key == "omc_api").first()
  if not row or not row.value:
    return None
  data = row.value or {}
  base_url = (data.get("base_url") or "").strip()
  username = (data.get("username") or "").strip()
  password = (data.get("password") or "").strip()
  timeout = int(data.get("timeout_seconds") or 10)
  if not base_url or not username or not password:
    return None
  return {
    "base_url": base_url,
    "username": username,
    "password": password,
    "timeout_seconds": timeout,
  }


def get_omc_client(db: Session) -> Optional[OmcClient]:
  cfg = load_omc_config(db)
  if not cfg:
    return None
  return OmcClient(
    base_url=cfg["base_url"],
    username=cfg.get("username"),
    password=cfg.get("password"),
    timeout_seconds=cfg.get("timeout_seconds", 10),
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
