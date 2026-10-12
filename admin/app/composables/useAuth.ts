import type { AdminAuthResponse, AdminLoginStep, AuthResponse, Role, User } from '~/types/api'

/** Lets the API label the session ("Admin · Chrome · Windows") in the session lists. */
export const CLIENT_HEADERS = { 'X-Client-Platform': 'admin' }

const cookieOptions = {
  sameSite: 'strict' as const,
  secure: !import.meta.dev,
  path: '/',
}

// One refresh at a time for the whole tab. Each useAuth() call is a new closure, so a per-call
// promise let the requests that hit 401 together (every 15 min, when the access token expires)
// refresh in parallel with the same token: the API saw a reused refresh token and closed the session.
// The panel is a SPA (ssr: false), so module state is per browser tab.
let refreshing: Promise<boolean> | null = null

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
  /** What the staff role allows (admins can do everything); the API enforces the same. */
  const can = (permission: string) => isAdmin.value || !!user.value?.permissions?.includes(permission)

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

  /** Password step. Returns the second-factor step, or null when the API signed in directly. */
  async function login(email: string, password: string): Promise<AdminLoginStep | null> {
    const data = await $fetch<AdminLoginStep | AdminAuthResponse>(`${config.public.apiBase}/auth/admin/login`, {
      method: 'POST',
      headers: CLIENT_HEADERS,
      body: { email, password },
    })
    if ('challenge' in data) return data
    setSession(data)
    return null
  }

  /** Code step. Returns the recovery codes when the authenticator was just set up. */
  async function verifyTotp(challenge: string, code: string): Promise<string[] | null> {
    const data = await $fetch<AdminAuthResponse>(`${config.public.apiBase}/auth/admin/totp`, {
      method: 'POST',
      headers: CLIENT_HEADERS,
      body: { challenge, code },
    })
    setSession(data)
    return data.recovery_codes ?? null
  }

  async function refresh(): Promise<boolean> {
    if (!refreshToken.value) return false
    // Share one in-flight refresh between concurrent 401s.
    refreshing ??= $fetch<Omit<AuthResponse, 'user'>>(`${config.public.apiBase}/auth/refresh`, {
      method: 'POST',
      headers: CLIENT_HEADERS,
      body: { refresh_token: refreshToken.value },
    })
      .then((data) => {
        accessToken.value = data.access_token
        refreshToken.value = data.refresh_token
        return true
      })
      .catch((error: { status?: number }) => {
        // Only a rejected token ends the session; a network blip or a 5xx keeps it for the next try.
        if (error?.status === 401) clearSession()
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
    can,
    login,
    verifyTotp,
    logout,
    refresh,
    clearSession,
  }
}
