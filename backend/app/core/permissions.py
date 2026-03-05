from typing import Dict, Iterable, List


BUILTIN_ROLE_DEFINITIONS = [
    {"code": "admin", "name": "系统管理员", "description": "超级管理员，默认绕过全部权限校验", "is_system": True},
    {"code": "manager", "name": "项目经理", "description": "项目经理（可按权限点授权）", "is_system": True},
    {"code": "warehouse_manager", "name": "仓库管理员", "description": "仓储流程管理角色", "is_system": True},
    {"code": "planner", "name": "规划人员", "description": "站点规划角色", "is_system": True},
    {"code": "reviewer", "name": "审核人员", "description": "工单审核角色", "is_system": True},
    {"code": "inspector", "name": "现场工程师", "description": "现场执行角色", "is_system": True},
    {"code": "surveyor", "name": "勘察人员", "description": "勘察执行角色", "is_system": True},
    {"code": "user", "name": "普通用户", "description": "基础角色", "is_system": True},
]


# 说明：
# - code 采用 module:resource:action 三段式；
# - web-admin 页面、按钮、后端接口统一复用同一权限码，避免双份配置。
BUILTIN_PERMISSION_DEFINITIONS = [
    {"code": "authz:manage:all", "name": "权限系统管理", "module": "authz"},
    {"code": "dashboard:view:read", "name": "仪表盘查看", "module": "dashboard"},
    {"code": "users:list:read", "name": "用户列表查看", "module": "users"},
    {"code": "users:profile:read", "name": "用户详情查看", "module": "users"},
    {"code": "users:create:write", "name": "创建用户", "module": "users"},
    {"code": "users:update:write", "name": "编辑用户", "module": "users"},
    {"code": "users:delete:write", "name": "禁用/删除用户", "module": "users"},
    {"code": "users:password:write", "name": "重置密码", "module": "users"},
    {"code": "users:batch:write", "name": "用户批量操作", "module": "users"},
    {"code": "sites:list:read", "name": "站点列表查看", "module": "sites"},
    {"code": "sites:detail:read", "name": "站点详情查看", "module": "sites"},
    {"code": "sites:create:write", "name": "站点创建", "module": "sites"},
    {"code": "sites:update:write", "name": "站点编辑", "module": "sites"},
    {"code": "sites:survey-stage:write", "name": "勘察阶段批量设置", "module": "sites"},
    {"code": "sites:lld:read", "name": "LLD 规划查看", "module": "sites"},
    {"code": "sites:lld:write", "name": "LLD 规划编辑", "module": "sites"},
    {"code": "inspection:template:read", "name": "检查模板查看", "module": "inspection"},
    {"code": "inspection:template:write", "name": "检查模板编辑", "module": "inspection"},
    {"code": "workorder:list:read", "name": "工单列表查看", "module": "workorder"},
    {"code": "workorder:create:write", "name": "工单创建", "module": "workorder"},
    {"code": "workorder:update:write", "name": "工单编辑", "module": "workorder"},
    {"code": "workorder:delete:write", "name": "工单删除", "module": "workorder"},
    {"code": "workorder:dispatch:write", "name": "工单派发/改派", "module": "workorder"},
    {"code": "workorder:review:write", "name": "工单审核", "module": "workorder"},
    {"code": "workorder:batch:write", "name": "工单批量操作", "module": "workorder"},
    {"code": "inventory:equipment:read", "name": "设备类型查看", "module": "inventory"},
    {"code": "inventory:equipment:write", "name": "设备类型管理", "module": "inventory"},
    {"code": "inventory:package:read", "name": "设备套装查看", "module": "inventory"},
    {"code": "inventory:package:write", "name": "设备套装管理", "module": "inventory"},
    {"code": "inventory:stock:read", "name": "库存查看", "module": "inventory"},
    {"code": "inventory:stock-in:write", "name": "入库操作", "module": "inventory"},
    {"code": "inventory:stock-out:write", "name": "出库操作", "module": "inventory"},
    {"code": "inventory:history:read", "name": "出入库记录查看", "module": "inventory"},
    {"code": "inventory:flow-settings:write", "name": "库存流程设置", "module": "inventory"},
    {"code": "inventory:warehouse:read", "name": "仓库查看", "module": "inventory"},
    {"code": "inventory:warehouse:write", "name": "仓库管理", "module": "inventory"},
    {"code": "inventory:material-request:read", "name": "物料申请查看", "module": "inventory"},
    {"code": "inventory:material-request:write", "name": "物料申请处理", "module": "inventory"},
    {"code": "inventory:issue-draft:read", "name": "领料单查看", "module": "inventory"},
    {"code": "inventory:issue-draft:write", "name": "领料单确认", "module": "inventory"},
    {"code": "inventory:return:read", "name": "退库查看", "module": "inventory"},
    {"code": "inventory:return:write", "name": "退库申请/处理", "module": "inventory"},
    {"code": "inventory:user-ownership:read", "name": "人员领用台账查看", "module": "inventory"},
    {"code": "system:mobile-settings:read", "name": "移动端配置查看", "module": "system"},
    {"code": "system:mobile-settings:write", "name": "移动端配置管理", "module": "system"},
    {"code": "system:geocode-cache:read", "name": "逆地理缓存查看", "module": "system"},
    {"code": "system:geocode-cache:write", "name": "逆地理缓存管理", "module": "system"},
    {"code": "system:logs:read", "name": "系统日志查看", "module": "system"},
    {"code": "system:backup:write", "name": "系统备份管理", "module": "system"},
    {"code": "system:app-version:read", "name": "App版本查看", "module": "system"},
    {"code": "system:app-version:write", "name": "App版本管理", "module": "system"},
    {"code": "system:ai:read", "name": "AI 管理查看", "module": "system"},
    {"code": "system:ai:write", "name": "AI 管理配置", "module": "system"},
]


