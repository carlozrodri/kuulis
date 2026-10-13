import type { CheckKind, CheckStatus, Day, DocumentAlert, DocumentKind, DriverDocument, VerificationSettings, VerificationState } from '~/types/api'

// Ongoing driver verification (doc 12): expiry badges, review checklists, rejection reasons and
// the keyboard shortcuts of the review screen.

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

/** API defaults, for an older API or staff without config access. */
export const DEFAULT_VERIFICATION: VerificationSettings = {
  expiring_documents: ['drivers_license', 'medical_certificate', 'vehicle_registration'],
  optional_documents: ['criminal_record'],
  expiry_notice_days: [30, 7, 1],
  selfie_every_days: 7,
  mismatch_reports: 2,
  report_window_days: 30,
  induction_required: false,
}

export const checkStatusColor: Record<CheckStatus, BadgeColor> = {
  requested: 'neutral',
  pending: 'warning',
  approved: 'success',
  rejected: 'error',
  cancelled: 'neutral',
}

/** Rejecting these suspends the driver and opens an urgent report. */
export function checkSuspends(kind: CheckKind): boolean {
  return kind === 'selfie' || kind === 'reverification'
}

// ---- Expiry --------------------------------------------------------------------------------

const utc = (day: Day) => Date.parse(`${day.slice(0, 10)}T00:00:00Z`)

/** Whole days from `from` to `to` (negative when `to` is earlier). */
export function daysBetween(from: Day, to: Day): number {
  return Math.round((utc(to) - utc(from)) / 86_400_000)
}

export type ExpiryKey = 'expired' | 'today' | 'soon' | 'valid' | 'noDate'
export interface ExpiryBadge {
  key: ExpiryKey
  days: number | null
  color: BadgeColor
}

/**
 * Badge for a document's expiry: "vencido", "vence hoy", "vence en N días", "vigente hasta" or
 * "sin fecha" (an expiring kind without a date). null when the kind does not expire and has no date.
 */
export function expiryBadge(
  doc: Pick<DriverDocument, 'kind'> & { expires_on?: Day | null },
  today: Day,
  expiring: DocumentKind[],
  soonDays = 30,
): ExpiryBadge | null {
  if (!doc.expires_on) return expiring.includes(doc.kind) ? { key: 'noDate', days: null, color: 'warning' } : null
  const days = daysBetween(today, doc.expires_on)
  if (days < 0) return { key: 'expired', days, color: 'error' }
  if (days === 0) return { key: 'today', days, color: 'error' }
  if (days <= soonDays) return { key: 'soon', days, color: days <= 7 ? 'error' : 'warning' }
  return { key: 'valid', days, color: 'neutral' }
}

/** The most urgent expiry of a driver (for the list): expired first, then the fewest days left. */
export function nearestExpiry(state: VerificationState | null | undefined): DocumentAlert | null {
  if (!state?.expiring?.length) return null
  return [...state.expiring].sort((a, b) => a.days_left - b.days_left)[0] ?? null
}

/** The driver typed a date nobody confirmed yet. */
export function expiryUnconfirmed(doc: { expires_on?: Day | null, expiry_confirmed?: boolean }): boolean {
  return !!doc.expires_on && !doc.expiry_confirmed
}

/** Renewals of an expiring document and moto changes (the new carnet) need a date to approve. */
export function checkNeedsExpiry(kind: CheckKind, documentKind: DocumentKind | null | undefined, expiring: DocumentKind[]): boolean {
  if (kind === 'vehicle_change') return true
  return kind === 'document_renewal' && !!documentKind && expiring.includes(documentKind)
}

// ---- Checklists ----------------------------------------------------------------------------

export type ChecklistItem
  = | 'legible'
    | 'clearPhoto'
    | 'nameMatches'
    | 'numberMatches'
    | 'valid'
    | 'live'
    | 'faceMatchesSelfie'
    | 'faceMatchesId'
    | 'plateMatches'
    | 'vehicleMatches'

const DOCUMENT_CHECKLIST: Record<DocumentKind, ChecklistItem[]> = {
  id_card: ['legible', 'nameMatches', 'numberMatches', 'clearPhoto'],
  rif: ['legible', 'nameMatches', 'numberMatches'],
  drivers_license: ['legible', 'nameMatches', 'numberMatches'],
  medical_certificate: ['legible', 'nameMatches'],
  vehicle_registration: ['legible', 'plateMatches', 'vehicleMatches'],
  criminal_record: ['legible', 'nameMatches', 'numberMatches'],
  selfie: ['clearPhoto', 'live', 'faceMatchesId'],
  vehicle_photo: ['clearPhoto', 'plateMatches', 'vehicleMatches'],
}

/** What to tick before approving a document; "vigente" only for the kinds that expire. */
export function documentChecklist(kind: DocumentKind, expiring: DocumentKind[]): ChecklistItem[] {
  const items = [...(DOCUMENT_CHECKLIST[kind] ?? ['legible'])]
  if (expiring.includes(kind)) items.push('valid')
  return items
}

export function checkChecklist(kind: CheckKind, documentKind: DocumentKind | null | undefined, expiring: DocumentKind[]): ChecklistItem[] {
  switch (kind) {
    case 'selfie':
      return ['clearPhoto', 'live', 'faceMatchesSelfie', 'faceMatchesId']
    case 'reverification':
      return ['clearPhoto', 'live', 'faceMatchesSelfie', 'faceMatchesId', 'plateMatches', 'vehicleMatches']
    case 'document_renewal':
      return documentKind ? documentChecklist(documentKind, expiring) : ['legible']
    case 'vehicle_change':
      return ['legible', 'plateMatches', 'vehicleMatches', 'valid', 'clearPhoto']
  }
}

