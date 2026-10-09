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
}

export interface AppConfig {
  driver_min_age: number
  vehicle_min_year: Record<VehicleType, number>
  enabled_vehicle_types: VehicleType[]
  driver_required_documents: DocumentKind[]
  vehicle_photo_min_count: number
}
