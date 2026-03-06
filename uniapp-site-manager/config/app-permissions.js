export const LEGACY_APP_ROLES = [
  'admin',
  'manager',
  'warehouse_manager',
  'planner',
  'reviewer',
  'inspector',
  'surveyor',
  'user',
]

export const APP_PERMISSION_CODES = {
  HOME_READ: 'app:home:read',
  SITES_READ: 'app:sites:read',
  WORKORDERS_READ: 'app:workorders:read',
  PROFILE_READ: 'app:profile:read',
  INSPECTION_CREATE: 'app:inspection:create',
  INSPECTION_REVIEW: 'app:inspection:review',
  MAP_READ: 'app:map:read',
  SCAN_PICKUP_USE: 'app:scan-pickup:use',
  MATERIAL_REQUEST_USE: 'app:material-request:use',
  MATERIAL_APPROVAL_USE: 'app:material-approval:use',
  ISSUE_CONFIRM_USE: 'app:issue-confirm:use',
  RETURN_REQUEST_USE: 'app:return-request:use',
  MANUAL_STOCK_OUT_USE: 'app:manual-stock-out:use',
  SITE_STATS_READ: 'app:site-stats:read',
  SETTINGS_READ: 'app:settings:read',
  DEVTOOLS_READ: 'app:devtools:read',
}

export const APP_FEATURE_RULES = {
  home: {
    allPermissions: [APP_PERMISSION_CODES.HOME_READ],
    legacyRoles: LEGACY_APP_ROLES,
  },
  sites: {
    allPermissions: [APP_PERMISSION_CODES.SITES_READ, 'sites:list:read'],
    legacyRoles: ['admin', 'manager', 'inspector', 'surveyor', 'user'],
  },
  workorders: {
    allPermissions: [APP_PERMISSION_CODES.WORKORDERS_READ, 'workorder:list:read'],
    legacyRoles: ['admin', 'manager', 'inspector', 'surveyor', 'user'],
  },
  profile: {
    allPermissions: [APP_PERMISSION_CODES.PROFILE_READ],
    legacyRoles: LEGACY_APP_ROLES,
  },
  inspection_create: {
    allPermissions: [APP_PERMISSION_CODES.INSPECTION_CREATE, 'sites:list:read'],
    legacyRoles: LEGACY_APP_ROLES,
  },
  inspection_review: {
    allPermissions: [APP_PERMISSION_CODES.INSPECTION_REVIEW, 'workorder:review:write'],
    legacyRoles: ['admin', 'manager', 'reviewer'],
  },
  map_view: {
    allPermissions: [APP_PERMISSION_CODES.MAP_READ, 'sites:list:read'],
    legacyRoles: LEGACY_APP_ROLES,
  },
  scan_pickup: {
    allPermissions: [APP_PERMISSION_CODES.SCAN_PICKUP_USE],
    legacyRoles: ['admin', 'manager', 'warehouse_manager', 'planner', 'reviewer', 'inspector', 'user'],
  },
  material_request: {
    allPermissions: [APP_PERMISSION_CODES.MATERIAL_REQUEST_USE],
    legacyRoles: ['admin', 'manager', 'warehouse_manager', 'planner', 'reviewer', 'inspector', 'user'],
  },
  material_approval: {
    allPermissions: [APP_PERMISSION_CODES.MATERIAL_APPROVAL_USE, 'inventory:material-request:write'],
    legacyRoles: ['admin', 'manager', 'warehouse_manager'],
  },
  issue_confirm: {
    allPermissions: [APP_PERMISSION_CODES.ISSUE_CONFIRM_USE, 'inventory:issue-draft:write'],
    legacyRoles: ['admin', 'manager', 'warehouse_manager'],
  },
  return_request: {
    allPermissions: [APP_PERMISSION_CODES.RETURN_REQUEST_USE],
    legacyRoles: ['admin', 'manager', 'warehouse_manager', 'planner', 'reviewer', 'inspector', 'user'],
  },
  manual_stock_out: {
    allPermissions: [APP_PERMISSION_CODES.MANUAL_STOCK_OUT_USE, 'inventory:stock-out:write'],
    legacyRoles: ['admin', 'manager'],
  },
  site_stats: {
    allPermissions: [APP_PERMISSION_CODES.SITE_STATS_READ],
    legacyRoles: ['admin', 'manager'],
  },
  settings: {
    allPermissions: [APP_PERMISSION_CODES.SETTINGS_READ, 'system:mobile-settings:read'],
    legacyRoles: ['admin', 'manager'],
  },
  devtools: {
    allPermissions: [APP_PERMISSION_CODES.DEVTOOLS_READ, 'system:mobile-settings:read'],
    legacyRoles: ['admin', 'manager'],
  },
}

