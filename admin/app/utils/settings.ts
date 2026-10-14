import type { AppConfig, AppLinks, DocumentKind, LocationIntervals, NotificationSettings, PaymentMethod, QualitySettings, RateSource, SafetySettings, ServiceArea, SupportSettings, VehicleType, VerificationSettings } from '~/types/api'
import { DOCUMENT_KINDS, PAYMENT_METHODS, RATE_SOURCES, VEHICLE_TYPES } from '~/types/api'

/** Editable copy of AppConfig: decimals as numbers so they bind to numeric inputs. */
export interface FareForm { base: number, per_km: number, per_minute: number, minimum: number }
export interface SurgeRuleForm { days: number[], start: string, end: string, multiplier: number }

export interface SettingsForm {
  driver_min_age: number
  vehicle_min_year: Record<VehicleType, number>
  enabled_vehicle_types: VehicleType[]
  driver_required_documents: DocumentKind[]
  vehicle_photo_min_count: number
  fares: Record<VehicleType, FareForm>
  surge_rules: SurgeRuleForm[]
  surge_manual_multiplier: number
  fare_rounding: string
  payment_methods: PaymentMethod[]
  service_areas: ServiceArea[]
  offer_timeout_seconds: number
  search_radius_m: number[]
  search_timeout_seconds: number
  quote_ttl_seconds: number
  rates_stale_minutes: Record<RateSource, number>
  rates_manual_hold_hours: number
  promo_pair_alert_threshold: number
  promo_pair_alert_days: number
  topup_min_amount: number
  topup_binance_pay_id: string
  topup_account_name: string
  transfer_monthly_limit: number
  subscription_free_months: number
  subscription_grace_days: number
  approval_adjust_limit: number
  approval_fares: boolean
  approval_broadcasts: boolean
  app_links: AppLinks
  location_intervals: LocationIntervals
  safety: SafetySettings
  verification: VerificationSettings
  support: SupportSettings
  notifications: NotificationSettings
  /** Rates and the dispatch weight as percentages (15 = 0.15 in the API), see QUALITY_PERCENT_FIELDS. */
  quality: QualitySettings
}

