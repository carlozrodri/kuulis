import type { Role } from '~/types/api'

const PUBLIC_ROUTES = new Set(['/login'])

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
  if (!auth.user.value) {
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
  if (required && !auth.hasRole(...required)) {
    return navigateTo('/')
  }
})
