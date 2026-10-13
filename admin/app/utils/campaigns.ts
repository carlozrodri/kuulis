import type {
  CampaignAudience,
  CampaignChannel,
  CampaignCreate,
  CampaignRead,
  CampaignStats,
  CampaignStatus,
  Segment,
} from '~/types/api'
import { CAMPAIGN_CHANNELS } from '~/types/api'
import type { Translate } from '~/utils/control'
import { listOf } from '~/utils/control'
import { fromLocalInput, toLocalInput } from '~/utils/promotions'

// Marketing campaigns (doc 14): the form behind /campaigns/[id], its checks and the summaries.

/** Limits from the contract (the API validates again). */
export const CAMPAIGN_NAME_MIN = 2
export const CAMPAIGN_NAME_MAX = 120
export const CAMPAIGN_TITLE_MAX = 120
export const CAMPAIGN_BODY_MAX = 1000
export const DEEP_LINK_MAX = 300
export const SEGMENT_DAYS_MIN = 1
export const SEGMENT_DAYS_MAX = 365
export const SEGMENT_CITIES_MAX = 20
/** Results refresh while a campaign is going out. */
export const CAMPAIGN_POLL_MS = 5000

/** App screens a campaign can open (key under `campaigns.links`). */
export const SUGGESTED_LINKS = [
  { path: '/', key: 'home' },
  { path: '/wallet', key: 'wallet' },
  { path: '/profile/invite', key: 'invite' },
  { path: '/help', key: 'help' },
  { path: '/notifications', key: 'inbox' },
] as const

const VERSION = /^\d+(\.\d+){0,2}$/
const DEEP_LINK = /^(\/\S*|https:\/\/[^\s/]+\.\S+)$/

export const CAMPAIGN_STATUS_COLORS: Record<CampaignStatus, 'neutral' | 'warning' | 'info' | 'primary' | 'success' | 'error'> = {
  draft: 'neutral',
  pending_approval: 'warning',
  scheduled: 'info',
  sending: 'primary',
  sent: 'success',
  cancelled: 'error',
}

/** Text, audience and date can still change. */
export const isCampaignEditable = (status: CampaignStatus) => status === 'draft' || status === 'scheduled' || status === 'pending_approval'
export const canCancelCampaign = (status: CampaignStatus) => status === 'scheduled' || status === 'sending' || status === 'pending_approval'
export const canDeleteCampaign = (status: CampaignStatus) => status === 'draft' || status === 'pending_approval'

export interface CampaignForm {
  name: string
  audience: CampaignAudience
  cities: string[]
  activeOn: boolean
  active_days: number
  inactiveOn: boolean
  inactive_days: number
  fee_pending: boolean
  newOn: boolean
  new_without_ride_days: number
  versionOn: boolean
  app_version_below: string
  locale: 'any' | 'es' | 'en'
  channels: CampaignChannel[]
  title_es: string
  body_es: string
  title_en: string
  body_en: string
  deep_link: string
  when: 'now' | 'later'
  /** `datetime-local` value, the admin's browser time. */
  scheduled_at: string
}

export function defaultCampaignForm(): CampaignForm {
  return {
    name: '',
    audience: 'all',
    cities: [],
    activeOn: false,
    active_days: 30,
    inactiveOn: false,
    inactive_days: 30,
    fee_pending: false,
    newOn: false,
    new_without_ride_days: 7,
    versionOn: false,
    app_version_below: '',
    locale: 'any',
    channels: ['push', 'inbox'],
    title_es: '',
    body_es: '',
    title_en: '',
    body_en: '',
    deep_link: '',
    when: 'now',
    scheduled_at: '',
  }
}

