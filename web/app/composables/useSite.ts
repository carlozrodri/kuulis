import type { PublicSite } from '~/utils/types'

/** Cities, driver requirements and fee tiers from the API (GET /public/site); null when unreachable. */
export function useSite() {
  const { request } = useApi()
  return useAsyncData('site', () => request<PublicSite>('/public/site').catch(() => null))
}
