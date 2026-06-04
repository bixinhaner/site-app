"""
OMC 设备库存快照同步。

当前生产可用的批量入口是 REST:
  POST /northboundApi/v1/device/query

该接口不能证明设备“曾激活”，但可用 connection_status/offlineDays
为 ever_online 补漏，减少逐 SN 调 /enodeb/infos/status/{sn} 的请求量。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set

from sqlalchemy.orm import Session

from app.services.omc_client import is_success_status_payload
from app.services.omc_state import upsert_omc_device_state
from app.utils.timezone import to_utc_iso


DEFAULT_INVENTORY_SNAPSHOT_ENABLED = True
DEFAULT_INVENTORY_SNAPSHOT_INTERVAL_SECONDS = 300
DEFAULT_INVENTORY_DEVICE_GROUP_IDS: List[int] = []
DEFAULT_INVENTORY_PAGE_SIZE = 1000
DEFAULT_OFFLINE_DAYS_MARKS_EVER_ONLINE = True

MIN_INVENTORY_SNAPSHOT_INTERVAL_SECONDS = 60
MAX_INVENTORY_SNAPSHOT_INTERVAL_SECONDS = 86400
MIN_INVENTORY_PAGE_SIZE = 1
MAX_INVENTORY_PAGE_SIZE = 5000
MAX_INVENTORY_DEVICE_GROUPS = 200


def _parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _parse_group_ids(value: Any) -> List[int]:
    if value is None or value == "":
        return []

    raw_items: List[Any]
    if isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = str(value).replace("，", ",").split(",")

    group_ids: List[int] = []
    seen: Set[int] = set()
    for item in raw_items:
        try:
            group_id = int(str(item).strip())
        except (TypeError, ValueError):
            continue
        if group_id <= 0 or group_id in seen:
            continue
        group_ids.append(group_id)
        seen.add(group_id)
        if len(group_ids) >= MAX_INVENTORY_DEVICE_GROUPS:
            break

    return group_ids


def normalize_inventory_snapshot_config(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = data or {}
    return {
        "inventory_snapshot_enabled": _parse_bool(
            data.get("inventory_snapshot_enabled"),
            DEFAULT_INVENTORY_SNAPSHOT_ENABLED,
        ),
        "inventory_snapshot_interval_seconds": _clamp_int(
            data.get("inventory_snapshot_interval_seconds"),
            DEFAULT_INVENTORY_SNAPSHOT_INTERVAL_SECONDS,
            MIN_INVENTORY_SNAPSHOT_INTERVAL_SECONDS,
            MAX_INVENTORY_SNAPSHOT_INTERVAL_SECONDS,
        ),
        "inventory_device_group_ids": _parse_group_ids(data.get("inventory_device_group_ids")),
        "inventory_page_size": _clamp_int(
            data.get("inventory_page_size"),
            DEFAULT_INVENTORY_PAGE_SIZE,
            MIN_INVENTORY_PAGE_SIZE,
            MAX_INVENTORY_PAGE_SIZE,
        ),
        "offline_days_marks_ever_online": _parse_bool(
            data.get("offline_days_marks_ever_online"),
            DEFAULT_OFFLINE_DAYS_MARKS_EVER_ONLINE,
        ),
    }


def _parse_offline_days(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        parsed = int(float(text))
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _normalize_device_query_row(
    row: Dict[str, Any],
    *,
    observed_at: datetime,
    offline_days_marks_ever_online: bool,
) -> Optional[Dict[str, Any]]:
    sn = str(
        row.get("serial_number")
        or row.get("sn")
        or row.get("device_sn")
        or ""
    ).strip()
    if not sn:
        return None

    connection_status = str(row.get("connection_status") or "").strip().lower()
    offline_days = _parse_offline_days(row.get("offlineDays"))
    online_raw: Optional[bool] = None
    online_evidence_at: Optional[datetime] = None
    evidence_source: Optional[str] = None

    if connection_status == "on":
        online_raw = True
        online_evidence_at = observed_at
        evidence_source = "connection_status"
    elif connection_status == "off":
        online_raw = False
        if offline_days_marks_ever_online and offline_days is not None:
            online_evidence_at = observed_at - timedelta(days=offline_days)
            evidence_source = "offlineDays"

    status_payload = {
        **row,
        "_snapshot": {
            "source": "device_query",
            "observed_at": to_utc_iso(observed_at),
            "online_evidence_at": to_utc_iso(online_evidence_at) if online_evidence_at else None,
            "online_evidence_source": evidence_source,
            "offline_days_marks_ever_online": bool(offline_days_marks_ever_online),
        },
    }

    return {
        "sn": sn,
        "online_raw": online_raw,
        "online_evidence_at": online_evidence_at,
        "status_payload": status_payload,
        "connection_status": connection_status,
        "offline_days": offline_days,
    }


def sync_from_inventory_snapshot(
    db: Session,
    rows: Iterable[Dict],
    *,
    source_label: str = "inventory_ftp",
) -> None:
    """
    从库存快照（例如 CSV 行列表）中同步设备状态到 OmcDeviceState。

    每一行预期包含:
      - sn: 设备序列号
      - online: "1"/"0" 或布尔
      - active: "1"/"0" 或布尔
    """
    for row in rows:
        sn = (row.get("sn") or "").strip()
        if not sn:
            continue

        online_val = row.get("online")
        active_val = row.get("active")

        online_raw = None if online_val is None else str(online_val).strip() == "1"
        activated_raw = None if active_val is None else str(active_val).strip() == "1"

        if online_raw is None and activated_raw is None:
            continue

        upsert_omc_device_state(
            db=db,
            sn=sn,
            online_raw=online_raw,
            activated_raw=activated_raw,
            source=source_label,
            status_payload=row,
        )


def sync_device_query_snapshot(
    db: Session,
    rows: Iterable[Dict[str, Any]],
    *,
    observed_at: Optional[datetime] = None,
    source_label: str = "inventory_rest",
    offline_days_marks_ever_online: bool = DEFAULT_OFFLINE_DAYS_MARKS_EVER_ONLINE,
) -> Dict[str, Any]:
    observed_at = observed_at or datetime.utcnow()
    covered_sns: Set[str] = set()
    stats: Dict[str, Any] = {
        "total_rows": 0,
        "updated": 0,
        "invalid_rows": 0,
        "online_raw_true": 0,
        "online_raw_false": 0,
        "offline_with_evidence": 0,
        "newly_online": 0,
        "covered_sns": covered_sns,
    }

    for row in rows:
        stats["total_rows"] += 1
        normalized = _normalize_device_query_row(
            row,
            observed_at=observed_at,
            offline_days_marks_ever_online=offline_days_marks_ever_online,
        )
        if not normalized:
            stats["invalid_rows"] += 1
            continue

        sn = normalized["sn"]
        online_raw = normalized["online_raw"]
        online_evidence_at = normalized["online_evidence_at"]
        covered_sns.add(sn)

        if online_raw is True:
            stats["online_raw_true"] += 1
        elif online_raw is False:
            stats["online_raw_false"] += 1
        if online_raw is False and online_evidence_at is not None:
            stats["offline_with_evidence"] += 1

        _, newly_online, _ = upsert_omc_device_state(
            db=db,
            sn=sn,
            online_raw=online_raw,
            activated_raw=None,
            source=source_label,
            status_payload=normalized["status_payload"],
            observed_at=observed_at,
            online_evidence_at=online_evidence_at,
        )
        stats["updated"] += 1
        if newly_online:
            stats["newly_online"] += 1

    return stats


def _extract_device_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if not isinstance(data, dict):
        return []

    rows = (
        data.get("rows")
        or data.get("list")
        or data.get("items")
        or data.get("records")
        or []
    )
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _extract_total(payload: Dict[str, Any]) -> Optional[int]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return None
    for key in ("total", "total_count", "totalCount"):
        value = data.get(key)
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _coerce_group_id(value: Any) -> Optional[int]:
    try:
        group_id = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return group_id if group_id > 0 else None


def _extract_group_children(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("children", "child", "childs", "groups", "list"):
        children = node.get(key)
        if isinstance(children, list):
            return [child for child in children if isinstance(child, dict)]
    return []


def _extract_group_name(node: Dict[str, Any], group_id: int) -> str:
    raw = (
        node.get("group_name")
        or node.get("groupName")
        or node.get("name")
        or node.get("label")
        or node.get("text")
    )
    name = str(raw or "").strip()
    return name or f"Group {group_id}"


def _extract_group_leaf(node: Dict[str, Any], children: List[Dict[str, Any]]) -> bool:
    for key in ("leaf", "is_leaf", "isLeaf"):
        if key not in node:
            continue
        value = node.get(key)
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y"}:
            return True
        if text in {"0", "false", "no", "n"}:
            return False
    return not children


def flatten_device_groups(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    将 /device/group 的树形或列表响应摊平成可查询的 group 列表。
    """
    if not is_success_status_payload(payload):
        return []

    data = payload.get("data") if isinstance(payload, dict) else None
    roots: List[Dict[str, Any]]
    if isinstance(data, list):
        roots = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        rows = data.get("rows")
        if isinstance(rows, list):
            roots = [item for item in rows if isinstance(item, dict)]
        else:
            roots = [data]
    else:
        return []

    result: List[Dict[str, Any]] = []
    seen: Set[int] = set()

    def walk(node: Dict[str, Any], parent_id: Optional[int], parent_path: str) -> None:
        group_id = _coerce_group_id(
            node.get("id")
            or node.get("group_id")
            or node.get("groupId")
            or node.get("value")
        )
        children = _extract_group_children(node)
        if group_id is None:
            for child in children:
                walk(child, parent_id, parent_path)
            return

        name = _extract_group_name(node, group_id)
        path = f"{parent_path}/{name}" if parent_path else name
        leaf = _extract_group_leaf(node, children)
        if group_id not in seen:
            result.append(
                {
                    "id": group_id,
                    "name": name,
                    "parent_id": parent_id,
                    "path": path,
                    "leaf": leaf,
                }
            )
            seen.add(group_id)

        for child in children:
            walk(child, group_id, path)

    for root in roots:
        walk(root, None, "")

    return result[:MAX_INVENTORY_DEVICE_GROUPS]


