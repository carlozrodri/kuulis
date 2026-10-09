export type Role = 'user' | 'staff' | 'admin';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  locale: 'es' | 'en';
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

export type VehicleType = 'moto' | 'car';

export type DocumentKind =
  | 'id_card'
  | 'rif'
  | 'drivers_license'
  | 'medical_certificate'
  | 'vehicle_registration'
  | 'selfie'
  | 'vehicle_photo';

export type DocumentStatus = 'pending' | 'approved' | 'rejected';

export type DriverStatus = 'draft' | 'pending_review' | 'approved' | 'rejected' | 'suspended';

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
  method: 'PUT';
  headers: Record<string, string>;
  expires_in: number;
}

// ── Phase 1B: rides (docs/api/phase-1b.md) ──

export type PaymentMethod = 'cash_usd' | 'pago_movil' | 'binance' | 'zelle' | 'cash_ves';

/** Public configuration keys added in 1B (all optional: older servers may not send them). */
export interface RideConfig {
  payment_methods?: PaymentMethod[];
  offer_timeout_seconds?: number;
  search_timeout_seconds?: number;
  quote_ttl_seconds?: number;
  service_area?: { min_lat: number; max_lat: number; min_lng: number; max_lng: number };
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
}

export type RideStatus =
  | 'searching'
  | 'driver_assigned'
  | 'driver_arrived'
  | 'in_progress'
  | 'completed'
  | 'cancelled_by_passenger'
  | 'cancelled_by_driver'
  | 'cancelled_by_admin'
  | 'no_drivers';

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
  vehicle: { brand: string; model: string; color: string; plate: string } | null;
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
