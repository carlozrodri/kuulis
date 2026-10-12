import type {
  AnnouncementInput,
  AnnouncementStyle,
  AppMode,
  AppPlatform,
  AppScreen,
  AreaPause,
  FlagRules,
  Localized,
  Maintenance,
} from '~/types/api'
import { APP_MODES, APP_PLATFORMS } from '~/types/api'
import { fromLocalInput, toLocalInput } from '~/utils/promotions'

// Remote control of the app (doc 10): maintenance, city pauses, feature flags and announcements.

/** vue-i18n's `t`, passed in so these helpers stay plain functions (and testable). */
export type Translate = (key: string, params?: Record<string, unknown>) => string

/** Limits from the contract (the API validates again). */
export const LOCALIZED_MAX = 300
export const CTA_URL_MAX = 500
export const AREA_MAX = 20

export const PLATFORM_LABELS: Record<AppPlatform, string> = { android: 'Android', ios: 'iOS', web: 'Web' }

const cleanLocalized = (value: Localized): Localized => ({ es: value.es.trim(), en: value.en.trim() })
const copyLocalized = (value: Localized | null | undefined): Localized => ({ es: value?.es ?? '', en: value?.en ?? '' })

/** "Caracas, Valencia y Maracay" (or "… o …" with `disjunction`). */
export function listOf(items: string[], locale: string, type: 'conjunction' | 'disjunction' = 'conjunction'): string {
  try {
    return new Intl.ListFormat(locale, { style: 'long', type }).format(items)
  }
  catch {
    return items.join(', ')
  }
}

// ---- Maintenance and city pauses -------------------------------------------------------------------

export interface MaintenanceForm {
  /** `all` = every city (the API's empty `areas`). */
  scope: 'all' | 'areas'
  areas: string[]
  message: Localized
  /** `datetime-local` value, browser time ("" = no estimate). */
  eta: string
}

export interface PauseForm {
  area: string
  message: Localized
  eta: string
}

export function maintenanceFormFrom(m: Maintenance | null | undefined): MaintenanceForm {
  return {
    scope: m?.areas?.length ? 'areas' : 'all',
    areas: [...(m?.areas ?? [])],
    message: copyLocalized(m?.message),
    eta: toLocalInput(m?.eta),
  }
}

/** Form → API shape, with the switch set to `enabled`. Areas keep the catalogue order when it is given. */
export function maintenancePayload(form: MaintenanceForm, enabled: boolean, catalogue: string[] = []): Maintenance {
  const chosen = [...new Set(form.areas)]
  const ordered = [...catalogue.filter(a => chosen.includes(a)), ...chosen.filter(a => !catalogue.includes(a))]
  return {
    enabled,
    message: cleanLocalized(form.message),
    eta: fromLocalInput(form.eta),
    areas: form.scope === 'areas' ? ordered : [],
  }
}

/** Issue keys (i18n under `appStatus.errors`); empty when the form can be saved. */
export function validateMaintenance(form: MaintenanceForm): string[] {
  const issues: string[] = []
  if (!form.message.es.trim()) issues.push('messageEs')
  if (form.scope === 'areas' && !form.areas.length) issues.push('areas')
  if (form.scope === 'areas' && form.areas.length > AREA_MAX) issues.push('tooManyAreas')
  if (form.eta && !fromLocalInput(form.eta)) issues.push('eta')
  return issues
}

export function pauseFormFrom(p: AreaPause | null | undefined, area = ''): PauseForm {
  return { area: p?.area ?? area, message: copyLocalized(p?.message), eta: toLocalInput(p?.eta) }
}

export function pausePayload(form: PauseForm): AreaPause {
  return { area: form.area, message: cleanLocalized(form.message), eta: fromLocalInput(form.eta) }
}

/** `others` = the cities already paused, apart from the one being edited. */
export function validatePause(form: PauseForm, others: string[]): string[] {
  const issues: string[] = []
  if (!form.area) issues.push('area')
  else if (others.includes(form.area)) issues.push('duplicate')
  if (!form.message.es.trim()) issues.push('messageEs')
  if (form.eta && !fromLocalInput(form.eta)) issues.push('eta')
  return issues
}

/** Replaces the pause for `previous` (the city being edited) or adds a new one; one pause per city. */
export function upsertPause(pauses: AreaPause[], pause: AreaPause, previous: string | null = null): AreaPause[] {
  const key = previous ?? pause.area
  const next = pauses.filter(p => p.area !== pause.area || p.area === key)
  const index = next.findIndex(p => p.area === key)
  if (index < 0) return [...next, pause]
  next[index] = pause
  return next
}

// ---- Feature flags ---------------------------------------------------------------------------------

/** Rules as the API expects them: catalogue order, no duplicates, whole percent 0–100, no build 0. */
export function normalizeRules(rules: FlagRules): FlagRules {
  const percent = Number.isFinite(rules.percent) ? Math.round(rules.percent) : 100
  const build = rules.min_build === null || rules.min_build === undefined ? null : Math.floor(Number(rules.min_build))
  return {
    platforms: APP_PLATFORMS.filter(p => rules.platforms.includes(p)),
    min_build: build !== null && Number.isFinite(build) && build > 0 ? build : null,
    areas: [...new Set(rules.areas)],
    roles: APP_MODES.filter(r => rules.roles.includes(r)),
    percent: Math.min(100, Math.max(0, percent)),
  }
}

export function sameFlagState(a: { enabled: boolean, rules: FlagRules }, b: { enabled: boolean, rules: FlagRules }): boolean {
  return a.enabled === b.enabled && JSON.stringify(normalizeRules(a.rules)) === JSON.stringify(normalizeRules(b.rules))
}