BUILTIN_ROLE_PERMISSION_TEMPLATE: Dict[str, List[str]] = {
    # admin 通过绕过机制获得全部权限；此处仍授予 authz 管理权限便于显式展示
    "admin": [p["code"] for p in BUILTIN_PERMISSION_DEFINITIONS],
    "manager": [
        "dashboard:view:read",
        "users:list:read",
        "users:profile:read",
        "users:update:write",
        "sites:list:read",
        "sites:detail:read",
        "sites:create:write",
        "sites:update:write",
        "sites:survey-stage:write",
        "sites:lld:read",
        "sites:lld:write",
        "inspection:template:read",
        "inspection:template:write",
        "workorder:list:read",
        "workorder:create:write",
        "workorder:update:write",
        "workorder:delete:write",
        "workorder:dispatch:write",
        "workorder:review:write",
        "workorder:batch:write",
        "inventory:equipment:read",
        "inventory:equipment:write",
        "inventory:package:read",
        "inventory:package:write",
        "inventory:stock:read",
        "inventory:stock-in:write",
        "inventory:stock-out:write",
        "inventory:history:read",
        "inventory:flow-settings:write",
        "inventory:warehouse:read",
        "inventory:material-request:read",
        "inventory:material-request:write",
        "inventory:issue-draft:read",
        "inventory:issue-draft:write",
        "inventory:return:read",
        "inventory:return:write",
        "inventory:user-ownership:read",
        "system:mobile-settings:read",
        "system:mobile-settings:write",
        "system:geocode-cache:read",
        "system:logs:read",
        "system:app-version:read",
        "system:ai:read",
    ],
    "warehouse_manager": [
        "inventory:equipment:read",
        "inventory:equipment:write",
        "inventory:package:read",
        "inventory:package:write",
        "inventory:stock:read",
        "inventory:stock-in:write",
        "inventory:stock-out:write",
        "inventory:history:read",
        "inventory:flow-settings:write",
        "inventory:warehouse:read",
        "inventory:material-request:read",
        "inventory:material-request:write",
        "inventory:issue-draft:read",
        "inventory:issue-draft:write",
        "inventory:return:read",
        "inventory:return:write",
        "inventory:user-ownership:read",
    ],
    "planner": [
        "sites:list:read",
        "sites:detail:read",
        "sites:lld:read",
        "sites:lld:write",
    ],
    "reviewer": [
        "workorder:list:read",
        "workorder:review:write",
        "inspection:template:read",
        "system:ai:read",
    ],
    "inspector": [
        "dashboard:view:read",
        "sites:list:read",
        "sites:detail:read",
        "workorder:list:read",
        "workorder:create:write",
        "inventory:stock:read",
        "inventory:history:read",
        "inventory:material-request:read",
        "inventory:material-request:write",
        "inventory:return:read",
        "inventory:return:write",
    ],
    "surveyor": [
        "dashboard:view:read",
        "sites:list:read",
        "sites:detail:read",
        "workorder:list:read",
    ],
    "user": [
        "dashboard:view:read",
        "sites:list:read",
        "sites:detail:read",
        "workorder:list:read",
    ],
}


def permission_matches(permission_code: str, granted_codes: Iterable[str]) -> bool:
    target = str(permission_code or "").strip()
    if not target:
        return False
    for raw in granted_codes or []:
        code = str(raw or "").strip()
        if not code:
            continue
        if code == "*" or code == target:
            return True
        if code.endswith(":*") and target.startswith(code[:-1]):
            return True
    return False
