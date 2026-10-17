export type Role = "user" | "staff" | "admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  locale: "es" | "en";
  avatar_key: string | null;
  /** Presigned URL of the profile photo; it expires, so a failed load falls back to the initials. */
  avatar_url?: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login_at: string | null;
  /** Rating received as a passenger (older servers omit it). */
  rating_avg?: number | null;
  rating_count?: number;
  /** Phase 1E: the account suspension in force, null when there is none (older servers omit it). */
  suspension?: Suspension | null;
  /** Doc 07: legal texts this user still has to accept (older servers omit it). */
  pending_legal?: string[] | null;
  /** Doc 07: explicit permissions in force, e.g. "background_location" (older servers omit it). */
  consents?: string[] | null;
}

/** "Download my data" (doc 07): a JSON file emailed as a link that lasts 24 h. */
export interface DataExport {
  id: string;
  status: 'pending' | 'ready' | 'failed' | 'expired';
  created_at: string;
  completed_at: string | null;
  expires_at: string | null;
  /** When the next export can be asked for (null after a failure: retry now). */
  next_at: string | null;
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
  /** Doc 14. Older API versions leave these out. */
  category?: NotificationCategory | null;
  /** App path ("/wallet") or https URL set by campaigns. */
  deep_link?: string | null;
  read_at: string | null;
  created_at: string;
}

export type NotificationCategory = "transactional" | "safety" | "support" | "marketing";

/** GET/PUT /notifications/preferences (doc 14). Times are "HH:MM", Caracas time. */
export interface NotificationPreferences {
  marketing_push: boolean;
  marketing_email: boolean;
  quiet_start: string;
  quiet_end: string;
  default_quiet_start: string;
  default_quiet_end: string;
  /** Doc 21: "Mucha demanda en …" pushes for drivers (older servers do not send it). */
  demand_alerts?: boolean;
}

export type NotificationPreferencesUpdate = Partial<
  Pick<NotificationPreferences, "marketing_push" | "marketing_email" | "quiet_start" | "quiet_end" | "demand_alerts">
>;

// ── Phase 1A: configuration and drivers (docs/api/phase-1a.md) ──

export type VehicleType = "moto" | "car";

export type DocumentKind =
  | "id_card"
  | "rif"
  | "drivers_license"
  | "medical_certificate"
  | "vehicle_registration"
  | "selfie"
  | "vehicle_photo"
  // Doc 12: optional "certificado de antecedentes penales".
  | "criminal_record";

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
  /** Doc 12 (older servers omit it; see DEFAULT_VERIFICATION in lib/verification.ts). */
  verification?: VerificationConfig;
  /** Doc 13 (older servers omit it). */
  support?: Partial<SupportConfig>;
}

/** Support settings the app reads (doc 13), from GET /config/public. */
export interface SupportConfig {
  response_promise_es: string;
  response_promise_en: string;
  auto_close_days: number;
  lost_item_days: number;
  lost_item_chat_hours: number;
}

/** Ongoing driver verification settings (doc 12), from GET /config/public. */
export interface VerificationConfig {
  /** Kinds that carry an expiry date (license, medical certificate, registration). */
  expiring_documents: DocumentKind[];
  /** Kinds the driver may add without being asked (criminal record certificate). */
  optional_documents: DocumentKind[];
  /** "Expires in N days" notices; the largest is the dashboard's warning window. */
  expiry_notice_days: number[];
  /** Random live selfie about this often when going online (0: never). */
  selfie_every_days: number;
}

/** Doc 12: a moto change waits as `pending` while the `active` one keeps working. */
export type VehicleStatus = "active" | "pending" | "retired";

export interface Vehicle {
  id: string;
  status?: VehicleStatus;
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
  /** Doc 12: "YYYY-MM-DD" for expiring kinds; null when unknown (approved before doc 12). */
  expires_on?: string | null;
  /** A verifier checked the date; until then the driver can still correct it. */
  expiry_confirmed?: boolean;
  created_at: string;
}

// ── Doc 12: ongoing verification ──

export type CheckKind = "selfie" | "reverification" | "document_renewal" | "vehicle_change";

export type CheckStatus = "requested" | "pending" | "approved" | "rejected" | "cancelled";

/** A document that expires within the warning window (or already did: negative `days_left`). */
export interface DocumentAlert {
  kind: DocumentKind;
  expires_on: string;
  days_left: number;
  renewal_pending: boolean;
}