def fetch_device_groups(client: Any) -> Dict[str, Any]:
    try:
        payload = client.get_device_groups()
    except Exception as exc:
        return {
            "groups": [],
            "errors": [{"error": str(exc)}],
            "payload": None,
        }

    if not is_success_status_payload(payload):
        return {
            "groups": [],
            "errors": [{"payload": payload}],
            "payload": payload,
        }

    return {
        "groups": flatten_device_groups(payload),
        "errors": [],
        "payload": payload,
    }


def fetch_device_query_snapshot(
    client: Any,
    *,
    group_ids: Iterable[int],
    page_size: int,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    seen_sns: Set[str] = set()
    request_count = 0
    selected_group_ids = list(group_ids or [])
    auto_discovered = not bool(selected_group_ids)
    auto_discovered_groups: List[Dict[str, Any]] = []

    if auto_discovered:
        group_stats = fetch_device_groups(client)
        errors.extend(group_stats.get("errors") or [])
        auto_discovered_groups = list(group_stats.get("groups") or [])
        queryable_groups = [
            group for group in auto_discovered_groups
            if group.get("id") and bool(group.get("leaf"))
        ]
        skipped_non_leaf_groups = [
            group for group in auto_discovered_groups
            if group.get("id") and not bool(group.get("leaf"))
        ]
        selected_group_ids = [int(group["id"]) for group in queryable_groups]
        if not selected_group_ids:
            return {
                "rows": rows,
                "errors": errors or [{"error": "OMC 未返回可查询的设备分组"}],
                "requests": request_count,
                "covered_sns": seen_sns,
                "group_ids": [],
                "auto_discovered": auto_discovered,
                "auto_discovered_groups": auto_discovered_groups,
                "skipped_non_leaf_groups": skipped_non_leaf_groups,
            }
    else:
        skipped_non_leaf_groups = []

    for group_id in selected_group_ids:
        page_no = 0
        group_total: Optional[int] = None
        group_row_count = 0
        while page_no < 1000:
            request_count += 1
            try:
                payload = client.query_devices(
                    group_id=group_id,
                    page_size=page_size,
                    page_no=page_no,
                )
            except Exception as exc:
                errors.append({"group_id": group_id, "page_no": page_no, "error": str(exc)})
                break

            if not is_success_status_payload(payload):
                errors.append(
                    {
                        "group_id": group_id,
                        "page_no": page_no,
                        "payload": payload,
                    }
                )
                break

            page_rows = _extract_device_rows(payload)
            total = _extract_total(payload)
            if total is not None:
                group_total = total

            new_row_count = 0
            for row in page_rows:
                group_row_count += 1
                sn = str(row.get("serial_number") or row.get("sn") or "").strip()
                if sn and sn in seen_sns:
                    continue
                if sn:
                    seen_sns.add(sn)
                rows.append(row)
                new_row_count += 1

            if not page_rows:
                break
            if page_no > 0 and new_row_count == 0:
                break
            if group_total is not None and group_row_count >= group_total:
                break
            if group_total is None and len(page_rows) < page_size:
                break
            page_no += 1

    return {
        "rows": rows,
        "errors": errors,
        "requests": request_count,
        "covered_sns": seen_sns,
        "group_ids": selected_group_ids,
        "auto_discovered": auto_discovered,
        "auto_discovered_groups": auto_discovered_groups,
        "skipped_non_leaf_groups": skipped_non_leaf_groups,
    }


def sync_device_query_snapshot_from_omc(
    db: Session,
    client: Any,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = normalize_inventory_snapshot_config(config)
    observed_at = datetime.utcnow()
    fetch_stats = fetch_device_query_snapshot(
        client,
        group_ids=cfg["inventory_device_group_ids"],
        page_size=cfg["inventory_page_size"],
    )
    sync_stats = sync_device_query_snapshot(
        db,
        fetch_stats["rows"],
        observed_at=observed_at,
        offline_days_marks_ever_online=cfg["offline_days_marks_ever_online"],
    )
    covered_sns = set(sync_stats.get("covered_sns") or set())
    return {
        "enabled": bool(cfg["inventory_snapshot_enabled"]),
        "observed_at": to_utc_iso(observed_at),
        "group_ids": list(fetch_stats.get("group_ids") or []),
        "auto_discovered_groups": list(fetch_stats.get("auto_discovered_groups") or []),
        "auto_discovered": bool(fetch_stats.get("auto_discovered")),
        "skipped_non_leaf_groups": list(fetch_stats.get("skipped_non_leaf_groups") or []),
        "page_size": int(cfg["inventory_page_size"]),
        "requests": int(fetch_stats["requests"]),
        "errors": list(fetch_stats["errors"]),
        "snapshot_filter_usable": bool(covered_sns),
        **sync_stats,
    }
