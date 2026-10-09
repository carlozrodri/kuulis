import type { ReportCounts, ReportPage } from '~/types/api'

/**
 * Inbox counts for the sidebar badge (open / in review / urgent open), shared so the reports pages can refresh
 * them right after an action. GET /admin/reports returns `counts` for the whole inbox with any page.
 */
export function useReportCounts() {
  const counts = useState<ReportCounts | null>('report-counts', () => null)
  const { request } = useApi()

  async function refresh() {
    try {
      const page = await request<ReportPage>('/admin/reports', { query: { status: 'open', limit: 1, offset: 0 } })
      counts.value = page.counts ?? { open: page.total, in_review: 0, urgent_open: 0 }
    }
    catch {
      // An API without phase 1E (or a staff session that expired): just no badge.
    }
  }

  /** Pages that already fetched the inbox pass its counts instead of asking again. */
  function set(value: ReportCounts | null | undefined) {
    if (value) counts.value = value
  }

  return { counts, refresh, set }
}