export function campaignFormFrom(c: Pick<CampaignRead, 'name' | 'segment' | 'channels' | 'title_es' | 'body_es' | 'title_en' | 'body_en' | 'deep_link' | 'scheduled_at'>): CampaignForm {
  const d = defaultCampaignForm()
  const s = c.segment
  return {
    name: c.name,
    audience: s.audience ?? 'all',
    cities: [...(s.cities ?? [])],
    activeOn: !!s.active_days,
    active_days: s.active_days ?? d.active_days,
    inactiveOn: !!s.inactive_days,
    inactive_days: s.inactive_days ?? d.inactive_days,
    fee_pending: !!s.fee_pending,
    newOn: !!s.new_without_ride_days,
    new_without_ride_days: s.new_without_ride_days ?? d.new_without_ride_days,
    versionOn: !!s.app_version_below,
    app_version_below: s.app_version_below ?? '',
    locale: s.locale ?? 'any',
    channels: CAMPAIGN_CHANNELS.filter(ch => c.channels.includes(ch)),
    title_es: c.title_es,
    body_es: c.body_es ?? '',
    title_en: c.title_en ?? '',
    body_en: c.body_en ?? '',
    deep_link: c.deep_link ?? '',
    when: c.scheduled_at ? 'later' : 'now',
    scheduled_at: toLocalInput(c.scheduled_at),
  }
}

export function segmentFromForm(form: CampaignForm): Segment {
  return {
    audience: form.audience,
    cities: [...new Set(form.cities)],
    active_days: form.activeOn ? Number(form.active_days) : null,
    inactive_days: form.inactiveOn ? Number(form.inactive_days) : null,
    // A pending fee only exists for drivers.
    fee_pending: form.audience !== 'passengers' && form.fee_pending,
    new_without_ride_days: form.newOn ? Number(form.new_without_ride_days) : null,
    app_version_below: form.versionOn && form.app_version_below.trim() ? form.app_version_below.trim() : null,
    locale: form.locale === 'any' ? null : form.locale,
  }
}

/** The date to send at as an ISO timestamp, or null for "now". */
export function scheduledAtFrom(form: CampaignForm): string | null {
  return form.when === 'later' ? fromLocalInput(form.scheduled_at) : null
}

export function campaignPayload(form: CampaignForm): CampaignCreate {
  const optional = (text: string) => text.trim() || null
  return {
    name: form.name.trim(),
    segment: segmentFromForm(form),
    channels: CAMPAIGN_CHANNELS.filter(ch => form.channels.includes(ch)),
    title_es: form.title_es.trim(),
    body_es: form.body_es.trim(),
    title_en: optional(form.title_en),
    body_en: optional(form.title_en) ? optional(form.body_en) : null,
    deep_link: optional(form.deep_link),
    scheduled_at: scheduledAtFrom(form),
  }
}

/** Problems with the audience alone (the live count waits until there are none). */
export function segmentIssues(form: CampaignForm): string[] {
  const issues: string[] = []
  const days = (on: boolean, value: number) => on && !(Number.isInteger(Number(value)) && value >= SEGMENT_DAYS_MIN && value <= SEGMENT_DAYS_MAX)
  if (days(form.activeOn, form.active_days) || days(form.inactiveOn, form.inactive_days) || days(form.newOn, form.new_without_ride_days)) {
    issues.push('days')
  }
  // "Signed in within 30 days but not within 7": the second number must be the smaller one.
  else if (form.activeOn && form.inactiveOn && form.inactive_days >= form.active_days) issues.push('activeInactive')
  if (form.versionOn && !VERSION.test(form.app_version_below.trim())) issues.push('version')
  if (form.cities.length > SEGMENT_CITIES_MAX) issues.push('cities')
  return issues
}

/**
 * Issue keys (i18n under `campaigns.errors`); empty when the campaign can be saved. With `forSend`
 * the date is checked too (a draft may keep an old one).
 */
