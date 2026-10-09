export type Role = "user" | "staff" | "admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  locale: "es" | "en";
  avatar_key: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse extends TokenPair {
  user: User;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AppNotification {
  id: string;
  title: string;
  body: string;
  data: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

// ── Phase 1A: configuration and drivers (docs/api/phase-1a.md) ──

export type VehicleType = "moto" | "car";

export type DocumentKind =
  | "id_card"
  | "rif"
  | "drivers_license"
  | "medical_certificate"
  | "vehicle_registration"
  | "selfie"
  | "vehicle_photo";

export type DocumentStatus = "pending" | "approved" | "rejected";

export type DriverStatus =
  | "draft"
  | "pending_review"
  | "approved"
  | "rejected"
  | "suspended";

export interface AppConfig extends RideConfig {
  driver_min_age: number;
  vehicle_min_year: Partial<Record<VehicleType, number>>;
  enabled_vehicle_types: VehicleType[];
  driver_required_documents: DocumentKind[];
  vehicle_photo_min_count: number;
}

export interface Vehicle {
  id: string;
  type: VehicleType;
  brand: string;
  model: string;
  year: number;
  plate: string;
  color: string;
}

export interface DriverDocument {
  id: string;
  kind: DocumentKind;
  status: DocumentStatus;
  content_type: string;
  rejection_reason: string | null;
  created_at: string;
}

export interface DriverRequirements {
  missing_documents: DocumentKind[];
  vehicle_photos: number;
  vehicle_photos_required: number;
  age_ok: boolean;
  vehicle_ok: boolean;
  can_submit: boolean;
}

export interface DriverProfile {
  id: string;
  user_id: string;
  status: DriverStatus;
  birth_date: string;
  national_id: string;
  rif: string;
  phone: string;
  city: string;
  rejection_reason: string | null;
  /** Not in the written contract; shown when the API sends it. */
  suspension_reason?: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  approved_at: string | null;
  suspended_at?: string | null;
  first_trip_completed_at?: string | null;
  created_at?: string;
  vehicle: Vehicle | null;
  documents: DriverDocument[];
  requirements: DriverRequirements;
}

export interface DriverPersonalInput {
  birth_date: string;
  national_id: string;
  rif: string;
  phone: string;
}

export interface VehicleInput {
  type: VehicleType;
  brand: string;
  model: string;
  year: number;
  plate: string;
  color: string;
}

export interface PresignResponse {
  key: string;
  upload_url: string;
  method: "PUT";
  headers: Record<string, string>;
  expires_in: number;
}

// ── Phase 1B: rides (docs/api/phase-1b.md) ──

export type PaymentMethod =
  | "cash_usd"
  | "pago_movil"
  | "binance"
  | "zelle"
  | "cash_ves";

/** Public configuration keys added in 1B (all optional: older servers may not send them). */
export interface RideConfig {
  payment_methods?: PaymentMethod[];
  offer_timeout_seconds?: number;
  search_timeout_seconds?: number;
  quote_ttl_seconds?: number;
  service_areas?: {
    name: string;
    min_lat: number;
    max_lat: number;
    min_lng: number;
    max_lng: number;
  }[];
  surge_manual_multiplier?: string;
}

export interface LatLng {
  lat: number;
  lng: number;
}

export interface Place extends LatLng {
  address: string;
}

/** GET /geo/search and /geo/reverse. */
export interface GeoResult extends LatLng {
  name: string;
  address: string;
}

export interface Quote {
  quote_id: string;
  vehicle_type: VehicleType;
  pickup: Place;
  dropoff: Place;
  distance_m: number;
  duration_s: number;
  fare: string;
  surge_multiplier: string;
  polyline: string | null;
  expires_at: string;
  // Phase 1C (optional: older servers do not send them).
  /** Promotion discount in USD ("0.60"); Kuulis credits it to the driver. */
  discount?: string;
  /** What the passenger pays: fare − discount. */
  total?: string;
  promotion?: RidePromotion | null;
  total_ves?: VesAmount | null;
}

export type RideStatus =
  | "searching"
  | "driver_assigned"
  | "driver_arrived"
  | "in_progress"
  | "completed"
  | "cancelled_by_passenger"
  | "cancelled_by_driver"
  | "cancelled_by_admin"
  | "no_drivers";

export interface RideRating {
  stars: number;
  tags: string[];
  comment?: string | null;
}

export interface RidePassenger {
  id: string;
  first_name: string;
  rating: number | string | null;
}

export interface RideDriver {
  id: string;
  first_name: string;
  rating: number | string | null;
  photo_url: string | null;
  vehicle: {
    brand: string;
    model: string;
    color: string;
    plate: string;
  } | null;
}

export interface DriverLocation extends LatLng {
  heading?: number | null;
}

export interface Ride {
  id: string;
  status: RideStatus;
  vehicle_type: VehicleType;
  pickup: Place;
  dropoff: Place;
  distance_m: number;
  duration_s: number;
  fare: string;
  surge_multiplier: string;
  payment_method: PaymentMethod;
  polyline: string | null;
  passenger: RidePassenger;
  driver: RideDriver | null;
  driver_location: DriverLocation | null;
  requested_at: string;
  assigned_at: string | null;
  arrived_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  my_rating: RideRating | null;
  // Phase 1C (optional: older servers do not send them).
  discount?: string;
  total?: string;
  promotion?: RidePromotion | null;
  /** Bs per USD, frozen when the ride was requested. */
  rates?: { bcv: string | null; binance: string | null } | null;
  total_ves?: VesAmount | null;
}

export interface Offer {
  ride_id: string;
  pickup: Place;
  dropoff: Place;
  distance_m: number;
  duration_s: number;
  pickup_distance_m: number;
  pickup_eta_s: number;
  fare: string;
  payment_method: PaymentMethod;
  passenger: { first_name: string; rating: number | string | null };
  expires_at: string;
  // Phase 1C (optional): the driver collects `total`; Kuulis credits `discount` on completion.
  discount?: string;
  total?: string;
  total_ves?: VesAmount | null;
}

export interface DriverState {
  online: boolean;
  active_ride_id: string | null;
  current_offer: Offer | null;
}

export interface RideMessage {
  id: string;
  ride_id: string;
  sender_id: string;
  text: string;
  created_at: string;
}

/** WS `ride.driver_location`. */
export interface DriverLocationEvent extends LatLng {
  ride_id: string;
  heading?: number | null;
}

// ── Phase 1C: exchange rates, promotions and wallet (docs/api/phase-1c.md) ──

export type RateSource = "bcv" | "binance";

export interface ExchangeRate {
  source: RateSource;
  /** Bs per 1 USD ("875.65"). */
  rate: string;
  origin: "auto" | "manual";
  as_of: string;
  fetched_at: string;
  stale: boolean;
}

/** GET /rates. */
export interface Rates {
  bcv: ExchangeRate | null;
  binance: ExchangeRate | null;
}

/** A USD amount in bolívares at each rate ("2101.56"), null when that rate is missing. */
export interface VesAmount {
  bcv: string | null;
  binance: string | null;
}

/** The promotion applied to a quote or ride. `code` is null for automatic promotions. */
export interface RidePromotion {
  id: string;
  name: string;
  code: string | null;
}

/** Monthly transfer allowance: only what the driver sends counts (docs/api/phase-1d.md). */
export interface TransferAllowance {
  limit: string;
  sent_this_month: string;
  available: string;
}

/** GET /wallet/me. */
export interface Wallet {
  balance: string;
  currency: string;
  // Phase 1D (optional: older servers do not send them).
  binance_pay_id?: string | null;
  transfer?: TransferAllowance | null;
}

export type WalletEntryKind =
  | "promo_credit"
  | "top_up"
  | "transfer_in"
  | "transfer_out"
  | "subscription_fee"
  | "adjustment"
  | (string & {});

/** GET /wallet/me/entries (newest first). */
export interface WalletEntry {
  id: string;
  kind: WalletEntryKind;
  /** Signed USDT amount ("0.60", "-3.00"). */
  amount: string;
  balance_after: string;
  ride_id: string | null;
  /** For `promo_credit`: the promotion name. */
  description: string | null;
  /**
   * By kind: `promo_credit` {passenger_name}; `top_up` {method, reference}; `transfer_*` {counterpart_name,
   * note}; `subscription_fee` {month}; `adjustment` {reason}.
   */
  details?: Record<string, unknown> | null;
  created_at: string;
}

// ── Phase 1D: top-ups, transfers and the monthly subscription (docs/api/phase-1d.md) ──

/** GET /wallet/top-up-info: where the driver sends USDT. */
export interface TopUpInfo {
  method: "binance_pay";
  /** Kuulis' Binance Pay ID ("" when the admin has not configured it yet). */
  pay_id: string;
  account_name: string;
  min_amount: string;
  /** True when payments are matched automatically by the payer's Binance Pay ID. */
  automatic: boolean;
}

export type TopUpStatus = "pending" | "completed" | "rejected" | "unmatched";

/** GET /wallet/me/top-ups (paginated). */
export interface TopUp {
  id: string;
  status: TopUpStatus;
  amount: string;
  method: "binance_pay";
  /** Binance order ID the driver typed. */
  reference: string | null;
  payer_binance_id: string | null;
  payer_name: string | null;
  note: string | null;
  created_at: string;
  completed_at: string | null;
  rejection_reason: string | null;
}

/** GET /wallet/recipients?q=: a driver who can receive a transfer (short name such as "Luis G."). */
export interface Recipient {
  user_id: string;
  name: string;
}

/** `details` of a 409 transfer_limit_exceeded. */
export type TransferLimitDetails = TransferAllowance;

/** One step of the fee schedule: the fee applies when the month's earnings are above `above`. */
export interface FeeTier {
  above: string;
  fee: string;
}

export type ChargeStatus = "paid" | "pending" | "waived";

/** A monthly subscription charge (created on the 1st for the previous month). */
export interface Charge {
  id: string;
  /** The month the earnings belong to ("2026-10"). */
  month: string;
  earnings: string;
  fee: string;
  status: ChargeStatus;
  /** The whole month fell in the driver's free period. */
  free_period: boolean;
  due_at: string | null;
  paid_at: string | null;
  waived_reason: string | null;
}

/** GET /wallet/me/subscription: the current month (Caracas time). */
export interface SubscriptionSummary {
  month: string;
  earnings: string;
  estimated_fee: string;
  /** End of the free period; null until the first completed trip. */
  free_until: string | null;
  in_free_period: boolean;
  tiers: FeeTier[];
  next_charge_at: string | null;
  pending: Charge[];
  overdue: boolean;
  /** Past the grace week with a pending charge: cannot go online nor receive offers. */
  blocked: boolean;
  /** Not in the written contract: completed trips this month, shown when the API sends it. */
  trips?: number | null;
}