export const FARE_FIELDS = ['base', 'per_km', 'per_minute', 'minimum'] as const
export const FARE_ROUNDINGS = ['0.01', '0.05', '0.10', '0.25', '0.50', '1.00']
export const SURGE_MIN = 1
export const SURGE_MAX = 3
/** Phase 1C limits (the contract states the hold window; the rest match the API validation). */
export const RATE_STALE_MIN = 5
export const RATE_STALE_MAX = 43_200
export const MANUAL_HOLD_MIN = 1
export const MANUAL_HOLD_MAX = 168
export const PAIR_THRESHOLD_MIN = 2
export const PAIR_THRESHOLD_MAX = 100
export const PAIR_DAYS_MIN = 1
export const PAIR_DAYS_MAX = 365
/** Phase 1D limits (the contract states the defaults and the Pay ID format; the ranges are panel guard rails). */
export const TOPUP_MIN_MIN = 1
export const TOPUP_MIN_MAX = 1000
export const BINANCE_PAY_ID = /^\d{6,20}$/
export const ACCOUNT_NAME_MAX = 60
export const TRANSFER_LIMIT_MAX = 10_000
export const APPROVAL_LIMIT_MAX = 1000
export const FREE_MONTHS_MAX = 24
export const GRACE_DAYS_MAX = 60
/** Doc 10 limits (contract). */
export const WHATSAPP = /^\+?\d{0,19}$/
export const EMERGENCY_NUMBER = /^\d{0,10}$/
export const LINK_MAX = 300
export const SUPPORT_EMAIL_MAX = 120
export const ONLINE_SECONDS_MIN = 2
export const ONLINE_SECONDS_MAX = 120
export const ON_RIDE_SECONDS_MIN = 1
export const ON_RIDE_SECONDS_MAX = 60
/** Doc 11: trip safety limits (same as the API validation). */
export const SAFETY_LIMITS = {
  stop_minutes: [2, 60],
  deviation_m: [100, 10_000],
  deviation_minutes: [1, 30],
  overtime_factor: [1.2, 10],
  check_in_seconds: [30, 900],
  sos_location_seconds: [2, 60],
} as const
/** Doc 12 limits (same as the API validation). */
export const VERIFICATION_LIMITS = {
  selfie_every_days: [0, 90],
  mismatch_reports: [1, 20],
  report_window_days: [1, 365],
} as const
export type VerificationNumber = keyof typeof VERIFICATION_LIMITS
export const VERIFICATION_NUMBERS = Object.keys(VERIFICATION_LIMITS) as VerificationNumber[]
/** Doc 13: support limits (same as the API validation). */
export const SUPPORT_LIMITS = {
  sla_urgent_minutes: [1, 1440],
  sla_normal_hours: [1, 336],
  auto_close_days: [1, 60],
  lost_item_days: [1, 30],
  lost_item_chat_hours: [1, 336],
} as const
export type SupportNumber = keyof typeof SUPPORT_LIMITS
export const SUPPORT_NUMBERS = Object.keys(SUPPORT_LIMITS) as SupportNumber[]
export const PROMISE_MAX = 120
/** Doc 14: notification limits (same as the API validation). */
export const NOTIFICATION_LIMITS = {
  marketing_daily_cap: [0, 10],
  inbox_retention_days: [7, 730],
  device_idle_days: [7, 365],
} as const
export type NotificationNumber = keyof typeof NOTIFICATION_LIMITS
export const NOTIFICATION_NUMBERS = Object.keys(NOTIFICATION_LIMITS) as NotificationNumber[]
export const NOTICE_DAYS_MAX = 120
export const NOTICE_DAYS_COUNT = 5
/** Doc 15: quality limits (same as the API validation; percentages here, fractions in the API). */
export const QUALITY_LIMITS = {
  pickup_wait_minutes: [1, 30],
  passenger_cancel_grace_s: [0, 900],
  window_days: [7, 180],
  driver_cancel_warn: [0, 100],
  driver_cancel_low_priority: [0, 100],
  driver_cancel_review: [0, 100],
  min_rides: [1, 200],
  rating_review_below: [1, 5],
  rating_min_count: [1, 500],
  driver_cancel_burst: [0, 20],
  driver_decline_streak: [0, 50],
  driver_pause_minutes: [1, 240],
  passenger_no_show_warn: [0, 50],
  passenger_no_show_pause: [0, 50],
  passenger_pause_hours: [1, 720],
  dispatch_quality_weight: [0, 100],
} as const
export type QualityNumber = keyof typeof QUALITY_LIMITS
export const QUALITY_PERCENT_FIELDS: QualityNumber[] = ['driver_cancel_warn', 'driver_cancel_low_priority', 'driver_cancel_review', 'dispatch_quality_weight']
/** How the settings card groups the fields. */
export const QUALITY_SECTIONS: { key: 'pickup' | 'drivers' | 'driverPauses' | 'passengers' | 'general', fields: QualityNumber[] }[] = [
  { key: 'pickup', fields: ['pickup_wait_minutes', 'passenger_cancel_grace_s'] },
  { key: 'drivers', fields: ['driver_cancel_warn', 'driver_cancel_low_priority', 'driver_cancel_review', 'min_rides', 'rating_review_below', 'rating_min_count'] },
  { key: 'driverPauses', fields: ['driver_cancel_burst', 'driver_decline_streak', 'driver_pause_minutes'] },
  { key: 'passengers', fields: ['passenger_no_show_warn', 'passenger_no_show_pause', 'passenger_pause_hours'] },
  { key: 'general', fields: ['window_days', 'dispatch_quality_weight'] },
]
// 0.15 ↔ 15, without float noise (0.07 * 100 = 7.000000000000001).
const toPercent = (fraction: number) => Math.round(fraction * 10_000) / 100
const fromPercent = (percent: number) => Math.round(Number(percent) * 100) / 10_000

/** Selfie and moto photos are taken on the spot: they never expire nor are optional. */
export const PAPER_DOCUMENTS: DocumentKind[] = DOCUMENT_KINDS.filter(k => k !== 'selfie' && k !== 'vehicle_photo')

