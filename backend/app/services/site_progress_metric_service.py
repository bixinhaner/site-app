from typing import Dict

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.system_config import SystemConfig


SITE_PROGRESS_SETTINGS_KEY = "site_progress_settings"
SITE_PROGRESS_METRIC_MODE_WORKFLOW = "workflow"
SITE_PROGRESS_METRIC_MODE_DEVICE_FACT = "device_fact"
VALID_SITE_PROGRESS_METRIC_MODES = {
    SITE_PROGRESS_METRIC_MODE_WORKFLOW,
    SITE_PROGRESS_METRIC_MODE_DEVICE_FACT,
}

DEFAULT_SITE_PROGRESS_SETTINGS = {
    "metric_mode": SITE_PROGRESS_METRIC_MODE_WORKFLOW,
}


def normalize_site_progress_metric_mode(raw_mode: str | None) -> str:
    mode = str(raw_mode or "").strip().lower()
    if mode in VALID_SITE_PROGRESS_METRIC_MODES:
        return mode
    return SITE_PROGRESS_METRIC_MODE_WORKFLOW


def load_site_progress_settings(db: Session) -> Dict[str, str]:
    settings = dict(DEFAULT_SITE_PROGRESS_SETTINGS)
    row = db.query(SystemConfig).filter(SystemConfig.key == SITE_PROGRESS_SETTINGS_KEY).first()
    if not row or not isinstance(row.value, dict):
        return settings

    data = row.value or {}
    settings["metric_mode"] = normalize_site_progress_metric_mode(data.get("metric_mode"))
    return settings


def upsert_site_progress_settings(db: Session, settings_patch: Dict[str, str]) -> Dict[str, str]:
    settings = load_site_progress_settings(db)
    if "metric_mode" in settings_patch:
        settings["metric_mode"] = normalize_site_progress_metric_mode(settings_patch.get("metric_mode"))

    row = db.query(SystemConfig).filter(SystemConfig.key == SITE_PROGRESS_SETTINGS_KEY).first()
    if not row:
        row = SystemConfig(key=SITE_PROGRESS_SETTINGS_KEY, value=settings)
        db.add(row)
    else:
        row.value = settings
        flag_modified(row, "value")

    return settings


def get_site_progress_metric_mode(db: Session) -> str:
    settings = load_site_progress_settings(db)
    return normalize_site_progress_metric_mode(settings.get("metric_mode"))