/** What blocks going online and what the dashboard warns about (computed by the API). */
export interface VerificationState {
  expired: DocumentKind[];
  expiring: DocumentAlert[];
  missing_expiry: DocumentKind[];
  required_check_id: string | null;
  required_check_kind: "selfie" | "reverification" | null;
  can_go_online: boolean;
}

/** An open check: photos asked for (`requested`) or waiting for a verifier (`pending`). */
export interface DriverCheck {
  id: string;
  kind: CheckKind;
  status: CheckStatus;
  reason: string;
  document_id: string | null;
  vehicle_id: string | null;
  requested_at: string;
  submitted_at: string | null;
  reviewed_at: string | null;
  result_reason: string | null;
}

/** `details` of a 403 document_expired. */
export interface DocumentExpiredDetails {
  kinds: DocumentKind[];
}

/** `details` of a 403 selfie_required. */
export interface SelfieRequiredDetails {
  check_id: string;
  kind: "selfie" | "reverification" | null;
}

/** POST /drivers/me/vehicles: the new moto, its registration and photos (keys from checks/presign). */
export interface VehicleChangeInput {
  vehicle: VehicleInput;
  registration_key: string;
  registration_expires_on: string;
  photo_keys: string[];
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
  // Doc 12 (older servers omit them).
  /** A moto change under review; `vehicle` stays the one in use. */
  pending_vehicle?: Vehicle | null;
  verification?: VerificationState | null;
  /** Open checks only. */
  checks?: DriverCheck[];
  induction_completed_at?: string | null;
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
  // Doc 21 (optional: older servers do not send them).
  /** Why there is a surcharge: a surge zone at the pickup, the time of day or a manual one; null without one. */
  surge_reason?: "zone" | "time" | "manual" | null;
  /** Name of the surge zone when `surge_reason` is "zone". */
  surge_zone?: string | null;
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
  /** Doc 11: shown to the driver only when the city's safety rule allows it (e.g. at night). */
  photo_url?: string | null;
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
  // Doc 11: the driver types the passenger's PIN to start; only the passenger receives `start_pin`.
  pin_required?: boolean;
  start_pin?: string | null;
  // Doc 15 (optional: older servers do not send them).
  /** Stable code of why it was cancelled (`no_show`, `wrong_address`…); `cancel_reason` is the free text. */
  cancel_reason_code?: CancelReasonCode | null;
  /** Drivers who cancelled after accepting: the ride went back to `searching` this many times. */
  reassign_count?: number;
  /** While `driver_arrived`: when the wait is over and the driver may mark "No se presentó". */
  no_show_at?: string | null;
  /** While a driver is assigned: the passenger can cancel without it counting until then. */
  cancel_free_until?: string | null;
  // Doc 23 (optional: older servers do not send them).
  /** Note for the driver ("portón azul"), up to 140 characters. */
  note?: string | null;
  /** The ride was requested for this person; the driver sees the name. */
  rider_name?: string | null;
  /** Only for the passenger who requested (to send the live link to the person riding). */
  rider_phone?: string | null;
}

/** Doc 23: who actually rides when the passenger requests for someone else. */
export interface RiderInfo {
  name: string;
  /** E.164 ("+584141112233"). */
  phone: string;
}

/** GET /rides/{id}/receipt (doc 23): the receipt of a completed ride and its shareable image. */
export interface RideReceipt {
  ride_id: string;
  number: string;
  completed_at: string;
  pickup_address: string;
  dropoff_address: string;
  distance_m: number;
  duration_s: number;
  fare: string;
  discount: string;
  total: string;
  rates: { bcv: string | null; binance: string | null };
  total_ves: VesAmount;
  payment_method: PaymentMethod;
  passenger_name: string;
  driver_name: string;
  plate: string | null;
  /** Signed PNG anyone with the link can open. */
  image_url: string;
}

// ── Doc 15: cancellations and quality ──

export type PassengerCancelReason =
  | "driver_late"
  | "changed_plans"
  | "driver_asked"
  | "vehicle_mismatch"
  | "wrong_pickup"
  | "other";

export type DriverCancelReason =
  | "no_show"
  | "wrong_address"
  | "no_helmet"
  | "vehicle_problem"
  | "safety_concern"
  | "other";

export type CancelReasonCode = PassengerCancelReason | DriverCancelReason;

/** POST /rides/{id}/cancel. */
export interface CancelRideInput {
  reason_code?: CancelReasonCode;
  /** Free text, up to 500 characters. */
  reason?: string;
}

export type PauseReason = "cancel_burst" | "decline_streak" | "no_shows";