/** "30, 7, 1" → [30, 7, 1]; null when something is not a whole number. */
export function parseNoticeDays(text: string): number[] | null {
  const parts = text.split(/[\s,;]+/).filter(Boolean)
  if (!parts.every(p => /^\d+$/.test(p))) return null
  return parts.map(Number)
}
export type SafetyNumber = keyof typeof SAFETY_LIMITS
export const SAFETY_NUMBERS = Object.keys(SAFETY_LIMITS) as SafetyNumber[]

/** Defaults from docs/api/phase-1a.md, phase-1b.md and phase-1c.md, used for keys an older API does not return yet. */
export function defaultSettings(): SettingsForm {
  return {
    driver_min_age: 21,
    vehicle_min_year: { moto: 2013, car: 1993 },
    enabled_vehicle_types: ['moto'],
    driver_required_documents: DOCUMENT_KINDS.filter(k => k !== 'criminal_record'),
    vehicle_photo_min_count: 2,
    fares: {
      moto: { base: 0.8, per_km: 0.35, per_minute: 0.05, minimum: 1.5 },
      car: { base: 1.5, per_km: 0.6, per_minute: 0.08, minimum: 2.5 },
    },
    surge_rules: [],
    surge_manual_multiplier: 1,
    fare_rounding: '0.10',
    payment_methods: [...PAYMENT_METHODS],
    service_areas: [{ name: 'Caracas', min_lat: 10.35, max_lat: 10.56, min_lng: -67.1, max_lng: -66.7 }],
    offer_timeout_seconds: 15,
    search_radius_m: [2000, 4000, 7000],
    search_timeout_seconds: 180,
    quote_ttl_seconds: 300,
    rates_stale_minutes: { bcv: 2160, binance: 120 },
    rates_manual_hold_hours: 6,
    promo_pair_alert_threshold: 3,
    promo_pair_alert_days: 30,
    topup_min_amount: 5,
    topup_binance_pay_id: '',
    topup_account_name: 'Kuulis',
    transfer_monthly_limit: 50,
    subscription_free_months: 3,
    subscription_grace_days: 7,
    approval_adjust_limit: 20,
    approval_fares: true,
    approval_broadcasts: true,
    app_links: { support_whatsapp: '', support_email: '', emergency_number: '911', terms_url: '', privacy_url: '' },
    location_intervals: { online_seconds: 10, on_ride_seconds: 4 },
    safety: {
      pin_areas: ['Caracas'],
      passenger_photo: 'night',
      night_start: '19:00',
      night_end: '06:00',
      stop_minutes: 10,
      deviation_m: 600,
      deviation_minutes: 3,
      overtime_factor: 2,
      check_in_seconds: 120,
      sos_location_seconds: 5,
      sos_team_alert: false,
    },
    verification: {
      expiring_documents: ['drivers_license', 'medical_certificate', 'vehicle_registration'],
      optional_documents: ['criminal_record'],
      expiry_notice_days: [30, 7, 1],
      selfie_every_days: 7,
      mismatch_reports: 2,
      report_window_days: 30,
      induction_required: false,
    },
    support: {
      sla_urgent_minutes: 15,
      sla_normal_hours: 24,
      response_promise_es: 'Respondemos en menos de 24 horas.',
      response_promise_en: 'We answer within 24 hours.',
      auto_close_days: 7,
      auto_assign: false,
      lost_item_days: 7,
      lost_item_chat_hours: 72,
    },
    notifications: {
      quiet_start: '21:00',
      quiet_end: '08:00',
      marketing_daily_cap: 1,
      inbox_retention_days: 90,
      device_idle_days: 60,
      monthly_summary: true,
    },
    quality: {
      pickup_wait_minutes: 5,
      passenger_cancel_grace_s: 120,
      window_days: 30,
      driver_cancel_burst: 3,
      driver_decline_streak: 5,
      driver_pause_minutes: 15,
      driver_cancel_warn: 15,
      driver_cancel_low_priority: 25,
      driver_cancel_review: 35,
      min_rides: 10,
      passenger_no_show_warn: 2,
      passenger_no_show_pause: 3,
      passenger_pause_hours: 24,
      rating_review_below: 4.3,
      rating_min_count: 20,
      dispatch_quality_weight: 20,
    },
  }
}

