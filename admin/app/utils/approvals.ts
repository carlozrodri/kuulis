import type { ApprovalHeld, ApprovalRead } from '~/types/api'

export const APPROVAL_STATUSES = ['pending', 'approved', 'rejected', 'expired'] as const

/** An action endpoint answered 202 because the change now waits for a second person. */
export function isHeld(value: unknown): value is ApprovalHeld {
  return !!value && typeof value === 'object' && (value as { status?: unknown }).status === 'pending_approval'
}

export function approvalColor(status: ApprovalRead['status']): 'warning' | 'success' | 'error' | 'neutral' {
  switch (status) {
    case 'pending': return 'warning'
    case 'approved': return 'success'
    case 'rejected': return 'error'
    default: return 'neutral'
  }
}

/** Admin page of the record a request is about, when it has one. */
export function approvalLink(approval: Pick<ApprovalRead, 'action' | 'entity_id'>): string | null {
  switch (approval.action) {
    case 'wallet.adjust': return approval.entity_id ? `/wallets/${approval.entity_id}` : null
    case 'fee_schedule.create': return '/subscriptions?tab=schedules'
    case 'charge.waive': return '/subscriptions'
    case 'config.update': return '/settings'
    case 'campaign.send': return approval.entity_id ? `/campaigns/${approval.entity_id}` : null
    default: return null
  }
}