export function checklistComplete(items: readonly string[], ticked: Readonly<Record<string, boolean>>): boolean {
  return items.every(item => ticked[item] === true)
}

// ---- Rejection reasons ---------------------------------------------------------------------

export type RejectionReason
  = | 'blurry'
    | 'incomplete'
    | 'wrongDocument'
    | 'nameMismatch'
    | 'numberMismatch'
    | 'expired'
    | 'dateMismatch'
    | 'faceMismatch'
    | 'notLive'
    | 'plateMismatch'
    | 'vehicleMismatch'
    | 'other'

const DOCUMENT_REASONS: Record<DocumentKind, RejectionReason[]> = {
  id_card: ['blurry', 'incomplete', 'wrongDocument', 'nameMismatch', 'numberMismatch'],
  rif: ['blurry', 'incomplete', 'wrongDocument', 'nameMismatch', 'numberMismatch'],
  drivers_license: ['blurry', 'incomplete', 'wrongDocument', 'nameMismatch', 'numberMismatch'],
  medical_certificate: ['blurry', 'incomplete', 'wrongDocument', 'nameMismatch'],
  vehicle_registration: ['blurry', 'incomplete', 'wrongDocument', 'plateMismatch', 'vehicleMismatch'],
  criminal_record: ['blurry', 'incomplete', 'wrongDocument', 'nameMismatch', 'numberMismatch'],
  selfie: ['blurry', 'notLive', 'faceMismatch'],
  vehicle_photo: ['blurry', 'plateMismatch', 'vehicleMismatch'],
}

/** Predefined reasons (texts under verification.reasons), "other" (free text) always last. */
export function documentReasons(kind: DocumentKind, expiring: DocumentKind[]): RejectionReason[] {
  const reasons = [...(DOCUMENT_REASONS[kind] ?? ['blurry', 'incomplete', 'wrongDocument'])]
  if (expiring.includes(kind)) reasons.push('expired', 'dateMismatch')
  return [...reasons, 'other']
}

export function checkReasons(kind: CheckKind, documentKind: DocumentKind | null | undefined, expiring: DocumentKind[]): RejectionReason[] {
  switch (kind) {
    case 'selfie':
      return ['blurry', 'notLive', 'faceMismatch', 'other']
    case 'reverification':
      return ['blurry', 'notLive', 'faceMismatch', 'plateMismatch', 'vehicleMismatch', 'other']
    case 'document_renewal':
      return documentKind ? documentReasons(documentKind, expiring) : ['blurry', 'incomplete', 'wrongDocument', 'other']
    case 'vehicle_change':
      return ['blurry', 'incomplete', 'plateMismatch', 'vehicleMismatch', 'expired', 'dateMismatch', 'other']
  }
}

// ---- Keyboard shortcuts --------------------------------------------------------------------

export type ShortcutAction = 'approve' | 'reject' | 'zoomIn' | 'zoomOut' | 'rotate' | 'reset' | 'prev' | 'next' | 'nextCheck'

/** For the legend on the review screen, in this order. */
export const SHORTCUTS: { keys: string[], action: ShortcutAction | 'tick' }[] = [
  { keys: ['1', '…', '9'], action: 'tick' },
  { keys: ['A'], action: 'approve' },
  { keys: ['R'], action: 'reject' },
  { keys: ['+', '−'], action: 'zoomIn' },
  { keys: ['O'], action: 'rotate' },
  { keys: ['0'], action: 'reset' },
  { keys: ['←', '→'], action: 'next' },
  { keys: ['N'], action: 'nextCheck' },
]

const KEYMAP: Record<string, ShortcutAction> = {
  'a': 'approve',
  'r': 'reject',
  '+': 'zoomIn',
  '=': 'zoomIn',
  '-': 'zoomOut',
  '_': 'zoomOut',
  'o': 'rotate',
  '0': 'reset',
  'arrowleft': 'prev',
  'arrowright': 'next',
  'n': 'nextCheck',
}

interface KeyLike {
  key: string
  ctrlKey?: boolean
  metaKey?: boolean
  altKey?: boolean
  target?: EventTarget | { tagName?: string, isContentEditable?: boolean } | null
}

/** Typing in a field, or with Ctrl/Cmd/Alt held: not a shortcut. */
function ignored(event: KeyLike): boolean {
  if (event.ctrlKey || event.metaKey || event.altKey) return true
  const target = event.target as { tagName?: string, isContentEditable?: boolean } | null | undefined
  const tag = target?.tagName?.toUpperCase()
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || !!target?.isContentEditable
}

export function shortcutFor(event: KeyLike): ShortcutAction | null {
  if (ignored(event)) return null
  return KEYMAP[event.key.toLowerCase()] ?? null
}

/** 1-9 tick the checklist item with that number (0-based index), or null. */
export function checklistKey(event: KeyLike, count: number): number | null {
  if (ignored(event) || !/^[1-9]$/.test(event.key)) return null
  const index = Number(event.key) - 1
  return index < count ? index : null
}

/** The check after `current` in the queue (oldest first); wraps to the first other one. */
export function nextInQueue(ids: string[], current: string): string | null {
  const index = ids.indexOf(current)
  const after = index >= 0 ? ids.slice(index + 1) : ids
  return after.find(id => id !== current) ?? ids.find(id => id !== current) ?? null
}

// ---- Image viewer --------------------------------------------------------------------------

export const ZOOM_MIN = 0.5
export const ZOOM_MAX = 6

export function zoomBy(zoom: number, direction: 1 | -1): number {
  const next = direction > 0 ? zoom * 1.25 : zoom / 1.25
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(next * 100) / 100))
}

export function rotateBy(rotation: number, degrees = 90): number {
  return (((rotation + degrees) % 360) + 360) % 360
}
