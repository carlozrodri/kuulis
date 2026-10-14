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
  is_test_account?: boolean
  created_at: string
  last_login_at: string | null
  /** Admin panel accounts, from /users/me only. */
  permissions?: string[] | null
  /** Doc 07: deletion asked for (account inactive, restorable by signing in) and carried out. */
  deletion_requested_at?: string | null
  deleted_at?: string | null
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

export interface AdminAuthResponse extends AuthResponse {
  /** Only right after setting up the authenticator: shown once. */
  recovery_codes?: string[] | null
}

/** Password accepted: the second factor comes next (``totp_setup`` when there is no authenticator yet). */
export interface AdminLoginStep {
  status: 'totp_required' | 'totp_setup'
  challenge: string
  setup: { secret: string, otpauth_uri: string, qr_data_uri: string } | null
}

export interface SessionInfo {
  id: string
  current: boolean
  device: string | null
  platform: string | null
  ip: string | null
  created_at: string
  last_used_at: string
  admin: boolean
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
    | 'criminal_record'
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
  'criminal_record',
]
export const VEHICLE_TYPES: VehicleType[] = ['moto', 'car']

export interface Vehicle {
  id: string
  /** Doc 12: a moto change waits as `pending` while the active one keeps working. */
  status?: VehicleStatus
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
  // ---- Doc 12 ----
  expires_on?: Day | null
  /** A verifier confirmed the date the driver typed. */
  expiry_confirmed?: boolean
  reviewed_at?: string | null
  /** Replaced by a newer file (admin detail only): shown under "Historial". */
  superseded_by_id?: string | null
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
  // ---- Doc 12. Optional so the panel still loads against an older API. ----
  pending_vehicle?: Vehicle | null
  verification?: VerificationState | null
  checks?: DriverCheck[]
  induction_completed_at?: string | null
}

/** Shape returned by GET /admin/drivers (items) and GET /admin/drivers/{id}. */
export interface AdminDriver extends DriverProfile {
  user: Pick<User, 'id' | 'email' | 'full_name'> & Partial<User>
  /** Phase 1B: average rating received as a driver (decimal string or number) and how many ratings. */
  rating_avg?: number | string | null
  rating_count?: number | null
  assigned_to?: StaffBrief | null
  duplicates?: DriverDuplicate[]
}

// ---- Ongoing driver verification (doc 12) ----

export type VehicleStatus = 'active' | 'pending' | 'retired'
export type CheckKind = 'selfie' | 'reverification' | 'document_renewal' | 'vehicle_change'
export const CHECK_KINDS: CheckKind[] = ['selfie', 'reverification', 'document_renewal', 'vehicle_change']
export type CheckStatus = 'requested' | 'pending' | 'approved' | 'rejected' | 'cancelled'
export const CHECK_STATUSES: CheckStatus[] = ['pending', 'requested', 'approved', 'rejected', 'cancelled']
export type MarkKind = 'national_id' | 'rif' | 'plate' | 'phone' | 'binance_pay_id' | 'device'

export interface DocumentAlert {
  kind: DocumentKind
  expires_on: Day
  /** Negative once expired. */
  days_left: number
  renewal_pending: boolean
}

export interface VerificationState {
  expired: DocumentKind[]
  expiring: DocumentAlert[]
  /** Approved before doc 12 without a date: the driver is asked to type it. */
  missing_expiry: DocumentKind[]
  required_check_id: string | null
  required_check_kind: 'selfie' | 'reverification' | null
  can_go_online: boolean
}

export interface DriverCheck {
  id: string
  kind: CheckKind
  status: CheckStatus
  /** Why it was asked: random, reports, team, driver. */
  reason: string
  document_id: string | null
  vehicle_id: string | null
  requested_at: string
  submitted_at: string | null
  reviewed_at: string | null
  result_reason: string | null
}

export interface StaffBrief {
  id: string
  full_name: string
  email: string
}

export interface CheckFile {
  kind: DocumentKind
  content_type: string
  /** Detail only. */
  download_url?: string | null
}

/** GET /admin/drivers/checks items and GET /admin/drivers/checks/{id}. */
export interface DriverCheckAdmin extends DriverCheck {
  driver: { id: string, user_id: string, full_name: string, email: string, status: DriverStatus, plate: string | null }
  assigned_to: StaffBrief | null
  reviewed_by: StaffBrief | null
  files: CheckFile[]
  /** Detail only: approved selfie and cédula, the document in use for a renewal, current moto photos. */
  references: DriverDocument[]
  /** The renewal file. */
  document: DriverDocument | null
  /** The new moto. */
  vehicle: Vehicle | null
  /** What the driver typed for a renewal or a new registration. */
  expires_on: Day | null
}

export interface DriverDuplicate {
  kind: MarkKind
  user_id: string
  name: string
  /** null once the account was erased. */
  email: string | null
  driver_id: string | null
  driver_status: DriverStatus | null
  deleted: boolean
  suspended: boolean
}

