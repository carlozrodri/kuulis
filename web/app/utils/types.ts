export interface FeeTier {
  above: string
  fee: string
}

export interface PublicSite {
  cities: string[]
  driver: {
    min_age: number
    vehicle_types: string[]
    vehicle_min_year: Record<string, number>
    documents: string[]
    vehicle_photo_min_count: number
  }
  free_months: number
  fee_tiers: FeeTier[]
  payment_methods: string[]
}

export const LEGAL_KINDS = ['terms', 'privacy', 'community', 'driver_terms', 'wallet'] as const
export type LegalKind = typeof LEGAL_KINDS[number]

export function isLegalKind(value: unknown): value is LegalKind {
  return typeof value === 'string' && (LEGAL_KINDS as readonly string[]).includes(value)
}

export interface LegalSummary {
  kind: LegalKind
  version: number
  locale: string
  title: string
  summary: string
  requires_reacceptance: boolean
  published_at: string
}

export interface LegalDocument extends LegalSummary {
  body_md: string
}

/** GET /app/version: the newest APK published for this environment's channel (doc 09). */
export interface AppRelease {
  version: string
  build: number
  size: number
  sha256: string
  notes: string | null
  created_at: string
}

export interface VersionCheck {
  latest: AppRelease | null
}

/** Help center (doc 13): topics in the order the site lists them. */
export const HELP_TOPICS = ['account', 'rides', 'payments', 'wallet', 'safety', 'documents', 'app'] as const
export type HelpTopic = typeof HELP_TOPICS[number]
export type HelpAudience = 'all' | 'passenger' | 'driver'

export interface HelpArticleSummary {
  id: string
  slug: string
  locale: string
  topic: HelpTopic
  audience: HelpAudience
  title: string
  excerpt: string
  position: number
  updated_at: string
}

export interface HelpArticle extends HelpArticleSummary {
  body_md: string
}

/** The parts of GET /config/public the website reads (the rest is for the apps). */
export interface PublicConfig {
  app_links?: { support_whatsapp?: string, support_email?: string, emergency_number?: string }
  safety?: { pin_areas?: string[] }
  support?: { response_promise_es?: string, response_promise_en?: string }
}

export interface ContactChallenge {
  challenge: string
  difficulty: number
  expires_in: number
}

export type ContactCategory = 'app_issue' | 'other'