export function validateCampaign(form: CampaignForm, options: { forSend?: boolean, now?: Date } = {}): string[] {
  const issues: string[] = []
  const name = form.name.trim()
  if (name.length < CAMPAIGN_NAME_MIN || name.length > CAMPAIGN_NAME_MAX) issues.push('name')
  issues.push(...segmentIssues(form))
  if (!form.channels.length) issues.push('channels')
  if (!form.title_es.trim()) issues.push('titleEs')
  if (form.title_es.length > CAMPAIGN_TITLE_MAX || form.title_en.length > CAMPAIGN_TITLE_MAX
    || form.body_es.length > CAMPAIGN_BODY_MAX || form.body_en.length > CAMPAIGN_BODY_MAX) {
    issues.push('tooLong')
  }
  if (form.body_en.trim() && !form.title_en.trim()) issues.push('titleEn')
  const link = form.deep_link.trim()
  if (link && (link.length > DEEP_LINK_MAX || !DEEP_LINK.test(link))) issues.push('deepLink')
  if (form.when === 'later') {
    const at = fromLocalInput(form.scheduled_at)
    if (!at) issues.push('scheduleMissing')
    else if (options.forSend && new Date(at).getTime() <= (options.now ?? new Date()).getTime()) issues.push('schedulePast')
  }
  return issues
}

/**
 * Plain-language audience, e.g. "Motorizados en Caracas · con cuota pendiente · app menor a 1.4.0".
 * Texts come from `campaigns.summary`.
 */
export function segmentSummary(segment: Segment, t: Translate, locale: string): string {
  const who = t(`campaigns.summary.${segment.audience ?? 'all'}`)
  const parts = [segment.cities?.length ? t('campaigns.summary.inCities', { who, cities: listOf(segment.cities, locale, 'disjunction') }) : who]
  if (segment.active_days) parts.push(t('campaigns.summary.active', { n: segment.active_days }))
  if (segment.inactive_days) parts.push(t('campaigns.summary.inactive', { n: segment.inactive_days }))
  if (segment.fee_pending && segment.audience !== 'passengers') parts.push(t('campaigns.summary.feePending'))
  if (segment.new_without_ride_days) parts.push(t('campaigns.summary.newWithoutRide', { n: segment.new_without_ride_days }))
  if (segment.app_version_below) parts.push(t('campaigns.summary.versionBelow', { version: segment.app_version_below }))
  if (segment.locale) parts.push(t(`campaigns.summary.locale.${segment.locale}`))
  return parts.join(' · ')
}

export interface CampaignRates {
  /** Opened out of the people it reached. */
  openRate: number | null
  /** Push receipts confirmed out of the phones it was pushed to. */
  deliveryRate: number | null
  /** People already handled (sent or skipped) out of the frozen audience. */
  progress: number | null
}

const ratio = (part: number, whole: number) => (whole > 0 ? Math.min(1, part / whole) : null)

export function campaignRates(stats: Partial<CampaignStats> | null | undefined): CampaignRates {
  const s = stats ?? {}
  return {
    openRate: ratio(s.opened ?? 0, s.sent ?? 0),
    deliveryRate: ratio(s.delivered ?? 0, s.pushed ?? 0),
    progress: ratio((s.sent ?? 0) + (s.skipped ?? 0), s.targeted ?? 0),
  }
}

/** The date that matters for each status, with its label key under `campaigns.when`. */
export function campaignMoment(c: Pick<CampaignRead, 'status' | 'scheduled_at' | 'started_at' | 'finished_at' | 'created_at'>): { key: string, at: string } {
  switch (c.status) {
    case 'sent':
      return { key: 'sentAt', at: c.finished_at ?? c.started_at ?? c.created_at }
    case 'cancelled':
      return { key: 'cancelledAt', at: c.finished_at ?? c.created_at }
    case 'sending':
      return { key: 'startedAt', at: c.started_at ?? c.created_at }
    default:
      return c.scheduled_at ? { key: 'scheduledFor', at: c.scheduled_at } : { key: 'createdAt', at: c.created_at }
  }
}