const num = (value: unknown, fallback: number) => {
  const n = Number(value)
  return value !== null && value !== undefined && value !== '' && Number.isFinite(n) ? n : fallback
}
const money = (value: number | null | undefined) => (Number.isFinite(value) ? Number(value) : 0).toFixed(2)

export function settingsFromConfig(config: AppConfig): SettingsForm {
  const d = defaultSettings()
  const fares = { ...d.fares }
  for (const type of VEHICLE_TYPES) {
    const fare = config.fares?.[type]
    if (fare) {
      fares[type] = {
        base: num(fare.base, d.fares[type].base),
        per_km: num(fare.per_km, d.fares[type].per_km),
        per_minute: num(fare.per_minute, d.fares[type].per_minute),
        minimum: num(fare.minimum, d.fares[type].minimum),
      }
    }
  }
  const rounding = config.fare_rounding !== undefined ? num(config.fare_rounding, 0.1).toFixed(2) : d.fare_rounding
  return {
    driver_min_age: config.driver_min_age,
    vehicle_min_year: { ...d.vehicle_min_year, ...config.vehicle_min_year },
    enabled_vehicle_types: [...config.enabled_vehicle_types],
    driver_required_documents: [...config.driver_required_documents],
    vehicle_photo_min_count: config.vehicle_photo_min_count,
    fares,
    surge_rules: (config.surge_rules ?? []).map(rule => ({
      days: [...rule.days].sort((a, b) => a - b),
      start: rule.start.slice(0, 5),
      end: rule.end.slice(0, 5),
      multiplier: num(rule.multiplier, 1),
    })),
    surge_manual_multiplier: num(config.surge_manual_multiplier, d.surge_manual_multiplier),
    fare_rounding: rounding,
    payment_methods: [...(config.payment_methods ?? d.payment_methods)],
    service_areas: (config.service_areas?.length ? config.service_areas : d.service_areas).map(area => ({ ...area })),
    offer_timeout_seconds: config.offer_timeout_seconds ?? d.offer_timeout_seconds,
    search_radius_m: [...(config.search_radius_m ?? d.search_radius_m)],
    search_timeout_seconds: config.search_timeout_seconds ?? d.search_timeout_seconds,
    quote_ttl_seconds: config.quote_ttl_seconds ?? d.quote_ttl_seconds,
    rates_stale_minutes: {
      bcv: num(config.rates_stale_minutes?.bcv, d.rates_stale_minutes.bcv),
      binance: num(config.rates_stale_minutes?.binance, d.rates_stale_minutes.binance),
    },
    rates_manual_hold_hours: num(config.rates_manual_hold_hours, d.rates_manual_hold_hours),
    promo_pair_alert_threshold: num(config.promo_pair_alert_threshold, d.promo_pair_alert_threshold),
    promo_pair_alert_days: num(config.promo_pair_alert_days, d.promo_pair_alert_days),
    topup_min_amount: num(config.topup_min_amount, d.topup_min_amount),
    topup_binance_pay_id: config.topup_binance_pay_id ?? d.topup_binance_pay_id,
    topup_account_name: config.topup_account_name ?? d.topup_account_name,
    transfer_monthly_limit: num(config.transfer_monthly_limit, d.transfer_monthly_limit),
    subscription_free_months: num(config.subscription_free_months, d.subscription_free_months),
    subscription_grace_days: num(config.subscription_grace_days, d.subscription_grace_days),
    approval_adjust_limit: num(config.approval_adjust_limit, d.approval_adjust_limit),
    approval_fares: config.approval_fares ?? d.approval_fares,
    approval_broadcasts: config.approval_broadcasts ?? d.approval_broadcasts,
    app_links: { ...d.app_links, ...config.app_links },
    location_intervals: {
      online_seconds: num(config.location_intervals?.online_seconds, d.location_intervals.online_seconds),
      on_ride_seconds: num(config.location_intervals?.on_ride_seconds, d.location_intervals.on_ride_seconds),
    },
    safety: { ...d.safety, ...config.safety, pin_areas: [...(config.safety?.pin_areas ?? d.safety.pin_areas)] },
    verification: {
      ...d.verification,
      ...config.verification,
      expiring_documents: [...(config.verification?.expiring_documents ?? d.verification.expiring_documents)],
      optional_documents: [...(config.verification?.optional_documents ?? d.verification.optional_documents)],
      expiry_notice_days: [...(config.verification?.expiry_notice_days ?? d.verification.expiry_notice_days)],
    },
    support: { ...d.support, ...config.support },
    notifications: { ...d.notifications, ...config.notifications },
    quality: qualityFromConfig(config.quality, d.quality),
  }
}

