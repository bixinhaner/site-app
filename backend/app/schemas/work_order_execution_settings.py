from typing import Dict, List, Optional

from pydantic import BaseModel, Field


SUPPORTED_WEB_EXECUTION_WORK_ORDER_TYPES = (
    'site_survey',
    'opening_inspection',
    'equipment_replacement',
    'ssv',
    'maintenance',
    'power_issue',
    'transmission_issue',
    'gps_issue',
    'signal_issue',
)


class BoolRule(BaseModel):
    default: bool = False
    per_role: Dict[str, bool] = Field(default_factory=dict)
    per_user: Dict[str, bool] = Field(default_factory=dict)


class WorkOrderTypeRule(BaseModel):
    default: List[str] = Field(
        default_factory=lambda: list(SUPPORTED_WEB_EXECUTION_WORK_ORDER_TYPES),
    )
    per_role: Dict[str, List[str]] = Field(default_factory=dict)
    per_user: Dict[str, List[str]] = Field(default_factory=dict)


class WorkOrderExecutionSettingsPayload(BaseModel):
    enabled: BoolRule = Field(default_factory=lambda: BoolRule(default=False))
    allow_photo_upload: BoolRule = Field(default_factory=lambda: BoolRule(default=True))
    allow_device_binding: BoolRule = Field(default_factory=lambda: BoolRule(default=True))
    allow_submit: BoolRule = Field(default_factory=lambda: BoolRule(default=True))
    allow_recall: BoolRule = Field(default_factory=lambda: BoolRule(default=True))
    allow_local_upload_without_geo: BoolRule = Field(default_factory=lambda: BoolRule(default=False))
    visible_work_order_types: WorkOrderTypeRule = Field(default_factory=WorkOrderTypeRule)
    editable_work_order_types: WorkOrderTypeRule = Field(default_factory=WorkOrderTypeRule)
    config_version: int = 1


class WorkOrderExecutionSettingsUpdatePayload(WorkOrderExecutionSettingsPayload):
    config_version: Optional[int] = None


class EffectiveWorkOrderExecutionSettingsResponse(BaseModel):
    enabled: bool = False
    allow_photo_upload: bool = True
    allow_device_binding: bool = True
    allow_submit: bool = True
    allow_recall: bool = True
    allow_local_upload_without_geo: bool = False
    visible_work_order_types: List[str] = Field(default_factory=list)
    editable_work_order_types: List[str] = Field(default_factory=list)
