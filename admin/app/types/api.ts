export type Role = 'user' | 'staff' | 'admin'

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  locale: string
  avatar_key: string | null
  is_active: boolean
  is_verified: boolean
  created_at: string
  last_login_at: string | null
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface UserStats {
  total: number
  active: number
  verified: number
  by_role: Record<Role, number>
}

export interface ApiErrorBody {
  error: { code: string, message: string, details?: unknown }
}

// ---- Phase 1A: drivers & app configuration (docs/api/phase-1a.md) ----

export type DriverStatus = 'draft' | 'pending_review' | 'approved' | 'rejected' | 'suspended'
export type DocumentKind
  = | 'id_card'
    | 'rif'
    | 'drivers_license'
    | 'medical_certificate'
    | 'vehicle_registration'
    | 'selfie'
    | 'vehicle_photo'
export type DocumentStatus = 'pending' | 'approved' | 'rejected'
export type VehicleType = 'moto' | 'car'

export const DRIVER_STATUSES: DriverStatus[] = ['pending_review', 'approved', 'rejected', 'suspended', 'draft']
export const DOCUMENT_KINDS: DocumentKind[] = [
  'id_card',
  'rif',
  'drivers_license',
  'medical_certificate',
  'vehicle_registration',
  'selfie',
  'vehicle_photo',
]
export const VEHICLE_TYPES: VehicleType[] = ['moto', 'car']

export interface Vehicle {
  id: string
  type: VehicleType
  brand: string
  model: string
  year: number
  plate: string
  color: string
}

export interface DriverDocument {
  id: string
  kind: DocumentKind
  status: DocumentStatus
  content_type: string
  rejection_reason: string | null
  created_at: string
  /** Signed, short-lived URL. Only present on the admin detail endpoint. */
  download_url?: string | null
}

export interface DriverRequirements {
  missing_documents: DocumentKind[]
  vehicle_photos: number
  vehicle_photos_required: number
  age_ok: boolean
  vehicle_ok: boolean
  can_submit: boolean
}

export interface DriverProfile {
  id: string
  user_id: string
  status: DriverStatus
  birth_date: string | null
  national_id: string | null
  rif: string | null
  phone: string | null
  city: string | null
  rejection_reason: string | null
  submitted_at: string | null
  reviewed_at: string | null
  approved_at: string | null
  vehicle: Vehicle | null
  documents: DriverDocument[]
  requirements: DriverRequirements
}

/** Shape returned by GET /admin/drivers (items) and GET /admin/drivers/{id}. */
export interface AdminDriver extends DriverProfile {
  user: Pick<User, 'id' | 'email' | 'full_name'> & Partial<User>
  /** Phase 1B: average rating received as a driver (decimal string or number) and how many ratings. */
  rating_avg?: number | string | null
  rating_count?: number | null
}

export interface AppConfig {
  driver_min_age: number
  vehicle_min_year: Record<VehicleType, number>
  enabled_vehicle_types: VehicleType[]
  driver_required_documents: DocumentKind[]
  vehicle_photo_min_count: number
  // ---- Phase 1B (docs/api/phase-1b.md). Optional so the panel still loads against an older API. ----
  fares?: Partial<Record<VehicleType, Fare>>
  surge_rules?: SurgeRule[]
  surge_manual_multiplier?: string
  fare_rounding?: string
  payment_methods?: PaymentMethod[]
  service_areas?: ServiceArea[]
  offer_timeout_seconds?: number
  search_radius_m?: number[]
  search_timeout_seconds?: number
  quote_ttl_seconds?: number
  // ---- Phase 1C (docs/api/phase-1c.md). Optional so the panel still loads against an older API. ----
  rates_stale_minutes?: Partial<Record<RateSource, number>>
  rates_manual_hold_hours?: number
  promo_pair_alert_threshold?: number
  promo_pair_alert_days?: number
}

// ---- Phase 1B: rides (docs/api/phase-1b.md) ----

