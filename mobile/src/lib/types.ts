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

export interface AppConfig {
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
