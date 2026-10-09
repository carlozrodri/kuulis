import type { AppConfig, DocumentKind, PaymentMethod, ServiceArea, VehicleType } from '~/types/api'
import { DOCUMENT_KINDS, PAYMENT_METHODS, VEHICLE_TYPES } from '~/types/api'

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
  service_area: ServiceArea
  offer_timeout_seconds: number
  search_radius_m: number[]
  search_timeout_seconds: number
  quote_ttl_seconds: number
}

export const FARE_FIELDS = ['base', 'per_km', 'per_minute', 'minimum'] as const
export const FARE_ROUNDINGS = ['0.01', '0.05', '0.10', '0.25', '0.50', '1.00']
export const SURGE_MIN = 1
export const SURGE_MAX = 3

/** Defaults from docs/api/phase-1a.md and phase-1b.md, used for keys an older API does not return yet. */
export function defaultSettings(): SettingsForm {
  return {
    driver_min_age: 21,
    vehicle_min_year: { moto: 2013, car: 1993 },
    enabled_vehicle_types: ['moto'],
    driver_required_documents: [...DOCUMENT_KINDS],
    vehicle_photo_min_count: 2,
    fares: {
      moto: { base: 0.8, per_km: 0.35, per_minute: 0.05, minimum: 1.5 },
      car: { base: 1.5, per_km: 0.6, per_minute: 0.08, minimum: 2.5 },
    },
    surge_rules: [],
    surge_manual_multiplier: 1,
    fare_rounding: '0.10',
    payment_methods: [...PAYMENT_METHODS],
    service_area: { min_lat: 10.35, max_lat: 10.56, min_lng: -67.1, max_lng: -66.7 },
    offer_timeout_seconds: 15,
    search_radius_m: [2000, 4000, 7000],
    search_timeout_seconds: 180,
    quote_ttl_seconds: 300,
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
    service_area: { ...d.service_area, ...config.service_area },
    offer_timeout_seconds: config.offer_timeout_seconds ?? d.offer_timeout_seconds,
    search_radius_m: [...(config.search_radius_m ?? d.search_radius_m)],
    search_timeout_seconds: config.search_timeout_seconds ?? d.search_timeout_seconds,
    quote_ttl_seconds: config.quote_ttl_seconds ?? d.quote_ttl_seconds,
  }
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
    service_area: {
      min_lat: Number(form.service_area.min_lat),
      max_lat: Number(form.service_area.max_lat),
      min_lng: Number(form.service_area.min_lng),
      max_lng: Number(form.service_area.max_lng),
    },
    offer_timeout_seconds: form.offer_timeout_seconds,
    search_radius_m: form.search_radius_m.map(Number),
    search_timeout_seconds: form.search_timeout_seconds,
    quote_ttl_seconds: form.quote_ttl_seconds,
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
  const a = form.service_area
  const coordsOk = [a.min_lat, a.max_lat].every(v => Number.isFinite(v) && Math.abs(v) <= 90)
    && [a.min_lng, a.max_lng].every(v => Number.isFinite(v) && Math.abs(v) <= 180)
  if (!coordsOk || a.min_lat >= a.max_lat || a.min_lng >= a.max_lng) issues.push({ key: 'serviceArea' })
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
  return issues
}