function qualityFromConfig(quality: Partial<QualitySettings> | undefined, defaults: QualitySettings): QualitySettings {
  const form = { ...defaults }
  for (const key of Object.keys(QUALITY_LIMITS) as QualityNumber[]) {
    const value = quality?.[key]
    if (value === undefined || value === null) continue
    form[key] = QUALITY_PERCENT_FIELDS.includes(key) ? toPercent(num(value, 0)) : num(value, defaults[key])
  }
  return form
}

/** Serializes the form back to the API shape (decimals as 2-decimal strings, lists in catalogue order). */
export function settingsToPayload(form: SettingsForm): Required<AppConfig> {
  const fares = {} as Record<VehicleType, { base: string, per_km: string, per_minute: string, minimum: string }>
  for (const type of VEHICLE_TYPES) {
    const fare = form.fares[type]
    fares[type] = { base: money(fare.base), per_km: money(fare.per_km), per_minute: money(fare.per_minute), minimum: money(fare.minimum) }
  }
  return {
    driver_min_age: form.driver_min_age,
    vehicle_min_year: { ...form.vehicle_min_year },
    enabled_vehicle_types: VEHICLE_TYPES.filter(v => form.enabled_vehicle_types.includes(v)),
    driver_required_documents: DOCUMENT_KINDS.filter(k => form.driver_required_documents.includes(k)),
    vehicle_photo_min_count: form.vehicle_photo_min_count,
    fares,
    surge_rules: form.surge_rules.map(rule => ({
      days: [...new Set(rule.days)].sort((a, b) => a - b),
      start: rule.start,
      end: rule.end,
      multiplier: money(rule.multiplier),
    })),
    surge_manual_multiplier: money(form.surge_manual_multiplier),
    fare_rounding: form.fare_rounding,
    payment_methods: PAYMENT_METHODS.filter(m => form.payment_methods.includes(m)),
    service_areas: form.service_areas.map(area => ({
      name: area.name.trim(),
      min_lat: Number(area.min_lat),
      max_lat: Number(area.max_lat),
      min_lng: Number(area.min_lng),
      max_lng: Number(area.max_lng),
    })),
    offer_timeout_seconds: form.offer_timeout_seconds,
    search_radius_m: form.search_radius_m.map(Number),
    search_timeout_seconds: form.search_timeout_seconds,
    quote_ttl_seconds: form.quote_ttl_seconds,
    rates_stale_minutes: Object.fromEntries(RATE_SOURCES.map(s => [s, form.rates_stale_minutes[s]])) as Record<RateSource, number>,
    rates_manual_hold_hours: form.rates_manual_hold_hours,
    promo_pair_alert_threshold: form.promo_pair_alert_threshold,
    promo_pair_alert_days: form.promo_pair_alert_days,
    topup_min_amount: money(form.topup_min_amount),
    topup_binance_pay_id: form.topup_binance_pay_id.replace(/\s+/g, ''),
    topup_account_name: form.topup_account_name.trim(),
    transfer_monthly_limit: money(form.transfer_monthly_limit),
    subscription_free_months: form.subscription_free_months,
    subscription_grace_days: form.subscription_grace_days,
    approval_adjust_limit: money(form.approval_adjust_limit),
    approval_fares: form.approval_fares,
    approval_broadcasts: form.approval_broadcasts,
    app_links: {
      support_whatsapp: form.app_links.support_whatsapp.replace(/[\s-]+/g, ''),
      support_email: form.app_links.support_email.trim(),
      emergency_number: form.app_links.emergency_number.replace(/\s+/g, ''),
      terms_url: form.app_links.terms_url.trim(),
      privacy_url: form.app_links.privacy_url.trim(),
    },
    location_intervals: { ...form.location_intervals },
    safety: {
      ...form.safety,
      // In the order of the cities list, and only cities that still exist.
      pin_areas: form.service_areas.map(a => a.name.trim()).filter(name => form.safety.pin_areas.includes(name)),
      overtime_factor: Math.round(Number(form.safety.overtime_factor) * 10) / 10,
    },
    verification: {
      ...form.verification,
      expiring_documents: DOCUMENT_KINDS.filter(k => form.verification.expiring_documents.includes(k)),
      optional_documents: DOCUMENT_KINDS.filter(k => form.verification.optional_documents.includes(k)),
      // The API keeps them unique and from the earliest notice to the last one.
      expiry_notice_days: [...new Set(form.verification.expiry_notice_days.map(Number))].sort((a, b) => b - a),
    },
    support: {
      ...form.support,
      response_promise_es: form.support.response_promise_es.trim(),
      response_promise_en: form.support.response_promise_en.trim(),
    },
    notifications: { ...form.notifications },
    quality: Object.fromEntries((Object.keys(QUALITY_LIMITS) as QualityNumber[]).map((key) => {
      const value = Number(form.quality[key])
      if (QUALITY_PERCENT_FIELDS.includes(key)) return [key, fromPercent(value)]
      return [key, key === 'rating_review_below' ? Math.round(value * 10) / 10 : value]
    })) as unknown as QualitySettings,
  }
}

