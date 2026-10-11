import type { ApprovalHeld } from '~/types/api'

/** Requests this account can approve (sidebar badge), shared so any page can refresh it. */
export function useApprovalCount() {
  const pending = useState<number>('approval-count', () => 0)
  const { request } = useApi()
  const toast = useToast()
  const { t } = useI18n()

  async function refresh() {
    try {
      pending.value = (await request<{ pending: number }>('/admin/approvals/count')).pending
    }
    catch {
      // An API without approvals yet, or an expired session: just no badge.
    }
  }

  /** Tells the person their change now waits for someone else. */
  function notifyHeld(held: ApprovalHeld) {
    toast.add({
      title: t('approvals.held'),
      description: held.approval.summary,
      color: 'warning',
      icon: 'i-lucide-hourglass',
    })
    return refresh()
  }

  return { pending, refresh, notifyHeld }
}
