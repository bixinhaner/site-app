from __future__ import annotations

import copy
import json
import math
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.inspection import InspectionPhoto, SiteInspection
from app.models.site import Site
from app.utils.timezone import to_utc_iso


def _to_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _is_valid_coordinate_pair(latitude: Any, longitude: Any) -> bool:
    lat = _to_float(latitude)
    lon = _to_float(longitude)
    return lat is not None and lon is not None and not (lat == 0 and lon == 0)


def calculate_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6371000
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_m * c


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return copy.deepcopy(parsed) if isinstance(parsed, dict) else {}
    return {}


def _format_planned_coordinates(latitude: float, longitude: float) -> str:
    return f"{latitude:.6f}, {longitude:.6f}"


def build_uploaded_location_compare(
    *,
    planned_latitude: Any = None,
    planned_longitude: Any = None,
    distance_to_plan_m: Any = None,
    distance_threshold_m: Any = None,
    distance_exceeded: Optional[bool] = None,
    plan_coordinate_missing: Optional[bool] = None,
    distance_compare_enabled: Optional[bool] = None,
    distance_exceed_block_upload: Optional[bool] = None,
) -> Dict[str, Any]:
    location_compare: Dict[str, Any] = {}
    plan_lat = _to_float(planned_latitude)
    plan_lon = _to_float(planned_longitude)

    if plan_lat is not None and plan_lon is not None:
        location_compare["planned_coordinates"] = _format_planned_coordinates(plan_lat, plan_lon)
        location_compare["planned_latitude"] = plan_lat
        location_compare["planned_longitude"] = plan_lon

    distance = _to_float(distance_to_plan_m)
    if distance is not None:
        location_compare["distance_to_plan_m"] = round(distance, 2)

    threshold = _to_float(distance_threshold_m)
    if threshold is not None:
        location_compare["distance_threshold_m"] = round(threshold, 2)

    if distance_exceeded is not None:
        location_compare["distance_exceeded"] = bool(distance_exceeded)
    if plan_coordinate_missing is not None:
        location_compare["plan_coordinate_missing"] = bool(plan_coordinate_missing)
    if distance_compare_enabled is not None:
        location_compare["distance_compare_enabled"] = bool(distance_compare_enabled)
    if distance_exceed_block_upload is not None:
        location_compare["distance_exceed_block_upload"] = bool(distance_exceed_block_upload)

    return location_compare


def _refresh_compare_payload(
    compare: Dict[str, Any],
    *,
    actual_latitude: Any,
    actual_longitude: Any,
    planned_latitude: Any,
    planned_longitude: Any,
    reason: str,
) -> Dict[str, Any]:
    updated = copy.deepcopy(compare)
    refreshed_at = to_utc_iso(datetime.utcnow())

    plan_lat = _to_float(planned_latitude)
    plan_lon = _to_float(planned_longitude)
    actual_lat = _to_float(actual_latitude)
    actual_lon = _to_float(actual_longitude)
    has_plan = _is_valid_coordinate_pair(plan_lat, plan_lon)
    has_actual = _is_valid_coordinate_pair(actual_lat, actual_lon)

    updated["planned_coordinate_source"] = "current_site"
    updated["distance_compare_refreshed_at"] = refreshed_at
    updated["distance_compare_refresh_reason"] = reason

    if not has_plan:
        updated["planned_coordinates"] = None
        updated["planned_latitude"] = None
        updated["planned_longitude"] = None
        updated["distance_to_plan_m"] = None
        updated["distance_exceeded"] = False
        updated["plan_coordinate_missing"] = True
        return updated

    updated["planned_coordinates"] = _format_planned_coordinates(plan_lat, plan_lon)
    updated["planned_latitude"] = plan_lat
    updated["planned_longitude"] = plan_lon
    updated["plan_coordinate_missing"] = False

    if not has_actual:
        updated["distance_to_plan_m"] = None
        updated["distance_exceeded"] = False
        return updated

    distance_m = round(calculate_distance_meters(actual_lat, actual_lon, plan_lat, plan_lon), 2)
    updated["distance_to_plan_m"] = distance_m

    threshold = _to_float(updated.get("distance_threshold_m"))
    if threshold is None:
        threshold = _to_float(updated.get("threshold_m"))
    if threshold is not None and threshold > 0:
        updated["distance_threshold_m"] = round(threshold, 2)
        updated["distance_exceeded"] = distance_m > threshold
    else:
        updated["distance_exceeded"] = False

    return updated


def refresh_site_photo_location_compare_for_site(
    db: Session,
    site: Site,
    *,
    reason: str = "site_coordinate_changed",
) -> Dict[str, int]:
    photos = (
        db.query(InspectionPhoto)
        .join(SiteInspection, InspectionPhoto.inspection_id == SiteInspection.id)
        .filter(SiteInspection.site_id == site.id)
        .all()
    )

    matched_count = 0
    updated_count = 0
    skipped_count = 0

    for photo in photos:
        watermark_data = _as_dict(photo.watermark_data)
        compare = _as_dict(watermark_data.get("location_compare"))
        if not compare:
            skipped_count += 1
            continue

        matched_count += 1
        refreshed_compare = _refresh_compare_payload(
            compare,
            actual_latitude=photo.latitude,
            actual_longitude=photo.longitude,
            planned_latitude=site.latitude,
            planned_longitude=site.longitude,
            reason=reason,
        )
        if refreshed_compare == compare:
            continue

        watermark_data["location_compare"] = refreshed_compare
        photo.watermark_data = watermark_data
        flag_modified(photo, "watermark_data")
        updated_count += 1

    return {
        "photo_count": len(photos),
        "matched_count": matched_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
    }