/** Top-level keys whose value changed, so a save only PATCHes what the admin touched. */
export function changedSettings(current: Required<AppConfig>, original: Required<AppConfig>): Partial<AppConfig> {
  const patch: Record<string, unknown> = {}
  for (const key of Object.keys(current) as (keyof AppConfig)[]) {
    if (JSON.stringify(current[key]) !== JSON.stringify(original[key])) patch[key] = current[key]
  }
  return patch as Partial<AppConfig>
}

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/

export interface SettingsIssue { key: string, params?: Record<string, string | number> }

/** Client-side checks mirroring the contract; the API validates again. Returns i18n keys under settings.errors. */
export function validateSettings(form: SettingsForm): SettingsIssue[] {
  const issues: SettingsIssue[] = []
  if (!form.enabled_vehicle_types.length) issues.push({ key: 'needVehicleType' })
  for (const type of VEHICLE_TYPES) {
    const fare = form.fares[type]
    if (FARE_FIELDS.some(f => !Number.isFinite(fare[f]) || fare[f] < 0)) issues.push({ key: 'fareInvalid', params: { type } })
  }
  form.surge_rules.forEach((rule, index) => {
    const n = index + 1
    if (!rule.days.length) issues.push({ key: 'surgeDays', params: { n } })
    if (!TIME.test(rule.start) || !TIME.test(rule.end)) issues.push({ key: 'surgeTime', params: { n } })
    else if (rule.start === rule.end) issues.push({ key: 'surgeSameTime', params: { n } })
    if (!(rule.multiplier >= SURGE_MIN && rule.multiplier <= SURGE_MAX)) issues.push({ key: 'surgeMultiplier', params: { n } })
  })
  if (!(form.surge_manual_multiplier >= SURGE_MIN && form.surge_manual_multiplier <= SURGE_MAX)) issues.push({ key: 'manualMultiplier' })
  if (form.surge_rules.length > 50) issues.push({ key: 'surgeTooMany' })
  if (!form.payment_methods.length) issues.push({ key: 'paymentMethods' })
  if (!form.service_areas.length || form.service_areas.length > 20) issues.push({ key: 'serviceAreaCount' })
  form.service_areas.forEach((a, index) => {
    const coordsOk = [a.min_lat, a.max_lat].every(v => Number.isFinite(v) && Math.abs(v) <= 90)
      && [a.min_lng, a.max_lng].every(v => Number.isFinite(v) && Math.abs(v) <= 180)
    if (!a.name.trim() || !coordsOk || a.min_lat >= a.max_lat || a.min_lng >= a.max_lng) {
      issues.push({ key: 'serviceArea', params: { name: a.name.trim() || String(index + 1) } })
    }
  })
  const radii = form.search_radius_m
  if (!radii.length || radii.length > 6 || radii.some(r => !Number.isFinite(r) || r < 100 || r > 50_000) || radii.some((r, i) => i > 0 && r <= radii[i - 1]!)) {
    issues.push({ key: 'radii' })
  }
  if ([form.offer_timeout_seconds, form.search_timeout_seconds, form.quote_ttl_seconds].some(v => !Number.isFinite(v) || v <= 0)) {
    issues.push({ key: 'timeouts' })
  }
  else if (form.search_timeout_seconds < form.offer_timeout_seconds) {
    issues.push({ key: 'searchShorterThanOffer' })
  }
  const between = (v: number, min: number, max: number) => Number.isInteger(v) && v >= min && v <= max
  if (RATE_SOURCES.some(s => !between(form.rates_stale_minutes[s], RATE_STALE_MIN, RATE_STALE_MAX))) {
    issues.push({ key: 'ratesStale', params: { min: RATE_STALE_MIN, max: RATE_STALE_MAX } })
  }
  if (!between(form.rates_manual_hold_hours, MANUAL_HOLD_MIN, MANUAL_HOLD_MAX)) {
    issues.push({ key: 'manualHold', params: { min: MANUAL_HOLD_MIN, max: MANUAL_HOLD_MAX } })
  }
  if (!between(form.promo_pair_alert_threshold, PAIR_THRESHOLD_MIN, PAIR_THRESHOLD_MAX)) {
    issues.push({ key: 'pairThreshold', params: { min: PAIR_THRESHOLD_MIN, max: PAIR_THRESHOLD_MAX } })
  }
  if (!between(form.promo_pair_alert_days, PAIR_DAYS_MIN, PAIR_DAYS_MAX)) {
    issues.push({ key: 'pairDays', params: { min: PAIR_DAYS_MIN, max: PAIR_DAYS_MAX } })
  }
  if (!(Number.isFinite(form.topup_min_amount) && form.topup_min_amount >= TOPUP_MIN_MIN && form.topup_min_amount <= TOPUP_MIN_MAX)) {
    issues.push({ key: 'topupMin', params: { min: TOPUP_MIN_MIN, max: TOPUP_MIN_MAX } })
  }
  const payId = form.topup_binance_pay_id.replace(/\s+/g, '')
  if (payId && !BINANCE_PAY_ID.test(payId)) issues.push({ key: 'binancePayId' })
  const accountName = form.topup_account_name.trim()
  if (!accountName || accountName.length > ACCOUNT_NAME_MAX) issues.push({ key: 'accountName', params: { max: ACCOUNT_NAME_MAX } })
  if (!(Number.isFinite(form.transfer_monthly_limit) && form.transfer_monthly_limit >= 0 && form.transfer_monthly_limit <= TRANSFER_LIMIT_MAX)) {
    issues.push({ key: 'transferLimit', params: { max: TRANSFER_LIMIT_MAX } })
  }
  if (!between(form.subscription_free_months, 0, FREE_MONTHS_MAX)) {
    issues.push({ key: 'freeMonths', params: { min: 0, max: FREE_MONTHS_MAX } })
  }
  if (!between(form.subscription_grace_days, 0, GRACE_DAYS_MAX)) {
    issues.push({ key: 'graceDays', params: { min: 0, max: GRACE_DAYS_MAX } })
  }
  if (!(Number.isFinite(form.approval_adjust_limit) && form.approval_adjust_limit >= 0 && form.approval_adjust_limit <= APPROVAL_LIMIT_MAX)) {
    issues.push({ key: 'approvalLimit', params: { max: APPROVAL_LIMIT_MAX } })
  }
  const links = form.app_links
  if (!WHATSAPP.test(links.support_whatsapp.replace(/[\s-]+/g, ''))) issues.push({ key: 'whatsapp' })
  const email = links.support_email.trim()
  if (email && (email.length > SUPPORT_EMAIL_MAX || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))) issues.push({ key: 'supportEmail' })
  if (!EMERGENCY_NUMBER.test(links.emergency_number.replace(/\s+/g, ''))) issues.push({ key: 'emergencyNumber' })
  for (const key of ['terms_url', 'privacy_url'] as const) {
    const url = links[key].trim()
    if (url && (url.length > LINK_MAX || !/^https?:\/\/\S+$/.test(url))) issues.push({ key: key === 'terms_url' ? 'termsUrl' : 'privacyUrl' })
  }
  if (!between(form.location_intervals.online_seconds, ONLINE_SECONDS_MIN, ONLINE_SECONDS_MAX)) {
    issues.push({ key: 'onlineSeconds', params: { min: ONLINE_SECONDS_MIN, max: ONLINE_SECONDS_MAX } })
  }
  if (!between(form.location_intervals.on_ride_seconds, ON_RIDE_SECONDS_MIN, ON_RIDE_SECONDS_MAX)) {
    issues.push({ key: 'onRideSeconds', params: { min: ON_RIDE_SECONDS_MIN, max: ON_RIDE_SECONDS_MAX } })
  }
  if (!TIME.test(form.safety.night_start) || !TIME.test(form.safety.night_end) || form.safety.night_start === form.safety.night_end) {
    issues.push({ key: 'nightHours' })
  }
  for (const key of SAFETY_NUMBERS) {
    const [min, max] = SAFETY_LIMITS[key]
    const value = Number(form.safety[key])
    if (!(Number.isFinite(value) && value >= min && value <= max)) issues.push({ key: 'safetyNumber', params: { min, max } })
  }
  const notice = form.verification.expiry_notice_days
  if (notice.length > NOTICE_DAYS_COUNT || notice.some(d => !between(Number(d), 1, NOTICE_DAYS_MAX))) {
    issues.push({ key: 'noticeDays', params: { max: NOTICE_DAYS_MAX, count: NOTICE_DAYS_COUNT } })
  }
  for (const key of VERIFICATION_NUMBERS) {
    const [min, max] = VERIFICATION_LIMITS[key]
    if (!between(Number(form.verification[key]), min, max)) issues.push({ key: 'verificationNumber', params: { min, max } })
  }
  for (const key of SUPPORT_NUMBERS) {
    const [min, max] = SUPPORT_LIMITS[key]
    if (!between(Number(form.support[key]), min, max)) issues.push({ key: 'supportNumber', params: { min, max } })
  }
  if ([form.support.response_promise_es, form.support.response_promise_en].some(text => text.trim().length > PROMISE_MAX)) {
    issues.push({ key: 'supportPromise', params: { max: PROMISE_MAX } })
  }
  // Equal start and end is allowed: it means no default quiet hours.
  if (!TIME.test(form.notifications.quiet_start) || !TIME.test(form.notifications.quiet_end)) {
    issues.push({ key: 'quietHours' })
  }
  for (const key of NOTIFICATION_NUMBERS) {
    const [min, max] = NOTIFICATION_LIMITS[key]
    if (!between(Number(form.notifications[key]), min, max)) {
      issues.push({ key: 'notificationNumber', params: { min, max } })
    }
  }
  for (const key of Object.keys(QUALITY_LIMITS) as QualityNumber[]) {
    const [min, max] = QUALITY_LIMITS[key]
    const value = Number(form.quality[key])
    // The rating threshold and the percentages may have decimals; the rest are whole numbers.
    const ok = key === 'rating_review_below' || QUALITY_PERCENT_FIELDS.includes(key) ? Number.isFinite(value) && value >= min && value <= max : between(value, min, max)
    if (!ok) {
      issues.push({ key: 'qualityNumber', params: { min, max } })
      break
    }
  }
  const q = form.quality
  if (!(q.driver_cancel_warn <= q.driver_cancel_low_priority && q.driver_cancel_low_priority <= q.driver_cancel_review)) {
    issues.push({ key: 'qualityCancelOrder' })
  }
  if (q.passenger_no_show_pause && q.passenger_no_show_warn > q.passenger_no_show_pause) {
    issues.push({ key: 'qualityNoShowOrder' })
  }
  return issues
}