/** "who" part of a summary: a single role, or everybody when the rule lists none (or both). */
function audienceWho(roles: AppMode[], t: Translate, prefix: string): string {
  const unique = [...new Set(roles)]
  return unique.length === 1 ? t(`${prefix}.${unique[0]}`) : t(`${prefix}.all`)
}

/**
 * Plain-language summary of who gets a flag, e.g. "20 % de los motorizados en Caracas con build ≥ 7".
 * Texts come from `flags.summary`.
 */
export function flagSummary(enabled: boolean, rules: FlagRules, t: Translate, locale: string): string {
  if (!enabled) return t('flags.summary.off')
  const r = normalizeRules(rules)
  if (r.percent === 0) return t('flags.summary.nobody')
  const who = audienceWho(r.roles, t, 'flags.summary.who')
  const parts = [r.percent < 100 ? t('flags.summary.percentOf', { percent: r.percent, who }) : who]
  if (r.areas.length) parts.push(t('flags.summary.inAreas', { areas: listOf(r.areas, locale) }))
  if (r.platforms.length && r.platforms.length < APP_PLATFORMS.length) {
    parts.push(t('flags.summary.onPlatforms', { platforms: listOf(r.platforms.map(p => PLATFORM_LABELS[p]), locale, 'disjunction') }))
  }
  if (r.min_build) parts.push(t('flags.summary.minBuild', { build: r.min_build }))
  return parts.join(' ')
}

// ---- Announcements ---------------------------------------------------------------------------------

export type AnnouncementStatus = 'scheduled' | 'active' | 'ended'

export function announcementStatus(a: { starts_at: string, ends_at: string }, now: Date = new Date()): AnnouncementStatus {
  const time = now.getTime()
  if (new Date(a.starts_at).getTime() > time) return 'scheduled'
  if (new Date(a.ends_at).getTime() <= time) return 'ended'
  return 'active'
}

/** "Motorizados en Caracas" / "Todos". Texts come from `announcements.audience`. */
export function audienceSummary(target: { roles: AppMode[], areas: string[] }, t: Translate, locale: string): string {
  const who = audienceWho(target.roles, t, 'announcements.audience')
  return target.areas.length ? t('announcements.audience.inAreas', { who, areas: listOf(target.areas, locale) }) : who
}

export interface AnnouncementForm {
  title: Localized
  body: Localized
  roles: AppMode[]
  areas: string[]
  style: AnnouncementStyle
  dismissible: boolean
  /** `datetime-local` values, browser time. */
  starts_at: string
  ends_at: string
  hasCta: boolean
  ctaLabel: Localized
  ctaKind: 'screen' | 'url'
  ctaUrl: string
  ctaScreen: AppScreen
}

/** Starts now and runs for a week. */
export function defaultAnnouncementForm(now: Date = new Date()): AnnouncementForm {
  const start = new Date(now)
  start.setSeconds(0, 0)
  const end = new Date(start)
  end.setDate(end.getDate() + 7)
  return {
    title: { es: '', en: '' },
    body: { es: '', en: '' },
    roles: [],
    areas: [],
    style: 'info',
    dismissible: true,
    starts_at: toLocalInput(start),
    ends_at: toLocalInput(end),
    hasCta: false,
    ctaLabel: { es: '', en: '' },
    ctaKind: 'screen',
    ctaUrl: 'https://',
    ctaScreen: 'home',
  }
}

export function announcementFormFrom(a: AnnouncementInput): AnnouncementForm {
  return {
    title: copyLocalized(a.title),
    body: copyLocalized(a.body),
    roles: [...(a.target?.roles ?? [])],
    areas: [...(a.target?.areas ?? [])],
    style: a.style,
    dismissible: a.dismissible,
    starts_at: toLocalInput(a.starts_at),
    ends_at: toLocalInput(a.ends_at),
    hasCta: !!a.cta,
    ctaLabel: copyLocalized(a.cta?.label),
    ctaKind: a.cta?.url ? 'url' : 'screen',
    ctaUrl: a.cta?.url ?? 'https://',
    ctaScreen: a.cta?.screen ?? 'home',
  }
}

export function announcementPayload(form: AnnouncementForm): AnnouncementInput {
  return {
    title: cleanLocalized(form.title),
    body: cleanLocalized(form.body),
    target: { roles: APP_MODES.filter(r => form.roles.includes(r)), areas: [...new Set(form.areas)] },
    cta: form.hasCta
      ? {
          label: cleanLocalized(form.ctaLabel),
          url: form.ctaKind === 'url' ? form.ctaUrl.trim() : null,
          screen: form.ctaKind === 'screen' ? form.ctaScreen : null,
        }
      : null,
    starts_at: fromLocalInput(form.starts_at) ?? '',
    ends_at: fromLocalInput(form.ends_at) ?? '',
    dismissible: form.dismissible,
    style: form.style,
  }
}

const HTTPS_URL = /^https:\/\/[^\s/]+\.[^\s]+$/

/** Issue keys (i18n under `announcements.errors`); empty when the form can be saved. */
export function validateAnnouncement(form: AnnouncementForm): string[] {
  const issues: string[] = []
  if (!form.title.es.trim()) issues.push('titleEs')
  const start = fromLocalInput(form.starts_at)
  const end = fromLocalInput(form.ends_at)
  if (!start || !end) issues.push('dates')
  else if (end <= start) issues.push('order')
  if (form.areas.length > AREA_MAX) issues.push('tooManyAreas')
  if (form.hasCta) {
    if (!form.ctaLabel.es.trim()) issues.push('ctaLabel')
    if (form.ctaKind === 'url' && (!HTTPS_URL.test(form.ctaUrl.trim()) || form.ctaUrl.trim().length > CTA_URL_MAX)) issues.push('ctaUrl')
  }
  return issues
}