/** `details` of a 403 temporarily_paused (going online, quote, ride request). */
export interface TemporarilyPausedDetails {
  until: string;
  reason: PauseReason;
}

/** A quality pause in force for one side of the account. */
export interface QualityPause {
  until: string;
  reason: PauseReason | null;
}

/** WS `quality.paused`: `until` null means the team lifted it. */
export interface QualityPausedEvent {
  role: "driver" | "passenger";
  reason: PauseReason | null;
  until: string | null;
}

export type QualityLevel = "ok" | "warn" | "low_priority" | "review";

/** The rules behind the driver's level, from the remote configuration. */
export interface QualityThresholds {
  window_days: number;
  min_rides: number;
  /** Cancellation rates (0..1). */
  cancel_warn: number;
  cancel_low_priority: number;
  cancel_review: number;
  rating_review_below: number;
  rating_min_count: number;
  /** Cancellations within an hour that pause the driver (0: off). */
  cancel_burst: number;
  /** Offers declined in a row that pause the driver (0: off). */
  decline_streak: number;
  pause_minutes: number;
  pickup_wait_minutes: number;
}

/** GET /drivers/me/quality: rates over the last `window_days` days (null: nothing to divide by yet). */
export interface DriverQuality {
  offers: number;
  accepted: number;
  rides: number;
  cancels: number;
  no_shows: number;
  completed: number;
  acceptance_rate: number | null;
  cancel_rate: number | null;
  rating_avg: number | null;
  rating_count: number;
  level: QualityLevel;
  /** What pulls the level down: "cancel_rate", "rating", "no_shows". */
  reasons: string[];
  thresholds: QualityThresholds;
  paused_until: string | null;
  pause_reason: PauseReason | null;
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
  passenger: { first_name: string; rating: number | string | null; photo_url?: string | null };
  expires_at: string;
  // Phase 1C (optional): the driver collects `total`; Kuulis credits `discount` on completion.
  discount?: string;
  total?: string;
  total_ves?: VesAmount | null;
  // Doc 23 (optional): the passenger's note and who rides when it is someone else.
  note?: string | null;
  rider_name?: string | null;
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
  // False until staff match a first payment from the Pay ID (then top-ups are automatic).
  binance_pay_id_verified?: boolean;
  transfer?: TransferAllowance | null;
}

export type WalletEntryKind =
  | "promo_credit"
  | "top_up"
  | "transfer_in"
  | "transfer_out"
  | "subscription_fee"
  | "adjustment"
  | "referral_bonus"
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
  /** Doc 17: top-ups and paid fees have a receipt ("Ver recibo"); older servers do not send it. */
  receipt_id?: string | null;
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
  /**
   * Doc 17: why top-ups are confirmed by hand right now although matching is configured ("binance_down":
   * reconciliation with Binance has been failing). `automatic` is false then.
   */
  manual_reason?: "binance_down" | null;
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
  /** Doc 17: the support ticket of "No me llegó mi recarga", once claimed. */
  dispute_report_id?: string | null;
}

/** POST /wallet/me/top-ups/{id}/dispute (doc 17). */
export interface TopUpDisputeInput {
  /** Binance transaction id, 4–64 characters. */
  transaction_id: string;
  /** Uploaded screenshot keys (folder "uploads"), 1–3. */
  attachments: string[];
  note?: string;
}

/** `details` of a 409 top_up_dispute_open. */
export interface TopUpDisputeOpenDetails {
  report_id: string;
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
  /** Doc 17: the fee before Kuulis lowered it; null when it was not reduced. */
  original_fee?: string | null;
}

/** GET /wallet/me/subscription: the current month (Caracas time). */
export interface SubscriptionSummary {
  month: string;
  /** What counts for the fee (rides inside the free period are excluded). */
  earnings: string;
  /** Everything earned this month (fare minus promo discount); older APIs don't send it. */
  earned?: string;
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
  /** Completed trips this month. */
  trips?: number | null;
}

// ── Doc 17: receipts and monthly statements ──

export type ReceiptKind = "top_up" | "subscription_fee";

/** GET /wallet/me/receipts/{id}: a simple receipt, not a fiscal invoice (`fiscal` is false). */
export interface Receipt {
  id: string;
  /** "000123". */
  number: string;
  kind: ReceiptKind | (string & {});
  concept: string;
  amount: string;
  balance_after: string;
  reference: string | null;
  issued_at: string;
  entry_id: string;
  driver: { id: string; name: string; email: string };
  issuer: string;
  fiscal: boolean;
}

