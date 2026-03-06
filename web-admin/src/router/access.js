const hasCodeList = (value) => Array.isArray(value) && value.length > 0

export const routeHasAccess = (routeLike, userStore) => {
  if (!routeLike) return false

  const permissions = routeLike.meta?.permissions
  if (hasCodeList(permissions)) {
    return permissions.some(code => userStore.hasPermission(code))
  }

  const roles = routeLike.meta?.roles
  if (hasCodeList(roles)) {
    return roles.some(code => userStore.hasRole(code))
  }

  return true
}

const isVisibleLeafRoute = (routeLike) => {
  if (!routeLike?.name) return false
  if (routeLike.redirect) return false
  if (routeLike.meta?.hidden) return false
  return Boolean(routeLike.meta?.titleKey || routeLike.meta?.title)
}

const findFirstAccessibleLeaf = (routeList = [], userStore) => {
  for (const route of routeList) {
    if (!routeHasAccess(route, userStore)) continue

    if (Array.isArray(route.children) && route.children.length > 0) {
      const childMatch = findFirstAccessibleLeaf(route.children, userStore)
      if (childMatch) return childMatch
    }

    if (isVisibleLeafRoute(route)) {
      return { name: route.name }
    }
  }

  return null
}

export const resolveDefaultAuthenticatedRoute = (routeList = [], userStore) => {
  const rootRoute = routeList.find(route => route.path === '/')
  const children = Array.isArray(rootRoute?.children) ? rootRoute.children : []
  const dashboardRoute = children.find(route => route.name === 'Dashboard')

  if (dashboardRoute && routeHasAccess(dashboardRoute, userStore)) {
    return { name: 'Dashboard' }
  }

  return findFirstAccessibleLeaf(children, userStore)
}

export const isSameRouteTarget = (target, routeLike) => {
  if (!target || !routeLike) return false

  if (target.name && routeLike.name) {
    return target.name === routeLike.name
  }

  if (target.path && routeLike.path) {
    return target.path === routeLike.path
  }

  return false
}
