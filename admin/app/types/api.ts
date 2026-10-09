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