/** Decimal amounts travel as strings ("2.40") so they never lose precision. */
export type Decimal = string

export interface Fare {
  base: Decimal
  per_km: Decimal
  per_minute: Decimal
  minimum: Decimal
}

export interface SurgeRule {
  /** 0 = Monday … 6 = Sunday, Caracas time. */
  days: number[]
  start: string
  end: string
  multiplier: Decimal
}

export interface ServiceArea {
  name: string
  min_lat: number
  max_lat: number
  min_lng: number
  max_lng: number
}

export type PaymentMethod = 'cash_usd' | 'pago_movil' | 'binance' | 'zelle' | 'cash_ves'
export const PAYMENT_METHODS: PaymentMethod[] = ['cash_usd', 'pago_movil', 'binance', 'zelle', 'cash_ves']

export type RideStatus
  = | 'searching'
    | 'driver_assigned'
    | 'driver_arrived'
    | 'in_progress'
    | 'completed'
    | 'cancelled_by_passenger'
    | 'cancelled_by_driver'
    | 'cancelled_by_admin'
    | 'no_drivers'

export const RIDE_STATUSES: RideStatus[] = [
  'searching',
  'driver_assigned',
  'driver_arrived',
  'in_progress',
  'completed',
  'cancelled_by_passenger',
  'cancelled_by_driver',
  'cancelled_by_admin',
  'no_drivers',
]
export const ACTIVE_RIDE_STATUSES: RideStatus[] = ['searching', 'driver_assigned', 'driver_arrived', 'in_progress']

export interface Place {
  lat: number
  lng: number
  address: string | null
}

export interface RidePassenger {
  id: string
  first_name: string | null
  rating: number | string | null
  /** Admin endpoints may add contact details. */
  full_name?: string | null
  email?: string | null
  phone?: string | null
}

export interface RideDriver {
  id: string
  first_name: string | null
  rating: number | string | null
  photo_url: string | null
  vehicle: { brand: string, model: string, color: string, plate: string } | null
  /** `id` is the driver's user id; profile_id (for /drivers/{id}) when the admin API includes it. */
  profile_id?: string | null
  full_name?: string | null
  email?: string | null
  phone?: string | null
}

export interface DriverLocation {
  lat: number
  lng: number
  heading: number | null
}

export interface RideRating {
  id?: string
  rater_id?: string
  ratee_id?: string
  /** Who gave the rating. */
  rater_role?: 'passenger' | 'driver'
  stars: number
  tags: string[]
  comment: string | null
  created_at?: string
}

export interface Ride {
  id: string
  status: RideStatus
  vehicle_type: VehicleType
  pickup: Place
  dropoff: Place
  distance_m: number | null
  duration_s: number | null
  fare: Decimal
  surge_multiplier: Decimal
  payment_method: PaymentMethod
  /** Encoded polyline (Google/OSRM format, precision 5) or null when the route was estimated. */
  polyline: string | null
  passenger: RidePassenger
  driver: RideDriver | null
  driver_location: DriverLocation | null
  requested_at: string
  assigned_at: string | null
  arrived_at: string | null
  started_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  cancel_reason: string | null
  my_rating?: RideRating | null
  // ---- Phase 1C. Optional so the panel still works against an older API. ----
  /** What Kuulis pays the driver on completion; the passenger pays `total = fare − discount`. */
  discount?: Decimal
  total?: Decimal
  promotion?: PromotionRef | null
  /** Rates frozen when the ride was requested (Bs per 1 USD). */
  rates?: Record<RateSource, Decimal | null> | null
  total_ves?: VesAmount | null
}

export interface RideMessage {
  id: string
  ride_id: string
  sender_id: string
  text: string
  created_at: string
}

export type OfferStatus = 'pending' | 'accepted' | 'declined' | 'expired' | 'cancelled'

