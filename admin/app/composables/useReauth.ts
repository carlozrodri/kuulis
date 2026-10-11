/**
 * Fresh authenticator code for sensitive actions (roles, balances, second factors). useApi() calls
 * ask() when the API answers `reauth_required`; <ReauthModal> (in the default layout) collects the
 * code, confirms it with POST /auth/admin/reauth and resolves the promise.
 */
const pending = shallowRef<((ok: boolean) => void) | null>(null)

export function useReauth() {
  function ask(): Promise<boolean> {
    pending.value?.(false)
    return new Promise((resolve) => {
      pending.value = resolve
    })
  }

  function finish(ok: boolean) {
    pending.value?.(ok)
    pending.value = null
  }

  return { open: computed(() => pending.value !== null), ask, finish }
}
