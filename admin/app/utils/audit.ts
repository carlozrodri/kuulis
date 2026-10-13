import type { AuditEntry } from '~/types/api'

export const AUDIT_ENTITY_TYPES = [
  'user',
  'driver',
  'driver_check',
  'ride',
  'promotion',
  'report',
  'wallet',
  'top_up',
  'charge',
  'config',
  'rate',
  'subscription',
  'fee_schedule',
  'notification',
  'finance',
  'file',
  'staff_role',
  'audit',
  'approval',
  'legal',
  'app_release',
  'app_update',
  'feature_flag',
  'announcement',
] as const

/** Admin page of the audited record, when it has one. */
export function auditEntityLink(entry: Pick<AuditEntry, 'entity_type' | 'entity_id'> & Partial<Pick<AuditEntry, 'action'>>): string | null {
  const id = entry.entity_id
  // Maintenance and city pauses live in the config but are edited on their own page (doc 10).
  if (entry.action === 'app_status.update') return '/app-status'
  if (entry.entity_type === 'config') return '/settings'
  if (entry.entity_type === 'feature_flag') return '/flags'
  if (entry.entity_type === 'announcement') return '/announcements'
  if (!id) return null
  switch (entry.entity_type) {
    case 'user': return `/users/${id}`
    case 'driver': return `/drivers/${id}`
    case 'driver_check': return `/drivers/checks/${id}`
    case 'ride': return `/rides/${id}`
    case 'promotion': return `/promotions/${id}`
    case 'report': return `/reports/${id}`
    case 'wallet': return `/wallets/${id}`
    case 'staff_role': return '/roles'
    case 'approval': return '/approvals'
    case 'legal': return '/legal'
    case 'app_release': return '/versions'
    case 'app_update': return '/versions'
    default: return null
  }
}

export interface AuditChange {
  key: string
  before: unknown
  after: unknown
}

/** Keys of before/after side by side (only after when the action stored no before). */
export function auditChanges(entry: Pick<AuditEntry, 'before' | 'after'>): AuditChange[] {
  const before = entry.before ?? {}
  const after = entry.after ?? {}
  const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])]
  return keys.map(key => ({ key, before: before[key], after: after[key] }))
}

export function auditValue(value: unknown): string {
  if (value === undefined) return ''
  if (value === null) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
