import type { RiskSummary } from '~/types/api'

/** Anti-fraud summary (doc 16) for the menu badge, shared so the Risk page can refresh it after acting. */
export function useRiskSummary() {
  const summary = useState<RiskSummary | null>('risk-summary', () => null)
  const { request } = useApi()
  const auth = useAuth()

  async function refresh() {
    if (!auth.can('risk.view')) return
    try {
      summary.value = await request<RiskSummary>('/admin/risk/summary')
    }
    catch {
      // An API without doc 16, or a dropped connection: no badge until the next refresh.
    }
  }

  return { summary, refresh }
}
