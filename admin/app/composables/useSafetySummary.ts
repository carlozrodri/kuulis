import type { SafetySummary } from '~/types/api'

/**
 * Safety center summary for the menu badge, shared by every page. The layout polls it every few
 * seconds and rings when a new alert opens (doc 11).
 */
export function useSafetySummary() {
  const summary = useState<SafetySummary | null>('safety-summary', () => null)
  const muted = useState<boolean>('safety-muted', () => false)
  const { request } = useApi()
  const auth = useAuth()

  async function refresh() {
    if (!auth.can('safety.view')) return
    let next: SafetySummary
    try {
      next = await request<SafetySummary>('/admin/safety/summary')
    }
    catch {
      return // An API without doc 11, or a dropped connection: try again on the next tick.
    }
    if (!muted.value && shouldRing(summary.value, next)) playAlarm()
    summary.value = next
  }

  return { summary, muted, refresh }
}