/** Money moved in a month, by kind; all positive except `adjustments` (signed). */
export interface StatementMovements {
  top_ups: string;
  promo_credits: string;
  transfers_in: string;
  transfers_out: string;
  fees: string;
  adjustments: string;
  /** Doc 22 (missing in statements cached before it). */
  referral_bonuses?: string;
}

/** GET /wallet/me/statements?month=YYYY-MM ("Estado de cuenta"). */
export interface Statement {
  month: string;
  /** Months with a statement, newest first (the month picker). */
  months: string[];
  opening_balance: string;
  closing_balance: string;
  /** Everything earned (fare minus promo discount). */
  earned: string;
  /** What counts for the fee (rides inside the free period are excluded). */
  counted: string;
  trips: number;
  tier: FeeTier | null;
  fee: string;
  /** The month is still open: the fee is an estimate. */
  estimated: boolean;
  /** The month's fee charge (billed on the 1st of the next month). */
  charge: Charge | null;
  movements: StatementMovements;
}

// ── Phase 1E: reports and account suspensions (docs/api/phase-1e.md) ──

/** A staff member or user as the API names them in moderation data. */
export interface UserBrief {
  id: string;
  name: string;
  email: string;
}

/** An account suspension in force. `until` null means indefinite; an expired one stops applying by itself. */
export interface Suspension {
  reason: string;
  suspended_at: string;
  until: string | null;
  by: UserBrief | null;
}

/** `details` of a 403 account_suspended (quote, ride request, going online). */
export interface AccountSuspendedDetails {
  until: string | null;
  reason: string;
}

export type ReportCategory =
  | "safety"
  | "harassment"
  | "driving"
  | "fare"
  | "vehicle_mismatch"
  | "lost_item"
  | "no_show"
  | "app_issue"
  | "payment"
  | "other";

export type ReportStatus = "open" | "in_review" | "resolved" | "dismissed";

export type ReportPriority = "urgent" | "normal";

/** POST /reports, GET /reports/me and /reports/me/{id}. */
export interface Report {
  id: string;
  category: ReportCategory;
  description: string;
  status: ReportStatus;
  priority: ReportPriority;
  ride_id: string | null;
  /** The side of the ride the report was made from; null for a general report. */
  reporter_role: "passenger" | "driver" | null;
  created_at: string;
  updated_at: string;
  /** The team's answer, shown to the reporter once resolved or dismissed. */
  resolution: string | null;
  resolved_at: string | null;
  // Doc 13: the report is a conversation (optional: older servers do not send them).
  source?: ReportSource;
  /** Who has to answer next; null once closed. */
  waiting_on?: "staff" | "user" | null;
  last_message_at?: string | null;
  csat?: number | null;
  /** The team wrote after the user last opened it. */
  unread?: boolean;
  can_reply?: boolean;
  can_rate?: boolean;
}

export type ReportSource = "app" | "help" | "lost_item" | "web";

export interface ReportInput {
  category: ReportCategory;
  description: string;
  ride_id?: string;
  /** Doc 13: uploaded photo keys (folder "uploads"), at most 4. */
  attachments?: string[];
  /** Doc 13: the help article the user came from ("Contactar a soporte"). */
  help_article_id?: string;
}

/** GET /reports/me/{id}/messages (doc 13), oldest first. */
export interface ReportMessage {
  id: string;
  author_kind: "user" | "staff" | "system";
  /** Staff first name; null for the user and automatic lines. */
  author_name: string | null;
  mine: boolean;
  body: string;
  attachments: { key: string; url: string }[];
  created_at: string;
}

// ── Doc 13: help center ──

export type HelpTopic = "account" | "rides" | "payments" | "wallet" | "safety" | "documents" | "app";
export type HelpAudience = "all" | "passenger" | "driver";

export interface HelpArticleSummary {
  id: string;
  slug: string;
  locale: string;
  topic: HelpTopic;
  audience: HelpAudience;
  title: string;
  /** Plain text, ≤180 chars. */
  excerpt: string;
  position: number;
  updated_at: string;
}

export interface HelpArticle extends HelpArticleSummary {
  body_md: string;
}

// ── Doc 13: lost item ──

export interface LostItem {
  id: string;
  ride_id: string;
  description: string;
  answer: "has_it" | "not_found" | null;
  answered_at: string | null;
  /** The ride chat stays open until then when the driver has it. */
  chat_until: string | null;
  chat_open: boolean;
  report_id: string | null;
  created_at: string;
}

/** `details` of a 409 report_already_open. */
export interface ReportAlreadyOpenDetails {
  report_id: string;
}

