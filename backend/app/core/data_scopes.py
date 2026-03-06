from typing import Dict, Iterable, List, Optional


BUILTIN_DATA_SCOPE_DEFINITIONS = [
    {
        "resource": "sites",
        "name": "站点数据范围",
        "description": "控制站点列表和站点详情能看到哪些站点。",
        "options": [
            {"code": "all", "name": "全部站点", "description": "可查看全部站点。"},
            {
                "code": "related_work_orders",
                "name": "关联工单站点",
                "description": "仅可查看自己被分配工单关联的站点。",
            },
        ],
    },
    {
        "resource": "work_orders",
        "name": "工单数据范围",
        "description": "控制工单列表、详情和大部分工单操作的可见范围。",
        "options": [
            {"code": "all", "name": "全部工单", "description": "可查看和处理全部工单。"},
            {"code": "assigned", "name": "仅自己工单", "description": "仅可查看和处理分配给自己的工单。"},
            {
                "code": "assigned_survey_only",
                "name": "仅自己勘察工单",
                "description": "仅可查看和处理分配给自己的勘察类工单。",
            },
        ],
    },
    {
        "resource": "inspections",
        "name": "检查数据范围",
        "description": "控制检查列表、详情和检查执行过程的可见范围。",
        "options": [
            {"code": "all", "name": "全部检查", "description": "可查看和处理全部检查。"},
            {"code": "assigned", "name": "仅自己检查", "description": "仅可查看和处理分配给自己的检查。"},
            {
                "code": "assigned_survey_only",
                "name": "仅自己勘察检查",
                "description": "仅可查看和处理分配给自己的勘察类检查。",
            },
        ],
    },
]


DATA_SCOPE_DEFINITION_BY_RESOURCE: Dict[str, Dict[str, object]] = {
    str(item["resource"]): item for item in BUILTIN_DATA_SCOPE_DEFINITIONS
}

BUILTIN_ROLE_DATA_SCOPE_TEMPLATE: Dict[str, Dict[str, str]] = {
    "admin": {
        "sites": "all",
        "work_orders": "all",
        "inspections": "all",
    },
    "manager": {
        "sites": "all",
        "work_orders": "all",
        "inspections": "all",
    },
    "warehouse_manager": {
        "sites": "all",
        "work_orders": "all",
        "inspections": "all",
    },
    "planner": {
        "sites": "all",
        "work_orders": "all",
        "inspections": "all",
    },
    "reviewer": {
        "sites": "all",
        "work_orders": "all",
        "inspections": "all",
    },
    "inspector": {
        "sites": "related_work_orders",
        "work_orders": "assigned",
        "inspections": "assigned",
    },
    "surveyor": {
        "sites": "related_work_orders",
        "work_orders": "assigned_survey_only",
        "inspections": "assigned_survey_only",
    },
    "user": {
        "sites": "all",
        "work_orders": "all",
        "inspections": "all",
    },
}


def list_data_scope_resources() -> List[str]:
    return [str(item["resource"]) for item in BUILTIN_DATA_SCOPE_DEFINITIONS]


def get_data_scope_definition(resource: str) -> Optional[Dict[str, object]]:
    return DATA_SCOPE_DEFINITION_BY_RESOURCE.get(str(resource or "").strip())


def get_data_scope_option_codes(resource: str) -> List[str]:
    definition = get_data_scope_definition(resource)
    if not definition:
        return []
    return [
        str(item.get("code") or "").strip()
        for item in definition.get("options", [])
        if str(item.get("code") or "").strip()
    ]


def is_valid_data_scope(resource: str, scope_code: str) -> bool:
    target_resource = str(resource or "").strip()
    target_scope = str(scope_code or "").strip()
    if not target_resource or not target_scope:
        return False
    return target_scope in set(get_data_scope_option_codes(target_resource))


def normalize_data_scope_mapping(raw_mapping: Optional[Dict[str, str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for resource, scope_code in (raw_mapping or {}).items():
        resource_code = str(resource or "").strip()
        normalized_scope = str(scope_code or "").strip()
        if not resource_code or not normalized_scope:
            continue
        if not is_valid_data_scope(resource_code, normalized_scope):
            raise ValueError(f"不支持的数据范围: {resource_code}={normalized_scope}")
        out[resource_code] = normalized_scope
    return out


def build_builtin_role_data_scope_mapping(role_code: str) -> Dict[str, str]:
    code = str(role_code or "").strip()
    return dict(BUILTIN_ROLE_DATA_SCOPE_TEMPLATE.get(code, {}))


def build_default_data_scope_mapping() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for definition in BUILTIN_DATA_SCOPE_DEFINITIONS:
        resource = str(definition["resource"])
        option_codes = get_data_scope_option_codes(resource)
        if option_codes:
            out[resource] = option_codes[0]
    return out


def summarize_data_scope_modules(mapping: Optional[Dict[str, str]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for resource, scope_code in sorted((mapping or {}).items()):
        out.setdefault("data_scopes", []).append(f"{resource}:{scope_code}")
    return out


def merge_data_scope_mapping(base: Optional[Dict[str, str]], overlay: Optional[Dict[str, str]]) -> Dict[str, str]:
    out = dict(base or {})
    for resource, scope_code in (overlay or {}).items():
        resource_code = str(resource or "").strip()
        normalized_scope = str(scope_code or "").strip()
        if not resource_code or not normalized_scope:
            continue
        out[resource_code] = normalized_scope
    return out


def has_any_limited_data_scope(mapping: Optional[Dict[str, str]], resources: Iterable[str]) -> bool:
    for resource in resources or []:
        resource_code = str(resource or "").strip()
        scope_code = str((mapping or {}).get(resource_code) or "").strip()
        if scope_code and scope_code != "all":
            return True
    return False