export interface RideOffer {
  id?: string
  /** Driver's user id. */
  driver_id: string
  driver_profile_id?: string | null
  driver_name?: string | null
  status: OfferStatus | string
  pickup_distance_m?: number | null
  pickup_eta_s?: number | null
  created_at?: string | null
  sent_at?: string | null
  responded_at?: string | null
  expires_at?: string | null
}

/** GET /admin/rides/{id}: the ride plus chat, ratings and offer history. */
export interface AdminRide extends Ride {
  messages?: RideMessage[]
  ratings?: RideRating[]
  offers?: RideOffer[]
}

/** GET /admin/drivers/online. */
export interface OnlineDriver {
  /** Driver's user id. */
  driver_id: string
  driver_profile_id?: string | null
  name: string | null
  lat: number
  lng: number
  last_seen_at: string | null
  active_ride_id: string | null
}

// ---- Phase 1C: exchange rates & promotions (docs/api/phase-1c.md) ----

export type RateSource = 'bcv' | 'binance'
export const RATE_SOURCES: RateSource[] = ['bcv', 'binance']
export type RateOrigin = 'auto' | 'manual'

export interface ExchangeRate {
  source: RateSource
  /** Bs per 1 USD, 2 decimals. */
  rate: Decimal
  origin: RateOrigin
  /** Date of the rate according to the source. */
  as_of: string
  /** When Kuulis stored it. */
  fetched_at: string
  /** Older than rates_stale_minutes[source]. */
  stale: boolean
}

/** GET /rates and POST /admin/rates/refresh. */
export type CurrentRates = Record<RateSource, ExchangeRate | null>

/** Amount in bolívares per rate source (null when that rate is missing). */
export type VesAmount = Record<RateSource, Decimal | null>

/** GET /admin/rates/history items. */
export interface RateHistoryEntry {
  id: string
  source: RateSource
  rate: Decimal
  origin: RateOrigin
  as_of: string
  fetched_at: string
  created_by: { id: string, name: string | null } | null
  note: string | null
}

export type PromotionStatus = 'active' | 'scheduled' | 'ended' | 'exhausted' | 'inactive'
export const PROMOTION_STATUSES: PromotionStatus[] = ['active', 'scheduled', 'ended', 'exhausted', 'inactive']
export type DiscountType = 'percent' | 'fixed'

export interface PromotionRef {
  id: string
  name: string
  code: string | null
}

export interface PromotionStats {
  /** Rides in progress plus completed. */
  uses: number
  completed: number
  credited: Decimal
  reserved: Decimal
  remaining: Decimal
}

export interface Promotion {
  id: string
  name: string
  description: string | null
  /** null = automatic promotion (applies without a code). */
  code: string | null
  discount_type: DiscountType
  discount_value: Decimal
  max_discount: Decimal | null
  min_fare: Decimal
  starts_at: string
  ends_at: string
  budget: Decimal
  max_uses_per_passenger: number
  max_total_uses: number | null
  first_ride_only: boolean
  /** Empty = every service area / vehicle type. */
  service_areas: string[]
  vehicle_types: VehicleType[]
  is_active: boolean
  status: PromotionStatus
  stats: PromotionStats
  created_at: string
  updated_at: string
}

/** POST /admin/promotions body (PATCH takes any subset). */
export type PromotionInput = Omit<Promotion, 'id' | 'status' | 'stats' | 'created_at' | 'updated_at'>

/** GET /admin/promotions/{id}/rides items. */
export interface PromotionRide {
  ride_id: string
  status: RideStatus
  passenger_name: string | null
  driver_name: string | null
  fare: Decimal
  discount: Decimal
  total: Decimal
  requested_at: string
  completed_at: string | null
}

/** GET /admin/promotions/alerts items: passenger–driver pairs with many promoted rides. */
export interface PromotionPairAlert {
  passenger: { id: string, name: string | null, email: string | null }
  driver: { id: string, name: string | null, email: string | null, profile_id: string | null }
  rides: number
  discount_total: Decimal
  last_ride_at: string
}
