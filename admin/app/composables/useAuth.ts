import type { AuthResponse, Role, User } from '~/types/api'

const cookieOptions = {
  sameSite: 'strict' as const,
  secure: !import.meta.dev,
  path: '/',
}

/**
 * Session state for the admin panel. Tokens live in first-party cookies scoped to this domain;
 * the access token is short lived and refreshed transparently by useApi().
 */
export function useAuth() {
  const config = useRuntimeConfig()
  const accessToken = useCookie<string | null>('kuulis_at', { ...cookieOptions, maxAge: 60 * 15 })
  const refreshToken = useCookie<string | null>('kuulis_rt', { ...cookieOptions, maxAge: 60 * 60 * 24 * 30 })
  const user = useState<User | null>('auth:user', () => null)

  const isAuthenticated = computed(() => !!refreshToken.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const hasRole = (...roles: Role[]) => !!user.value && roles.includes(user.value.role)

  function setSession(data: AuthResponse) {
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    user.value = data.user
  }

  function clearSession() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
  }

  async function login(email: string, password: string) {
    const data = await $fetch<AuthResponse>(`${config.public.apiBase}/auth/admin/login`, {
      method: 'POST',
      body: { email, password },
    })
    setSession(data)
    return data.user
  }

  let refreshing: Promise<boolean> | null = null
  async function refresh(): Promise<boolean> {
    if (!refreshToken.value) return false
    // Share one in-flight refresh between concurrent 401s.
    refreshing ??= $fetch<Omit<AuthResponse, 'user'>>(`${config.public.apiBase}/auth/refresh`, {
      method: 'POST',
      body: { refresh_token: refreshToken.value },
    })
      .then((data) => {
        accessToken.value = data.access_token
        refreshToken.value = data.refresh_token
        return true
      })
      .catch(() => {
        clearSession()
        return false
      })
      .finally(() => {
        refreshing = null
      })
    return refreshing
  }

  async function logout() {
    if (refreshToken.value) {
      await $fetch(`${config.public.apiBase}/auth/logout`, {
        method: 'POST',
        body: { refresh_token: refreshToken.value },
      }).catch(() => {})
    }
    clearSession()
    await navigateTo('/login')
  }

  return {
    user,
    accessToken,
    isAuthenticated,
    isAdmin,
    hasRole,
    login,
    logout,
    refresh,
    clearSession,
  }
}
