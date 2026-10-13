import type { AuthorKind, CannedAction, ReplyThen, ReportAdminRead, ReportSource, WaitingOn } from '~/types/api'

// Support tickets, saved replies and the help center (doc 13).

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

/** Limits from the contract (the API validates again). */
export const REPLY_MAX = 4000
export const MAX_ATTACHMENTS = 4
export const ATTACHMENT_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic']
export const TAG_MAX = 40
export const TAGS_MAX = 10
export const CANNED_TITLE_MAX = 120
export const CANNED_BODY_MAX = 4000
export const HELP_SLUG_MAX = 120
export const HELP_TITLE_MAX = 200
export const HELP_SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

export const sourceIcon: Record<ReportSource, string> = {
  app: 'i-lucide-smartphone',
  help: 'i-lucide-book-open',
  lost_item: 'i-lucide-package-search',
  web: 'i-lucide-globe',
}

export const waitingOnColor: Record<WaitingOn, BadgeColor> = {
  staff: 'warning',
  user: 'info',
}

/** What a saved reply does maps to the composer's "after sending" choice. */
export function thenFromAction(action: CannedAction | null | undefined): ReplyThen {
  if (action === 'resolve') return 'resolve'
  if (action === 'none') return 'keep'
  return 'wait_user'
}

export type SlaState = 'overdue' | 'soon' | 'ok'

/**
 * Where the ticket stands against its answer deadline: `overdue` (the API flag, or the deadline passed while it
 * waits on the team), `soon` (less than an hour left) or `ok`. null when there is no deadline running (answered,
 * waiting on the user, or closed).
 */
export function slaState(
  report: Pick<ReportAdminRead, 'overdue' | 'sla_due_at' | 'waiting_on' | 'status'>,
  now: number = Date.now(),
): SlaState | null {
  if (report.status === 'resolved' || report.status === 'dismissed') return null
  if (report.overdue) return 'overdue'
  if (!report.sla_due_at || report.waiting_on !== 'staff') return null
  const left = new Date(report.sla_due_at).getTime() - now
  if (!Number.isFinite(left)) return null
  if (left <= 0) return 'overdue'
  return left < 3_600_000 ? 'soon' : 'ok'
}

/** Minutes as "45 min", "3 h 20 min" or "2 d 4 h" (averages of the metrics; "—" when there is no data). */
export function formatMinutesSpan(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined || !Number.isFinite(minutes) || minutes < 0) return '—'
  const total = Math.round(minutes)
  if (total < 60) return `${total} min`
  const days = Math.floor(total / 1440)
  const hours = Math.floor((total % 1440) / 60)
  if (days > 0) return hours ? `${days} d ${hours} h` : `${days} d`
  const rest = total % 60
  return rest ? `${hours} h ${rest} min` : `${hours} h`
}

/** Share of "yes" among the "¿Te ayudó?" answers; null without answers. */
export function helpfulRate(yes: number, no: number): number | null {
  const total = (yes || 0) + (no || 0)
  return total > 0 ? (yes || 0) / total : null
}

/** "Pago Móvil " → "pago-movil": lower case, no accents, words joined by dashes. */
export function normalizeTag(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9_]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, TAG_MAX)
}

/** Normalized, without empties nor repeats, in the order given. */
export function normalizeTags(tags: string[]): string[] {
  return [...new Set(tags.map(normalizeTag).filter(Boolean))]
}

/** Help article slug from its title: "¿Cómo pago?" → "como-pago". */
export function slugify(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, HELP_SLUG_MAX)
    .replace(/-+$/, '')
}

export interface TicketContact {
  name: string
  email: string | null
  /** A website contact without an account. */
  web: boolean
}

/** Who wrote the ticket: the account, or the name and e-mail typed in the web form. */
export function ticketContact(report: Pick<ReportAdminRead, 'reporter' | 'contact_name' | 'contact_email' | 'source'>): TicketContact {
  if (report.reporter) {
    return { name: report.reporter.name || report.reporter.email || '—', email: report.reporter.email, web: report.source === 'web' }
  }
  return { name: report.contact_name || report.contact_email || '—', email: report.contact_email ?? null, web: true }
}

/** Conversation layout: the user on the left, the team on the right, automatic lines centered. */
export function messageSide(kind: AuthorKind): 'left' | 'right' | 'center' {
  if (kind === 'staff') return 'right'
  if (kind === 'system') return 'center'
  return 'left'
}

/** Attachments the API accepts (images, at most 4 per message). */
export function isAllowedAttachment(file: Pick<File, 'type'>): boolean {
  return ATTACHMENT_TYPES.includes(file.type)
}

/** Image type from a storage key's extension, for the viewer (HEIC opens in a new tab). */
export function contentTypeFromKey(key: string): string {
  const ext = key.split('?')[0]!.split('.').pop()?.toLowerCase() ?? ''
  const types: Record<string, string> = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp', heic: 'image/heic' }
  return types[ext] ?? 'image/jpeg'
}