export interface VerificationSettings {
  expiring_documents: DocumentKind[]
  optional_documents: DocumentKind[]
  expiry_notice_days: number[]
  /** 0 = no random selfie. */
  selfie_every_days: number
  mismatch_reports: number
  report_window_days: number
  induction_required: boolean
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
  // ---- Phase 1D (docs/api/phase-1d.md). Optional so the panel still loads against an older API. ----
  topup_min_amount?: Decimal
  /** Kuulis' Binance Pay ID shown to drivers ("" = not configured yet). */
  topup_binance_pay_id?: string
  topup_account_name?: string
  transfer_monthly_limit?: Decimal
  subscription_free_months?: number
  subscription_grace_days?: number
  // ---- Four-eyes approvals (doc 06). ----
  /** Balance adjustments above this many USD wait for a second person ("0.00" = never). */
  approval_adjust_limit?: Decimal
  approval_fares?: boolean
  approval_broadcasts?: boolean
  /** Doc 17: waiving or lowering a driver's monthly fee waits for a second person. */
  approval_waivers?: boolean
  // ---- Remote control (doc 10). Maintenance and city pauses are edited on /app-status, not here. ----
  app_links?: AppLinks
  location_intervals?: LocationIntervals
  // ---- Trip safety (doc 11). ----
  safety?: SafetySettings
  // ---- Ongoing driver verification (doc 12). ----
  verification?: VerificationSettings
  // ---- Support (doc 13). ----
  support?: SupportSettings
  // ---- Notifications (doc 14). ----
  notifications?: NotificationSettings
  // ---- Cancellations and quality (doc 15). ----
  quality?: QualitySettings
  // ---- Anti-fraud (doc 16). ----
  risk?: RiskSettings
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
  // ---- Doc 15. Optional so the panel still works against an older API. ----
  cancel_reason_code?: CancelReasonCode | null
  /** Drivers who cancelled after accepting (the ride went back to searching). */
  reassign_count?: number
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
  // ---- Doc 11. ----
  pin_required?: boolean
  /** Wrong start PINs the driver typed (3 lock the start). */
  pin_failures?: number
  /** Real path of the driver: [lat, lng, unix seconds]. Empty until the ride ends. */
  track?: [number, number, number][]
  safety_alerts?: RideSafetyAlert[]
  // ---- Doc 15. ----
  reassigned_from_driver_id?: string | null
  cancellations?: RideCancellation[]
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

// ---- Phase 1D: wallet, top-ups, transfers & subscription (docs/api/phase-1d.md) ----

/** Calendar month in Caracas time, "2026-10". */
export type Month = string

/** Someone as the admin list endpoints return them (name and email of the driver). */
export interface PartyRef {
  id: string
  name: string | null
  email: string | null
}

export type WalletEntryKind
  = | 'promo_credit'
    | 'top_up'
    | 'transfer_in'
    | 'transfer_out'
    | 'subscription_fee'
    | 'adjustment'
export const WALLET_ENTRY_KINDS: WalletEntryKind[] = [
  'promo_credit',
  'top_up',
  'transfer_in',
  'transfer_out',
  'subscription_fee',
  'adjustment',
]

/** `details` per kind (all keys optional so an older/newer API never breaks the table). */
export interface WalletEntryDetails {
  /** promo_credit */
  passenger_name?: string | null
  /** top_up */
  method?: string | null
  reference?: string | null
  /** transfer_in / transfer_out */
  counterpart_name?: string | null
  note?: string | null
  /** subscription_fee */
  month?: Month | null
  /** adjustment */
  reason?: string | null
  [key: string]: unknown
}

export interface WalletEntry {
  id: string
  kind: WalletEntryKind
  /** Signed: negative for transfer_out, subscription_fee and negative adjustments. */
  amount: Decimal
  balance_after: Decimal
  ride_id: string | null
  description: string | null
  details: WalletEntryDetails | null
  created_at: string
}

export type TopUpStatus = 'pending' | 'unmatched' | 'completed' | 'rejected'
export const TOP_UP_STATUSES: TopUpStatus[] = ['pending', 'unmatched', 'completed', 'rejected']
export type TopUpMethod = 'binance_pay'

export interface TopUp {
  id: string
  status: TopUpStatus
  amount: Decimal
  method: TopUpMethod | string
  /** Binance order id. */
  reference: string | null
  payer_binance_id: string | null
  payer_name: string | null
  note: string | null
  created_at: string
  completed_at: string | null
  rejection_reason: string | null
  /** Doc 17: the support ticket where the driver said the top-up did not arrive. */
  dispute_report_id?: string | null
}

/** GET /admin/top-ups items: the top-up plus the driver (null while `unmatched`). */
export interface AdminTopUp extends TopUp {
  /** Binance Pay transaction id (automatic matches and assigned payments). */
  transaction_id?: string | null
  user?: PartyRef | null
  user_id?: string | null
  user_name?: string | null
  user_email?: string | null
}

/** GET /wallet/top-up-info. */
export interface TopUpInfo {
  method: TopUpMethod
  pay_id: string
  account_name: string
  min_amount: Decimal
  /** True when the worker reconciles Binance Pay automatically (API credentials configured). */
  automatic: boolean
}

/** GET /admin/transfers items. */
export interface AdminTransfer {
  id: string
  amount: Decimal
  note: string | null
  created_at: string
  sender?: PartyRef | null
  recipient?: PartyRef | null
  /** Alternative flat shape, tolerated. */
  from_user?: PartyRef | null
  to_user?: PartyRef | null
  // ---- Doc 16: held for an anti-fraud review / returned to the sender. Optional for an older API. ----
  held?: boolean
  returned?: boolean
}

export type ChargeStatus = 'paid' | 'pending' | 'waived'
export const CHARGE_STATUSES: ChargeStatus[] = ['pending', 'paid', 'waived']

export interface Charge {
  id: string
  month: Month
  earnings: Decimal
  fee: Decimal
  status: ChargeStatus
  /** The month fell entirely within the driver's free period. */
  free_period: boolean
  /** Only for `pending`: after this moment the driver is blocked. */
  due_at: string | null
  paid_at: string | null
  waived_reason: string | null
  /** Pending and past `due_at` (the driver is blocked). Computed by the panel when an older API omits it. */
  overdue?: boolean
  /** Doc 17: the fee before an admin lowered it (null when it was never reduced). */
  original_fee?: Decimal | null
}

/** GET /admin/subscriptions/charges items. */
export interface AdminCharge extends Charge {
  user?: PartyRef | null
  user_id?: string | null
  user_name?: string | null
  user_email?: string | null
}

/**
 * GET /admin/subscriptions/charges. `totals` = sum of `fee` per status over every row matching the filters
 * (not just this page). Used when the API sends it; the panel adds the rows up otherwise.
 */
export interface ChargePage extends Page<AdminCharge> {
  totals?: Partial<Record<ChargeStatus, Decimal>> | null
}

/** POST /admin/subscriptions/run. */
export interface SubscriptionRunResult {
  created: number
  paid: number
  pending: number
  waived: number
}

export interface FeeTier {
  /** The fee applies when the month's earnings are strictly above this amount. */
  above: Decimal
  fee: Decimal
}

export interface FeeSchedule {
  /** null for the built-in default schedule (nothing stored yet). */
  id: string | null
  effective_month: Month
  tiers: FeeTier[]
  /** The schedule in force this month, when the API flags it. */
  current?: boolean
  created_by: PartyRef | null
  created_at: string | null
}

/** GET /admin/wallets/{user_id}. */
export interface AdminWallet {
  user: PartyRef
  balance: Decimal
  binance_pay_id: string | null
  sent_this_month: Decimal
  /** The 20 most recent. */
  entries: WalletEntry[]
  pending_charges: Charge[]
}

// ---- Phase 1E: reports, account suspensions, finance & metrics (docs/api/phase-1e.md) ----

/** Calendar day in Caracas time, "2026-10-09". */
export type Day = string

export interface UserBrief {
  id: string
  name: string | null
  email: string | null
}

/** Account suspension in force (`until` null = indefinite). */
export interface Suspension {
  reason: string
  suspended_at: string
  until: string | null
  by: UserBrief | null
}

/** GET /admin/users/{id}/suspensions items, newest first. */
export interface SuspensionRecord extends Suspension {
  lifted_at: string | null
  lifted_by: UserBrief | null
  report_id: string | null
}

/** POST /admin/users/{id}/suspend body. */
export interface SuspendInput {
  reason: string
  until?: string
  report_id?: string
}

/** UserRead in the admin API adds the suspension in force (phase 1E) and the passenger rating (1B). */
export interface AdminUser extends User {
  suspension?: Suspension | null
  rating_avg?: number | null
  rating_count?: number
}

export type ReportCategory
  = | 'safety'
    | 'harassment'
    | 'driving'
    | 'fare'
    | 'vehicle_mismatch'
    | 'lost_item'
    | 'no_show'
    | 'app_issue'
    | 'payment'
    | 'other'
export const REPORT_CATEGORIES: ReportCategory[] = [
  'safety',
  'harassment',
  'driving',
  'fare',
  'vehicle_mismatch',
  'lost_item',
  'no_show',
  'app_issue',
  'payment',
  'other',
]
export type ReportPriority = 'urgent' | 'normal'
export const REPORT_PRIORITIES: ReportPriority[] = ['urgent', 'normal']
export type ReportStatus = 'open' | 'in_review' | 'resolved' | 'dismissed'
export const REPORT_STATUSES: ReportStatus[] = ['open', 'in_review', 'resolved', 'dismissed']
export type ReporterRole = 'passenger' | 'driver'

export interface Report {
  id: string
  category: ReportCategory
  description: string
  status: ReportStatus
  priority: ReportPriority
  ride_id: string | null
  /** null for a general report (no ride, nobody reported). */
  reporter_role: ReporterRole | null
  created_at: string
  updated_at: string
  /** Answer shown to the reporter once resolved or dismissed. */
  resolution: string | null
  resolved_at: string | null
}

// ---- Support (doc 13): tickets are reports with a conversation ----

/** web = public contact form on the website, maybe without an account. */
export type ReportSource = 'app' | 'help' | 'lost_item' | 'web'
export const REPORT_SOURCES: ReportSource[] = ['app', 'help', 'lost_item', 'web']
/** null once the ticket is closed. */
export type WaitingOn = 'staff' | 'user'
/** system = automatic lines (e.g. "closed for inactivity"). */
export type AuthorKind = 'user' | 'staff' | 'system'

/** GET /admin/reports items. */
export interface ReportAdminRead extends Report {
  /** null for a web contact without an account: use contact_name / contact_email. */
  reporter: UserBrief | null
  reported: UserBrief | null
  assigned_to: UserBrief | null
  notes_count: number
  // ---- Doc 13. Optional so the inbox still loads against an older API. ----
  source?: ReportSource
  waiting_on?: WaitingOn | null
  waiting_since?: string | null
  first_response_at?: string | null
  sla_due_at?: string | null
  overdue?: boolean
  last_message_at?: string | null
  tags?: string[]
  csat?: number | null
  csat_comment?: string | null
  contact_email?: string | null
  contact_name?: string | null
  messages_count?: number
}

export interface ReportCounts {
  open: number
  in_review: number
  urgent_open: number
  /** Doc 13. */
  waiting_staff?: number
  overdue?: number
  mine?: number
}

export interface MessageAttachment {
  key: string
  /** Short-lived download link. */
  url: string
}

/** A line of the ticket conversation (oldest first; the first one is the description). */
export interface ReportMessageAdminRead {
  id: string
  author_kind: AuthorKind
  /** Staff first name; null for the user and system lines. */
  author_name: string | null
  mine: boolean
  body: string
  attachments: MessageAttachment[]
  created_at: string
  author: UserBrief | null
}

export type LostItemAnswer = 'has_it' | 'not_found'

export interface LostItemRead {
  id: string
  ride_id: string
  description: string
  answer: LostItemAnswer | null
  answered_at: string | null
  chat_until: string | null
  chat_open: boolean
  report_id: string | null
  created_at: string
}

/** What the ticket does after the team's answer. */
export type ReplyThen = 'wait_user' | 'resolve' | 'keep'
export const REPLY_THEN: ReplyThen[] = ['wait_user', 'resolve', 'keep']

/** POST /admin/reports/{id}/messages body. */
export interface ReportReplyInput {
  body: string
  attachments?: string[]
  canned_response_id?: string
  then: ReplyThen
  add_tags?: string[]
}

export interface TagCount {
  tag: string
  count: number
}

export type CannedAction = 'none' | 'wait_user' | 'resolve'
export const CANNED_ACTIONS: CannedAction[] = ['none', 'wait_user', 'resolve']

/** A saved reply. `{nombre}` and `{viaje}` are filled in when sent. */
export interface CannedResponse {
  id: string
  title: string
  body: string
  locale: string
  action: CannedAction
  tags: string[]
  uses: number
  created_at: string
  updated_at: string
}

export interface CannedInput {
  title: string
  body: string
  locale: string
  action: CannedAction
  tags: string[]
}

export interface SupportMetricsDay {
  date: Day
  created: number
  resolved: number
}

export interface SupportAgentMetrics {
  user: UserBrief
  resolved: number
  first_response_minutes_avg: number | null
  csat_avg: number | null
}

/** GET /admin/support/metrics?days=30 (averages null when there is no data). */
export interface SupportMetrics {
  days: SupportMetricsDay[]
  first_response_minutes_avg: number | null
  resolution_hours_avg: number | null
  csat_avg: number | null
  csat_count: number
  overdue_open: number
  waiting_staff: number
  by_agent: SupportAgentMetrics[]
}

/** config.support (doc 13). */
export interface SupportSettings {
  sla_urgent_minutes: number
  sla_normal_hours: number
  response_promise_es: string
  response_promise_en: string
  auto_close_days: number
  auto_assign: boolean
  lost_item_days: number
  lost_item_chat_hours: number
}

/** POST /files/presign-upload response: PUT the bytes to upload_url with these headers, then send the key. */
export interface PresignedUpload {
  key: string
  upload_url: string
  method?: 'PUT'
  headers: Record<string, string>
  expires_in?: number
}

// ---- Help center (doc 13) ----

export type HelpTopic = 'account' | 'rides' | 'payments' | 'wallet' | 'safety' | 'documents' | 'app'
export const HELP_TOPICS: HelpTopic[] = ['account', 'rides', 'payments', 'wallet', 'safety', 'documents', 'app']
export type HelpAudience = 'all' | 'passenger' | 'driver'
export const HELP_AUDIENCES: HelpAudience[] = ['all', 'passenger', 'driver']
export const HELP_LOCALES = ['es', 'en'] as const
export type HelpLocale = typeof HELP_LOCALES[number]

/** GET /admin/help/articles items. */
export interface HelpArticleAdmin {
  id: string
  slug: string
  locale: string
  topic: HelpTopic
  audience: HelpAudience
  title: string
  excerpt: string
  position: number
  updated_at: string
  body_md: string
  published: boolean
  views: number
  helpful_yes: number
  helpful_no: number
}

export interface HelpArticleInput {
  slug: string
  locale: string
  topic: HelpTopic
  audience: HelpAudience
  title: string
  body_md: string
  published: boolean
  position: number
}

/** GET /admin/reports: a page plus counts for the whole inbox. */
export interface ReportPage extends Page<ReportAdminRead> {
  counts?: ReportCounts | null
}

/** `note` = written by staff; the rest are written by the system. */
export type ReportNoteKind = 'note' | 'status' | 'suspension'

export interface ReportNote {
  id: string
  body: string
  kind: ReportNoteKind
  author: UserBrief | null
  created_at: string
}

export interface PersonSummary {
  user_id: string
  name: string | null
  email: string | null
  phone: string | null
  role_in_ride: ReporterRole | null
  rating_avg: number | string | null
  rating_count: number
  rides_completed: number
  reports_against: { total: number, open: number, last_90_days: number }
  suspension: Suspension | null
  driver_profile_id: string | null
  driver_status: DriverStatus | null
}

/** GET /admin/reports/{id}. */
export interface ReportAdminDetail extends ReportAdminRead {
  ride: AdminRideRead | null
  notes: ReportNote[]
  reported_summary: PersonSummary | null
  /** null for a web contact without an account. */
  reporter_summary: PersonSummary | null
  // ---- Doc 13 ----
  messages?: ReportMessageAdminRead[]
  help_article?: { id: string, slug: string, title: string } | null
  lost_item?: LostItemRead | null
  /** Doc 17: the disputed top-up of a "my top-up did not arrive" ticket (category `payment`). */
  top_up?: AdminTopUp | null
}

/** RideAdminRead (list shape of /admin/rides): the ride plus flat names of both parties. */
export interface AdminRideRead extends Ride {
  passenger_name?: string | null
  passenger_email?: string | null
  driver_name?: string | null
  driver_email?: string | null
  driver_profile_id?: string | null
}

/** PATCH /admin/reports/{id}. */
export interface ReportUpdate {
  status?: 'open' | 'in_review'
  priority?: ReportPriority
  assigned_to_id?: string | null
  /** Doc 13: replaces the ticket's tags. */
  tags?: string[]
}

// ---- Finance ----

export interface CountAmount {
  count: number
  amount: Decimal
}

export interface FinanceDay {
  date: Day
  top_ups: Decimal
  fees: Decimal
  promo_credits: Decimal
}

/** GET /admin/finance/summary. */
export interface FinanceSummary {
  from: Day
  to: Day
  top_ups: {
    completed: CountAmount
    completed_auto: CountAmount
    completed_manual: CountAmount
    pending: CountAmount
    unmatched: CountAmount
    rejected: CountAmount
  }
  fees: { collected: Decimal, pending: Decimal, waived_count: number }
  promo_credits: Decimal
  adjustments: { credit: Decimal, debit: Decimal }
  transfers: CountAmount
  /** Sum of every wallet balance right now (what Kuulis owes in service). */
  wallet_balances: Decimal
  by_day: FinanceDay[]
}

// ---- Metrics ----

export interface MetricsTotals {
  rides_requested: number
  rides_completed: number
  rides_cancelled_passenger: number
  rides_cancelled_driver: number
  rides_cancelled_admin: number
  rides_no_drivers: number
  /** 0–1. */
  completion_rate: number | null
  gmv: Decimal
  discounts: Decimal
  avg_fare: Decimal | null
  avg_distance_m: number | null
  avg_assign_s: number | null
  avg_pickup_s: number | null
  avg_trip_s: number | null
  active_drivers: number
  active_passengers: number
  new_passengers: number
  new_drivers: number
  avg_rating_drivers: number | null
  avg_rating_passengers: number | null
}

export interface MetricsDay {
  date: Day
  requested: number
  completed: number
  cancelled: number
  no_drivers: number
  gmv: Decimal
  active_drivers: number
}

export interface MetricsHour {
  /** 0–23, Caracas time. */
  hour: number
  requested: number
  completed: number
}

export interface TopDriver {
  user_id: string
  name: string | null
  rides: number
  earnings: Decimal
  rating_avg: number | null
}

/** GET /admin/metrics. */
export interface Metrics {
  from: Day
  to: Day
  area: string | null
  totals: MetricsTotals
  by_day: MetricsDay[]
  by_hour: MetricsHour[]
  top_drivers: TopDriver[]
}

/** GET /admin/overview. */
export interface Overview {
  online_drivers: number
  rides_in_progress: number
  rides_today: number
  completed_today: number
  gmv_today: Decimal
  pending_driver_applications: number
  pending_top_ups: number
  unmatched_top_ups: number
  open_reports: number
  urgent_reports: number
  overdue_drivers: number
  stale_rates: RateSource[]
  open_alerts?: number
  /** Doc 12: selfies, renewals and moto changes waiting for a verifier. */
  pending_reverifications?: number
  documents_expiring_week?: number
}

// ---- Monitoring (GET /admin/system/health) ----------------------------------------------------

export type HealthStatus = 'ok' | 'warning' | 'down' | 'off'

export interface SystemHealth {
  env: string
  commit: string | null
  checked_at: string
  services: { name: 'database' | 'redis' | 'osrm' | 'photon', status: HealthStatus, latency_ms: number | null }[]
  loops: { name: string, status: HealthStatus, last_beat_at: string | null, max_age_seconds: number }[]
  queues: { taskiq_pending: number | null, dispatch_due: number, dispatch_overdue: number }
  traffic: { requests_5m: number, errors_5m: number, error_rate_5m: number, avg_ms_5m: number }
  rides: { searching: number, requested_last_hour: number, no_drivers_last_hour: number }
  stale_rates: RateSource[]
  disk_used_percent: number | null
  backups: {
    configured: boolean
    last_backup_at?: string | null
    last_backup_bytes?: number | null
    last_ledger_at?: string | null
    last_files_mirror_at?: string | null
    last_restore_check_at?: string | null
    last_restore_ok?: boolean | null
    errors: Record<string, string>
  }
  alerts: { key: string, message: string, since: string }[]
  /** Doc 17: the last daily ledger invariants check (null until the first one ran). */
  ledger?: LedgerHealth | null
}

export interface LedgerHealth {
  ok: boolean
  checked_at: string
  wallets: number
  /** How many issues the check found. */
  issues: number
  first_issue: LedgerIssue | null
}

export interface AuditEntry {
  id: string
  actor_id: string | null
  actor_email: string
  action: string
  entity_type: string
  entity_id: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  reason: string | null
  ip: string | null
  user_agent: string | null
  request_id: string | null
  created_at: string
}

export interface StaffRole {
  id: string
  name: string
  label: string
  permissions: string[]
  members: number
}

export interface RolesOverview {
  catalog: { group: string, permissions: string[] }[]
  roles: StaffRole[]
}

export interface StaffMember {
  id: string
  email: string
  full_name: string
  role: Role
  staff_role_id: string | null
  staff_role_label: string | null
  is_active: boolean
  totp_enabled: boolean
  invite_pending: boolean
  last_login_at: string | null
  created_at: string
}

// ---- Four-eyes approvals (doc 06) ----

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired'

export interface ApprovalRead {
  id: string
  action: string
  entity_type: string
  entity_id: string | null
  summary: string
  payload: Record<string, unknown>
  reason: string | null
  status: ApprovalStatus
  requested_by_id: string | null
  requested_by_email: string
  decided_by_email: string | null
  decided_at: string | null
  decision_note: string | null
  result: Record<string, unknown> | null
  expires_at: string
  created_at: string
  /** This account may approve or reject it now. */
  can_decide: boolean
}

/** 202 answer of an action that now waits for a second approval. */
export interface ApprovalHeld {
  status: 'pending_approval'
  approval: ApprovalRead
}

// ---- Legal texts (doc 07) ----

export const LEGAL_KINDS = ['terms', 'privacy', 'community', 'driver_terms', 'wallet'] as const
export type LegalKind = typeof LEGAL_KINDS[number]

export interface LegalVersion {
  kind: LegalKind
  version: number
  locale: 'es' | 'en'
  title: string
  summary: string
  requires_reacceptance: boolean
  published_at: string
}

export interface LegalDocument extends LegalVersion {
  body_md: string
}

export interface LegalAcceptance {
  kind: LegalKind
  version: number
  ip: string | null
  platform: string | null
  created_at: string
}

// ---- Privacy (doc 07) ----

export interface DeletionRequest {
  user_id: string
  email: string
  full_name: string
  requested_at: string
  erase_at: string
  erased_at: string | null
}

export interface AdminDataExport {
  id: string
  user_id: string
  email: string
  status: 'pending' | 'ready' | 'failed' | 'expired'
  error: string | null
  created_at: string
  completed_at: string | null
  expires_at: string | null
}

// ---- APK releases (doc 09) ----

export const RELEASE_CHANNELS = ['qa', 'beta', 'production'] as const
export type ReleaseChannel = typeof RELEASE_CHANNELS[number]

export interface AdminRelease {
  id: string
  platform: string
  channel: ReleaseChannel
  version: string
  build: number
  /** Bytes. */
  size: number
  sha256: string
  md5: string
  notes: string | null
  is_mandatory: boolean
  /** When it was published. */
  created_at: string
  /** Withdrawn (rolled back): the previous release is offered again. */
  withdrawn_at: string | null
  file_key: string
  published_by_email: string | null
  download_url: string | null
}

/** An APK the compiler uploaded, publishable from the admin. */
export interface AppBuild {
  key: string
  file_name: string
  version: string
  build: number
  size: number
  sha256: string
  md5: string
  profile: string | null
  commit: string | null
  built_at: string | null
  published_channels: ReleaseChannel[]
}

/** Distinct users per build over the last 7 days. */
export interface BuildUsage {
  platform: string
  build: number
  users: number
}

// ---- JS over-the-air updates ----

export interface AdminUpdate {
  id: string
  platform: string
  channel: ReleaseChannel
  /** Fingerprint of the native code (40 hex): only apps built with the same one receive it. */
  runtime_version: string
  /** rollback: the apps go back to the code inside the APK (no JS update). */
  kind: 'update' | 'rollback'
  commit: string | null
  message: string | null
  /** Stable share of devices that receive it (0 = paused). */
  rollout_percent: number
  /** Set on the replacement created by reverting that update. */
  reverted_from_id: string | null
  created_at: string
  withdrawn_at: string | null
  published_by_email: string | null
}

/** A JS export the compiler uploaded, publishable from the admin. */
export interface UpdateCandidate {
  key: string
  platform: string
  runtime_version: string
  commit: string | null
  message: string | null
  built_at: string | null
  /** Bytes. */
  bundle_size: number | null
  asset_count: number
  published_channels: ReleaseChannel[]
}

/** Distinct users per running update over the last 7 days ('embedded': the APK's own code). */
export interface UpdateUsage {
  update_id: string
  users: number
}

// ---- Remote control of the app (doc 10) ----

/** A text in both app languages (the app falls back to Spanish when `en` is empty). */
export interface Localized {
  es: string
  en: string
}

export interface Maintenance {
  enabled: boolean
  message: Localized
  /** Estimated end (ISO), shown in the app. */
  eta: string | null
  /** Empty = every city. */
  areas: string[]
}

/** New rides stopped in one city (rain, protests, curfew). */
export interface AreaPause {
  area: string
  message: Localized
  eta: string | null
}

export interface AppStatus {
  maintenance: Maintenance
  area_pauses: AreaPause[]
}

export interface AppStatusRead extends AppStatus {
  /** Service area names, for the pickers. */
  areas: string[]
}

export const APP_PLATFORMS = ['android', 'ios', 'web'] as const
export type AppPlatform = typeof APP_PLATFORMS[number]
export const APP_MODES = ['passenger', 'driver'] as const
export type AppMode = typeof APP_MODES[number]

/** Who gets a flag that is on. An empty list (or null) does not narrow anything. */
export interface FlagRules {
  platforms: AppPlatform[]
  min_build: number | null
  areas: string[]
  roles: AppMode[]
  /** 0–100. */
  percent: number
}

export interface FeatureFlag {
  key: string
  /** Spanish, from the API. */
  description: string
  default: boolean
  enabled: boolean
  rules: FlagRules
  /** False while it still follows the default. */
  changed: boolean
  updated_at: string | null
  updated_by_email: string | null
}

export interface FlagCheck {
  email: string
  role: AppMode
  enabled: boolean
}

export const ANNOUNCEMENT_STYLES = ['info', 'warning', 'promo'] as const
export type AnnouncementStyle = typeof ANNOUNCEMENT_STYLES[number]
/** Screens a banner button can open in the app. */
export const APP_SCREENS = ['home', 'wallet', 'promotions', 'profile', 'about', 'driver_signup'] as const
export type AppScreen = typeof APP_SCREENS[number]

export interface AnnouncementCta {
  label: Localized
  /** https:// only; exactly one of url and screen. */
  url: string | null
  screen: AppScreen | null
}

export interface AnnouncementInput {
  title: Localized
  body: Localized
  target: { roles: AppMode[], areas: string[] }
  cta: AnnouncementCta | null
  starts_at: string
  ends_at: string
  dismissible: boolean
  style: AnnouncementStyle
}

export interface AdminAnnouncement extends AnnouncementInput {
  id: string
  created_at: string
  created_by_email: string | null
  /** Accounts or devices that got it. */
  seen: number
  dismissed: number
}

export interface AppLinks {
  support_whatsapp: string
  support_email: string
  emergency_number: string
  terms_url: string
  privacy_url: string
}

/** How often the driver app sends its location, in seconds. */
export interface LocationIntervals {
  online_seconds: number
  on_ride_seconds: number
}

// ---- Trip safety (doc 11) ----

export type PassengerPhotoMode = 'off' | 'night' | 'always'

export interface SafetySettings {
  pin_areas: string[]
  passenger_photo: PassengerPhotoMode
  night_start: string
  night_end: string
  stop_minutes: number
  deviation_m: number
  deviation_minutes: number
  overtime_factor: number
  check_in_seconds: number
  sos_location_seconds: number
  /** Someone on call answers SOS: Telegram and the admin alarm (off by default). */
  sos_team_alert: boolean
}

export type AlertKind = 'sos' | 'stop' | 'deviation' | 'overtime'
export const ALERT_KINDS: AlertKind[] = ['sos', 'stop', 'deviation', 'overtime']
export type AlertStatus = 'checking' | 'open' | 'acknowledged' | 'resolved' | 'dismissed'
export type AlertOutcome = 'false_alarm' | 'assisted' | 'emergency_services' | 'no_answer' | 'other'
export const ALERT_OUTCOMES: AlertOutcome[] = ['assisted', 'emergency_services', 'false_alarm', 'no_answer', 'other']

export interface RideSafetyAlert {
  id: string
  kind: AlertKind
  status: AlertStatus
  user_id: string
  lat: number | null
  lng: number | null
  details: Record<string, unknown>
  created_at: string
  resolved_at: string | null
  outcome: string | null
}

export interface AlertParty {
  id: string
  name: string
  email: string
  /** Drivers only. */
  phone: string | null
  role: 'passenger' | 'driver'
}

/** GET /admin/safety/alerts items. */
export interface SafetyAlert {
  id: string
  ride_id: string | null
  ride_status: RideStatus | null
  kind: AlertKind
  status: AlertStatus
  raised_by: AlertParty | null
  passenger: AlertParty | null
  driver: AlertParty | null
  vehicle: { brand: string, model: string, color: string, plate: string } | null
  lat: number | null
  lng: number | null
  location_at: string | null
  driver_location: DriverLocation | null
  pickup: Place | null
  dropoff: Place | null
  polyline: string | null
  details: Record<string, unknown>
  /** user id -> "ok" | "help" (answers to "¿Todo bien?"). */
  answers: Record<string, 'ok' | 'help'>
  check_in_deadline: string | null
  escalated_at: string | null
  acknowledged_at: string | null
  handled_by_id: string | null
  handled_by_name: string | null
  notes: string
  outcome: string | null
  created_at: string
  resolved_at: string | null
}

/** GET /admin/safety/summary: polled for the menu badge and the alarm. */
export interface SafetySummary {
  open: number
  acknowledged: number
  latest_id: string | null
}

// ---- Notifications and campaigns (doc 14) ----

export const NOTIFICATION_CATEGORIES = ['transactional', 'safety', 'support', 'marketing'] as const
export type NotificationCategory = typeof NOTIFICATION_CATEGORIES[number]

/** A row of a user's inbox. */
export interface NotificationRead {
  id: string
  title: string
  body: string
  data: Record<string, unknown>
  category: NotificationCategory
  /** App path ("/wallet") or an https link; set by campaigns. */
  deep_link: string | null
  read_at: string | null
  created_at: string
}

export const CAMPAIGN_STATUSES = ['draft', 'pending_approval', 'scheduled', 'sending', 'sent', 'cancelled'] as const
export type CampaignStatus = typeof CAMPAIGN_STATUSES[number]
export const CAMPAIGN_CHANNELS = ['push', 'inbox', 'email'] as const
export type CampaignChannel = typeof CAMPAIGN_CHANNELS[number]
export const CAMPAIGN_AUDIENCES = ['all', 'passengers', 'drivers'] as const
export type CampaignAudience = typeof CAMPAIGN_AUDIENCES[number]

/** Who gets a campaign. Every condition narrows the audience. */
export interface Segment {
  audience: CampaignAudience
  /** Service area names; empty = everywhere. */
  cities: string[]
  /** Signed in within the last N days. */
  active_days?: number | null
  /** Not signed in within the last N days. */
  inactive_days?: number | null
  /** Drivers with a pending monthly fee. */
  fee_pending: boolean
  /** Accounts created in the last N days without a completed ride. */
  new_without_ride_days?: number | null
  /** Phone app version lower than this ("1.4.0"). */
  app_version_below?: string | null
  locale?: 'es' | 'en' | null
}

/** targeted = frozen audience; sent = got it on some channel; skipped by reason; pushed = phones;
 *  delivered = push receipts ok; opened = read or tapped. */
export interface CampaignStats {
  targeted: number
  pending: number
  sent: number
  skipped: number
  skipped_opt_out: number
  skipped_cap: number
  skipped_no_channel: number
  pushed: number
  delivered: number
  emailed: number
  opened: number
}

export interface CampaignRead {
  id: string
  name: string
  status: CampaignStatus
  segment: Segment
  channels: CampaignChannel[]
  title_es: string
  body_es: string
  title_en: string | null
  body_en: string | null
  deep_link: string | null
  scheduled_at: string | null
  started_at: string | null
  finished_at: string | null
  stats: CampaignStats
  created_by_id: string | null
  created_by_name: string | null
  created_at: string
  updated_at: string
}

/** POST /admin/campaigns body (PATCH takes any subset). */
export interface CampaignCreate {
  name: string
  segment: Segment
  channels: CampaignChannel[]
  title_es: string
  body_es: string
  title_en?: string | null
  body_en?: string | null
  deep_link?: string | null
  scheduled_at?: string | null
}
export type CampaignUpdate = Partial<CampaignCreate>

export interface AudienceCount {
  total: number
  /** Users with an active phone. */
  with_push: number
  passengers: number
  drivers: number
}

/** POST /admin/campaigns/{id}/test */
export interface CampaignTestResult {
  pushed: boolean
  emailed: boolean
}

export interface EmailTemplateInfo {
  name: string
  /** Spanish label and description. */
  label: string
  description: string
}

export interface EmailPreview {
  name: string
  locale: 'es' | 'en'
  subject: string
  html: string
  text: string
}

/** config.notifications (doc 14). */
export interface NotificationSettings {
  /** Caracas time "HH:MM"; equal values = no default quiet hours. */
  quiet_start: string
  quiet_end: string
  /** Marketing notifications per user per day (0 = no limit). */
  marketing_daily_cap: number
  inbox_retention_days: number
  device_idle_days: number
  monthly_summary: boolean
}

// ---- Doc 15: cancellations and service quality ----

export const PASSENGER_CANCEL_REASONS = ['driver_late', 'changed_plans', 'driver_asked', 'vehicle_mismatch', 'wrong_pickup', 'other'] as const
export const DRIVER_CANCEL_REASONS = ['no_show', 'wrong_address', 'no_helmet', 'vehicle_problem', 'safety_concern', 'other'] as const
export type CancelReasonCode = typeof PASSENGER_CANCEL_REASONS[number] | typeof DRIVER_CANCEL_REASONS[number]
export type CancelSide = 'passenger' | 'driver'
export const CANCEL_SIDES: CancelSide[] = ['passenger', 'driver']

/** One cancellation of a ride; a driver's sends the ride back to searching (`reassigned`). */
export interface RideCancellation {
  id: string
  user_id: string
  user_name: string
  side: CancelSide
  reason_code: CancelReasonCode | null
  reason: string | null
  /** Ride status when it happened. */
  stage: RideStatus
  /** Whether it counts against the person's rate (not in the passenger's grace period, not a no-show). */
  counted: boolean
  reassigned: boolean
  created_at: string
}

export const QUALITY_LEVELS = ['ok', 'warn', 'low_priority', 'review'] as const
export type QualityLevel = typeof QUALITY_LEVELS[number]
export type QualityRole = 'driver' | 'passenger'
export type PauseReason = 'cancel_burst' | 'decline_streak' | 'no_shows'
export type QualityReason = 'cancel_rate' | 'rating' | 'no_shows'

/** Rates over the configured window (null: nothing to divide by yet). */
export interface QualityStats {
  offers: number
  accepted: number
  rides: number
  cancels: number
  no_shows: number
  completed: number
  /** 0..1 */
  acceptance_rate: number | null
  cancel_rate: number | null
  rating_avg: number | null
  rating_count: number
  level: QualityLevel
  reasons: QualityReason[]
}

/** GET /admin/quality/users: people below a threshold or paused now, worst first. */
export interface QualityRow extends QualityStats {
  user_id: string
  role: QualityRole
  name: string
  email: string
  driver_profile_id: string | null
  computed_at: string
  paused_until: string | null
}

export interface QualityWeek {
  /** Monday of the week (YYYY-MM-DD). */
  week: Day
  offers: number
  accepted: number
  acceptance_rate: number | null
  driver_cancels: number
  driver_cancel_rate: number | null
  passenger_rides: number
  passenger_cancels: number
  passenger_cancel_rate: number | null
  no_shows: number
}

export interface QualityPause {
  id: string
  role: QualityRole
  reason: PauseReason
  created_at: string
  until: string
  lifted_at: string | null
  lifted_by_id: string | null
}

/** GET /admin/quality/users/{user_id}: live rates for both roles, the last 8 weeks and the pauses. */
export interface QualityDetail {
  user_id: string
  /** null when the person does not drive. */
  driver: QualityStats | null
  passenger: QualityStats
  /** Oldest first. */
  weeks: QualityWeek[]
  pauses: QualityPause[]
  window_days: number
}

/** GET /admin/quality/cancellations. */
export interface CancellationCount {
  side: CancelSide
  reason_code: CancelReasonCode | null
  total: number
  counted: number
  reassigned: number
}

/** config.quality (doc 15). Rates and the dispatch weight are 0..1 fractions. */
export interface QualitySettings {
  pickup_wait_minutes: number
  passenger_cancel_grace_s: number
  window_days: number
  /** 0 turns the rule off. */
  driver_cancel_burst: number
  driver_decline_streak: number
  driver_pause_minutes: number
  driver_cancel_warn: number
  driver_cancel_low_priority: number
  driver_cancel_review: number
  min_rides: number
  passenger_no_show_warn: number
  passenger_no_show_pause: number
  passenger_pause_hours: number
  rating_review_below: number
  rating_min_count: number
  dispatch_quality_weight: number
}

// ---- Doc 16: anti-fraud ----

export const RISK_KINDS = ['shared_device', 'fake_gps', 'suspicious_ride', 'frequent_pair', 'transfers', 'rating_ring'] as const
export type RiskKind = typeof RISK_KINDS[number]
export const SIGNAL_STATUSES = ['open', 'confirmed', 'dismissed'] as const
export type SignalStatus = typeof SIGNAL_STATUSES[number]
export const HOLD_KINDS = ['promo_credit', 'transfer'] as const
export type HoldKind = typeof HOLD_KINDS[number]
export const HOLD_STATUSES = ['held', 'released', 'voided'] as const
export type HoldStatus = typeof HOLD_STATUSES[number]
/** Codes in signal.reasons / hold.reasons (a newer API may add more: they render as the code). */
export type RiskReason
  = | 'same_device' | 'little_movement' | 'too_short' | 'same_place' | 'no_track' | 'frequent_pair' | 'shared_device'
    | 'mocked' | 'jumps' | 'chain' | 'fan_in' | 'new_account' | 'recipient_frozen' | 'first_transfer' | 'rating_ring' | 'risk_score'
export type BlockedKind = 'email' | MarkKind

/** A person in a risk row: links to the driver page when driver_profile_id is set. */
export interface RiskUser {
  id: string
  name: string
  /** null once the account was erased. */
  email: string | null
  /** 0..100 */
  risk_score: number
  driver_profile_id: string | null
}

export interface SignalRead {
  id: string
  kind: RiskKind
  reasons: string[]
  /** 0..100 */
  score: number
  status: SignalStatus
  /** Numbers behind the alert; keys depend on the kind (see riskEvidenceLines). */
  evidence: Record<string, unknown>
  user: RiskUser
  related_user: RiskUser | null
  ride_id: string | null
  created_at: string
  reviewed_by_name: string | null
  reviewed_at: string | null
  review_note: string | null
}

export interface RideEvidence {
  id: string
  status: string
  pickup: [number, number]
  dropoff: [number, number]
  /** Route estimate. */
  distance_m: number
  duration_s: number
  discount: Decimal
  started_at: string | null
  completed_at: string | null
  /** Real path: [lat, lng, unix seconds]; may be empty. */
  track: [number, number, number][]
}

export interface HoldRead {
  id: string
  kind: HoldKind
  status: HoldStatus
  amount: Decimal
  /** Who receives the money. */
  user: RiskUser
  sender: RiskUser | null
  ride_id: string | null
  reasons: string[]
  /** Pays itself at this moment (first transfer of an account) unless someone acts first. */
  release_at: string | null
  created_at: string
  resolved_at: string | null
  resolved_by_name: string | null
  note: string | null
}

export interface SignalDetail extends SignalRead {
  ride: RideEvidence | null
  accounts: RiskUser[]
  holds: HoldRead[]
}

export interface DeviceRead {
  id: string
  platform: string
  model: string
  app_version: string
  first_seen: string
  last_seen: string
  /** Other accounts seen on the same phone. */
  other_accounts: RiskUser[]
}

export interface BlockedRead {
  id: string
  kind: BlockedKind
  reason: string
  source_user: RiskUser | null
  created_at: string
  created_by_name: string | null
}

/** GET /admin/risk/users/{user_id}. */
export interface RiskUserDetail {
  user: RiskUser
  /** Promotion credits wait and outgoing transfers are blocked. */
  frozen: boolean
  suspended: boolean
  signals: SignalRead[]
  devices: DeviceRead[]
  duplicates: DriverDuplicate[]
  holds: HoldRead[]
  blocked: BlockedRead[]
}

/** GET /admin/risk/summary. */
export interface RiskSummary {
  open: { kind: RiskKind, open: number }[]
  holds: number
  held_amount: Decimal
}

/** config.risk (doc 16). Shares are 0..1 fractions. */
export interface RiskSettings {
  window_days: number
  freeze_score: number
  ride_hold_score: number
  max_accounts_per_device: number
  min_path_share: number
  min_duration_share: number
  same_place_m: number
  min_ride_m: number
  pair_rides: number
  pair_days: number
  jump_alerts: number
  /** 0 turns it off. */
  first_transfer_hold_hours: number
  chain_minutes: number
  fan_in_senders: number
  new_account_days: number
  rating_ring_rides: number
}

// ---- Payments hardening: closings, invariants, simulator (doc 17) ----

export type LedgerIssueKind
  = | 'balance_mismatch'
    | 'last_entry_mismatch'
    | 'negative_balance'
    | 'duplicate_top_up'
    | 'top_up_without_entry'
    | 'fee_without_entry'

/** One problem the invariants check found; the other keys depend on the kind. */
export interface LedgerIssue {
  kind: LedgerIssueKind | string
  user_id?: string
  wallet_id?: string
  top_up_id?: string
  charge_id?: string
  /** duplicate_top_up: the Binance payment id credited more than once. */
  id?: string
  count?: number
  balance?: Decimal
  entries?: Decimal
  balance_after?: Decimal
  [key: string]: unknown
}

/** GET /admin/finance/invariants (null until the first check) and POST /admin/finance/invariants/run. */
export interface InvariantsResult {
  ok: boolean
  checked_at: string
  wallets: number
  issues: LedgerIssue[]
}

export interface CountAmount {
  count: number
  amount: Decimal
}

/** What a closing freezes (also GET /admin/finance/closings/preview). */
export interface ClosingTotals {
  entries: Partial<Record<WalletEntryKind, { count: number, credits: Decimal, debits: Decimal }>>
  top_ups: {
    credited: CountAmount
    credited_auto: CountAmount
    credited_manual: CountAmount
    unmatched: CountAmount
  }
  /** Fees billed this month (the 1st bills the month before), by status at closing time. */
  charges: Partial<Record<ChargeStatus, { count: number, fees: Decimal }>>
  fees_collected: Decimal
  balances: { opening: Decimal, closing: Decimal, net: Decimal }
}

export interface StatementRowMissing {
  id: string
  amount: Decimal
  at: string | null
}

export interface KuulisPaymentMissing {
  top_up_id: string
  id: string | null
  amount: Decimal
  status: TopUpStatus
  reason: 'not_found' | 'no_reference'
}

export interface AmountMismatch {
  top_up_id: string
  id: string | null
  amount: Decimal
  status: TopUpStatus
  binance_amount: Decimal
}

/** Binance Pay statement vs Kuulis top-ups for the month. */
export interface ClosingDifferences {
  statement_rows: number
  statement_total: Decimal
  kuulis_rows: number
  kuulis_total: Decimal
  matched: number
  missing_in_kuulis: StatementRowMissing[]
  missing_in_binance: KuulisPaymentMissing[]
  amount_mismatch: AmountMismatch[]
}

export interface Closing {
  month: Month
  totals: ClosingTotals
  hash: string
  previous_hash: string | null
  /** False: the stored closing no longer matches its hash (someone changed it). */
  hash_ok: boolean
  closed_by: UserBrief | null
  closed_at: string
  statement_uploaded_at: string | null
  has_statement_file: boolean
  differences: ClosingDifferences | null
  has_differences: boolean
  reconciled_at: string | null
  reconciled_by: UserBrief | null
  reconcile_note: string | null
}

export interface TierCount {
  above: Decimal
  fee: Decimal
  drivers: number
  total: Decimal
}

/** POST /admin/subscriptions/simulate. */
export interface Simulation {
  month: Month
  drivers: number
  referral_free: number
  billed: Decimal
  /** The current tiers reproduce exactly what the month billed. */
  matches: boolean
  current: TierCount[]
  current_total: Decimal
  proposed: TierCount[]
  proposed_total: Decimal
  /** proposed - current. */
  difference: Decimal
}

// ---- Product analytics (doc 19) -----------------------------------------------------------------

export interface FunnelStep {
  step: string
  users: number
}

/** GET /admin/analytics/funnels. */
export interface Funnels {
  passenger: FunnelStep[]
  driver: FunnelStep[]
  rides: FunnelStep[]
  onboarding_screens: FunnelStep[]
  computed_at: string | null
}

export interface RetentionRow {
  cohort: string
  users: number
  /** "1", "2", "4", "8": people who rode again that week; null while the week is not over. */
  weeks: Record<string, number | null>
}

export interface RetentionTable {
  rows: RetentionRow[]
  average: Record<string, number | null>
}

/** GET /admin/analytics/retention. */
export interface Retention {
  passenger: RetentionTable
  driver: RetentionTable
  computed_at: string | null
}

export interface SupplyCell {
  cell: string
  lat: number
  lng: number
  requests: number
  no_drivers: number
  quotes: number
  driver_hours: number
}

export interface SupplyHourRow {
  hour: number
  requests: number
  no_drivers: number
  quotes: number
  driver_hours: number
}

/** GET /admin/analytics/supply-demand. */
export interface SupplyDemand {
  cells: SupplyCell[]
  hours: SupplyHourRow[]
}

/** GET /admin/analytics/promotions. */
export interface PromotionAnalytics {
  id: string
  name: string
  code: string | null
  rides: number
  cost: Decimal
  cost_per_ride: Decimal | null
  new_passengers: number
  cost_per_new_passenger: Decimal | null
  returned_30d: number
  eligible_30d: number
  retention_30d: number | null
}

export interface ValueBucket {
  min: number
  max: number | null
  count: number
}

/** GET /admin/analytics/drivers. */
export interface DriverEconomics {
  month: string
  drivers: number
  total_earnings: Decimal
  median_earnings: Decimal | null
  earnings: ValueBucket[]
  tiers: { above: Decimal, fee: Decimal, drivers: number }[]
  online_drivers: number
  online_hours: number
  ride_hours: number
  utilization: number | null
  utilization_spread: ValueBucket[]
}