export const APP_PUBLIC_ROUTES = [
  'pages/login/login',
]

export const APP_PRIMARY_ROUTE_CANDIDATES = [
  { route: 'pages/home/home', feature: 'home' },
  { route: 'pages/workorder/list', feature: 'workorders' },
  { route: 'pages/site/list', feature: 'sites' },
  { route: 'pages/profile/profile', feature: 'profile' },
]

// 页面访问统一走这张映射表，避免“入口隐藏了但 URL 还能进”。
export const APP_ROUTE_ACCESS_RULES = {
  'pages/home/home': { feature: 'home' },
  'pages/site/list': { feature: 'sites' },
  'pages/site/detail': { feature: 'sites' },
  'pages/workorder/list': { feature: 'workorders' },
  'pages/inspection/site-select': { feature: 'inspection_create' },
  'pages/inspection/detail': { features: ['inspection_create', 'inspection_review'] },
  'pages/inspection/checklist': { feature: 'inspection_create' },
  'pages/inspection/camera': { feature: 'inspection_create' },
  'pages/inspection/review': { feature: 'inspection_review' },
  'pages/profile/profile': { feature: 'profile' },
  'pages/release-notes/release-notes': { feature: 'profile' },
  'pages/stock/scan-pickup': { feature: 'scan_pickup', surveyorMessageKey: 'stock.surveyorNoPermission' },
  'pages/stock/material-requests/list': { feature: 'material_request', surveyorMessageKey: 'stock.surveyorNoPermission' },
  'pages/stock/material-requests/create': { feature: 'material_request', surveyorMessageKey: 'stock.surveyorNoPermission' },
  'pages/stock/material-requests/detail': { feature: 'material_request', surveyorMessageKey: 'stock.surveyorNoPermission' },
  'pages/stock/issue-drafts/detail': { feature: 'material_request', surveyorMessageKey: 'stock.surveyorNoPermission' },
  'pages/stock/issue-drafts/pick': { feature: 'material_request', surveyorMessageKey: 'stock.surveyorNoPermission' },
  'pages/stock/material-requests/approval-list': { feature: 'material_approval' },
  'pages/stock/material-requests/approve': { feature: 'material_approval' },
  'pages/stock/issue-drafts/confirm-list': { feature: 'issue_confirm' },
  'pages/stock/issue-drafts/confirm': { feature: 'issue_confirm' },
  'pages/stock/manual-stock-out': { feature: 'manual_stock_out' },
  'pages/stock/returns/list': { feature: 'return_request', surveyorMessageKey: 'stock.surveyorNoPermission' },
  'pages/stock/returns/create': { feature: 'return_request', surveyorMessageKey: 'stock.surveyorNoPermission' },
  'pages/map/view': { feature: 'map_view' },
  'pages/map/sites': { feature: 'map_view' },
  'pages/test/logging-test': { feature: 'devtools' },
  'pages/test-location-plugin/test-location-plugin': { feature: 'devtools' },
  'pages/test-location-builtin/test-location-builtin': { feature: 'devtools' },
  'pages/test/watermark-test': { feature: 'devtools' },
}
