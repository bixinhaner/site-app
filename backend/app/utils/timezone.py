from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def _get_local_timezone():
    """
    获取服务器本地时区。

    说明：
    - 仅用于将“以本地时间写入”的历史数据转换为 UTC。
    - 对于未来新增逻辑，优先在写入时就使用 UTC（datetime.utcnow() 或 tz=UTC）。
    """
    return datetime.now().astimezone().tzinfo or timezone.utc


LOCAL_TZ = _get_local_timezone()


def to_utc_iso(dt: Optional[datetime], assume_local: bool = False) -> Optional[str]:
    """
    将 datetime 统一转换为 UTC ISO8601 字符串（以 Z 结尾）。

    参数:
        dt: 原始 datetime（可能为 naive）
        assume_local:
            - False: 将 naive datetime 视为已经是 UTC 时间
            - True: 将 naive datetime 视为服务器本地时间，再换算到 UTC

    返回:
        形如 '2025-01-01T12:00:00Z' 的字符串；若 dt 为 None，则返回 None
    """
    if dt is None:
        return None

    # 已带时区信息：统一转换为 UTC
    if dt.tzinfo is not None:
        aware = dt.astimezone(timezone.utc)
    else:
        if assume_local:
            aware = dt.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
        else:
            # 约定：不带 tzinfo 的时间视为 UTC
            aware = dt.replace(tzinfo=timezone.utc)

    return aware.isoformat().replace("+00:00", "Z")

