import type { Role } from '~/types/api'

const PUBLIC_ROUTES = new Set(['/login', '/accept-invite'])

export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuth()
  const { request } = useApi()

  if (PUBLIC_ROUTES.has(to.path)) {
    if (auth.isAuthenticated.value) return navigateTo('/')
    return
  }
  if (!auth.isAuthenticated.value) {
    return navigateTo({ path: '/login', query: { redirect: to.fullPath } })
  }
  // The login response has no permissions; /users/me does.
  if (!auth.user.value || auth.user.value.permissions == null) {
    try {
      auth.user.value = await request('/users/me')
    }
    catch {
      return navigateTo('/login')
    }
  }
  if (!auth.hasRole('staff', 'admin')) {
    await auth.logout()
    return abortNavigation()
  }
  const required = to.meta.roles as Role[] | undefined
  const permission = to.meta.permission as string | undefined
  if ((required && !auth.hasRole(...required)) || (permission && !auth.can(permission))) {
    const home = homePath(auth.isAdmin.value, auth.can)
    return to.path === home ? navigateTo('/profile') : navigateTo(home)
  }
})
