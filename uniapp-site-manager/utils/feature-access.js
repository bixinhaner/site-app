import {
  APP_PRIMARY_ROUTE_CANDIDATES,
  APP_PUBLIC_ROUTES,
  APP_ROUTE_ACCESS_RULES,
} from '@/config/app-permissions.js'

export const normalizeRoutePath = (rawRoute = '') => {
  const route = String(rawRoute || '').trim().split('?')[0]
  return route.replace(/^\/+/, '')
}

export const isPublicRoute = (route = '') => {
  const normalized = normalizeRoutePath(route)
  return APP_PUBLIC_ROUTES.includes(normalized)
}

export const getRouteAccessRule = (route = '') => {
  const normalized = normalizeRoutePath(route)
  return APP_ROUTE_ACCESS_RULES[normalized] || null
}

export const resolvePermissionDeniedMessage = (userStore, t, surveyorMessageKey = '') => {
  if (surveyorMessageKey && userStore?.isSurveyor && typeof t === 'function') {
    return t(surveyorMessageKey)
  }
  if (typeof t === 'function') {
    return t('messages.permissionDenied')
  }
  return '权限不足'
}

export const resolveFirstAccessibleRoute = (
  userStore,
  fallbackRoute = '/pages/profile/profile',
) => {
  for (const item of APP_PRIMARY_ROUTE_CANDIDATES) {
    const route = normalizeRoutePath(item?.route)
    const feature = String(item?.feature || '').trim()
    if (!route) continue
    if (!feature || userStore?.can?.(feature)) {
      return `/${route}`
    }
  }
  return fallbackRoute
}

const handleAccessDenied = ({
  deniedMessage = '权限不足',
  redirectUrl = '/pages/profile/profile',
  delay = 600,
  silent = false,
}) => {
  if (!silent) {
    uni.showToast({ title: deniedMessage, icon: 'none' })
  }

  setTimeout(() => {
    const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
    const currentRoute = normalizeRoutePath(pages?.[pages.length - 1]?.route || '')
    const normalizedRedirect = normalizeRoutePath(redirectUrl)
    const targetUrl = normalizedRedirect ? `/${normalizedRedirect}` : ''

    if (Array.isArray(pages) && pages.length > 1 && currentRoute !== normalizedRedirect) {
      uni.navigateBack({ delta: 1 })
      return
    }

    if (targetUrl && currentRoute !== normalizedRedirect) {
      uni.reLaunch({ url: targetUrl })
    }
  }, delay)

  return false
}

export const guardFeatureAccess = ({
  userStore,
  feature,
  deniedMessage = '',
  redirectUrl = '',
  delay = 600,
  t,
  surveyorMessageKey = '',
  silent = false,
}) => {
  const featureKey = String(feature || '').trim()
  if (!featureKey || userStore?.can?.(featureKey)) {
    return true
  }

  return handleAccessDenied({
    deniedMessage: deniedMessage || resolvePermissionDeniedMessage(userStore, t, surveyorMessageKey),
    redirectUrl: redirectUrl || resolveFirstAccessibleRoute(userStore),
    delay,
    silent,
  })
}

export const guardRouteAccess = ({
  userStore,
  route,
  deniedMessage = '',
  redirectUrl = '',
  delay = 600,
  t,
  silent = false,
}) => {
  const normalizedRoute = normalizeRoutePath(route)
  if (!normalizedRoute || isPublicRoute(normalizedRoute)) {
    return true
  }

  if (!userStore?.isLoggedIn) {
    uni.reLaunch({ url: '/pages/login/login' })
    return false
  }

  const rule = getRouteAccessRule(normalizedRoute)
  if (!rule) {
    return true
  }

  const featureKeys = []
  if (rule.feature) featureKeys.push(String(rule.feature).trim())
  if (Array.isArray(rule.features)) {
    for (const item of rule.features) {
      const feature = String(item || '').trim()
      if (feature) featureKeys.push(feature)
    }
  }

  if (featureKeys.length === 0 || featureKeys.some(feature => userStore?.can?.(feature))) {
    return true
  }

  return handleAccessDenied({
    deniedMessage: deniedMessage || resolvePermissionDeniedMessage(userStore, t, rule.surveyorMessageKey || ''),
    redirectUrl: redirectUrl || resolveFirstAccessibleRoute(userStore),
    delay,
    silent,
  })
}