/** GET /drivers/me/stats: completed rides and earnings (fare minus promo discount), Caracas days. */
export interface PeriodStats {
  rides: number;
  earnings: string;
}

export interface DriverStats {
  today: PeriodStats;
  yesterday: PeriodStats;
  /** Monday to today. */
  week: PeriodStats;
  /** 1st of the month to today. */
  month: PeriodStats;
  last_month: PeriodStats;
  /** Last 7 days, oldest first ("YYYY-MM-DD"). */
  by_day: (PeriodStats & { date: string })[];
  total_rides: number;
  rating: number | null;
  /** Doc 23: compliments passengers gave (rating tags), most given first. */
  compliments?: { tag: string; count: number }[];
}

/** GET /rides/me/stats: the passenger's completed rides. */
export interface FrequentPlace extends Place {
  rides: number;
}

export interface PassengerStats {
  rides: number;
  distance_m: number;
  /** Paid in USD (fare minus promo discount). */
  spent: string;
  /** Most visited destinations, most rides first. */
  frequent_places: FrequentPlace[];
}

/** GET /users/me/places: home and work (one each) and other saved places. */
export type PlaceKind = "home" | "work" | "other";

export interface SavedPlace extends Place {
  id: string;
  kind: PlaceKind;
  /** Custom name for "other" places ("Gym"); empty for home and work. */
  label: string;
  /** Doc 23: icon of an "other" place (null: the star). */
  icon?: PlaceIcon | null;
  updated_at: string;
}

export type PlaceIcon = "star" | "heart" | "dumbbell" | "school" | "store" | "users" | "utensils" | "hospital";

/** What the invite program offers (doc 22). */
export interface ReferralProgramInfo {
  /** New codes are accepted. */
  active: boolean;
  reward_usd: string;
  required_trips: number;
  window_days: number;
  referred_free_month: boolean;
  ends_at: string | null;
}

/** A driver who joined with the code, as the inviter sees them. */
export interface ReferralInvitee {
  name: string;
  joined_at: string;
  approved: boolean;
  status: "pending" | "reviewing" | "rewarded" | "expired" | "not_eligible";
  trips: number;
  required_trips: number;
  /** Null until approved. */
  deadline_at: string | null;
  reward_usd: string | null;
  /** free_month: the first version of the program. */
  reward_kind: "free_month" | "wallet_credit" | null;
}

/** GET /referrals/me: the driver's invite code and what it has earned. */
export interface ReferralSummary {
  /** Null until the user is an approved driver. */
  code: string | null;
  /** The web invite page (https://<site>/i/CODE). */
  share_url: string | null;
  invited: number;
  rewarded: number;
  /** Wallet credit earned with invites. */
  earned_usd: string;
  /** Free months of subscription earned and not used yet. */
  free_months: number;
  referred_by: string | null;
  /** A driver before their first trip can still enter someone's code. */
  can_redeem: boolean;
  program: ReferralProgramInfo;
  /** Newest first, at most 50. */
  invitees: ReferralInvitee[];
}

/** An APK published for a channel (doc 09). `download_url` is a presigned link valid about an hour. */
export interface AppRelease {
  version: string;
  build: number;
  /** Bytes. */
  size: number;
  sha256: string;
  md5: string;
  notes: string | null;
  is_mandatory: boolean;
  created_at: string;
  download_url: string | null;
}

/** GET /app/version: the newest APK for this channel and whether this build must update. */
export interface AppVersionCheck {
  latest: AppRelease | null;
  minimum_build: number;
  update_available: boolean;
  update_required: boolean;
}

// ---- Trip safety (doc 11) ----

/** Up to five; `auto_share` offers to share every ride, only between from/to (Caracas time) when set. */
export interface TrustedContact {
  id: string;
  name: string;
  phone: string;
  auto_share: boolean;
  auto_share_from: string | null;
  auto_share_to: string | null;
}

export interface ShareLink {
  url: string;
  token: string;
}

export type SafetyAlertKind = 'sos' | 'stop' | 'deviation' | 'overtime';

/** An open SOS of mine, or a "¿Todo bien?" waiting for my answer. */
export interface SafetyAlert {
  id: string;
  ride_id: string | null;
  kind: SafetyAlertKind;
  status: 'checking' | 'open' | 'acknowledged' | 'resolved' | 'dismissed';
  created_at: string;
  check_in_deadline?: string | null;
}

export interface SosResult extends SafetyAlert {
  share_url: string | null;
  location_seconds: number;
  /** The Kuulis team was told (only when there is someone on call). */
  team_alerted?: boolean;
}
