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

LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY = 'deny'
LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK = 'allow_with_watermark'
LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITHOUT_WATERMARK = 'allow_without_watermark'
SUPPORTED_LOCAL_UPLOAD_WITHOUT_GEO_POLICIES = (
    LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY,
    LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK,
    LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITHOUT_WATERMARK,
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


class LocalUploadWithoutGeoPolicyRule(BaseModel):
    default: str = LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY
    per_role: Dict[str, str] = Field(default_factory=dict)
    per_user: Dict[str, str] = Field(default_factory=dict)


class WorkOrderExecutionSettingsPayload(BaseModel):
    enabled: BoolRule = Field(default_factory=lambda: BoolRule(default=False))
    allow_photo_upload: BoolRule = Field(default_factory=lambda: BoolRule(default=True))
    allow_device_binding: BoolRule = Field(default_factory=lambda: BoolRule(default=True))
    allow_submit: BoolRule = Field(default_factory=lambda: BoolRule(default=True))
    allow_recall: BoolRule = Field(default_factory=lambda: BoolRule(default=True))
    local_upload_without_geo_policy: LocalUploadWithoutGeoPolicyRule = Field(
        default_factory=LocalUploadWithoutGeoPolicyRule,
    )
    # 兼容字段：由 local_upload_without_geo_policy 自动派生，不再作为 Web 执行端主配置。
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
    local_upload_without_geo_policy: str = LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY
    allow_local_upload_without_geo: bool = False
    visible_work_order_types: List[str] = Field(default_factory=list)
    editable_work_order_types: List[str] = Field(default_factory=list)
