import type { AppConfig, AppStatusRead } from '~/types/api'

/**
 * Names of the service areas (cities) for the flag and announcement pickers. They come from the app
 * status when this account may read it, else from the settings; empty when it may read neither.
 */
export async function useServiceAreaNames() {
  const { request } = useApi()
  const auth = useAuth()
  const { data } = await useAsyncData('service-area-names', async () => {
    try {
      if (auth.can('app_status.view')) return (await request<AppStatusRead>('/admin/app/status')).areas
      if (auth.can('config.view')) return ((await request<AppConfig>('/admin/config')).service_areas ?? []).map(a => a.name)
    }
    catch {
      // The pickers still show the cities already chosen.
    }
    return [] as string[]
  })
  return computed(() => data.value ?? [])
}
