import type {
  LearningStatus,
  MarketingAccountStatus,
  MarketingAsset,
  MarketingMetricFields,
  MarketingPerformanceRow,
  MarketingPlatform,
  MarketingStatus,
  MarketingVariant,
} from '~/types/api'

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

export const marketingStatusColor: Record<MarketingStatus, BadgeColor> = {
  idea: 'neutral',
  guion: 'info',
  revisado: 'info',
  producido: 'warning',
  aprobado: 'primary',
  publicado: 'success',
  archivado: 'neutral',
  descartado: 'error',
}

export const learningStatusColor: Record<LearningStatus, BadgeColor> = {
  hipotesis: 'warning',
  probado: 'success',
  descartado: 'neutral',
}

export const accountStatusColor: Record<MarketingAccountStatus, BadgeColor> = {
  pendiente: 'warning',
  activa: 'success',
  suspendida: 'error',
}

/** Lucide has no TikTok or WhatsApp logo: generic icons stand in for them. */
export const platformIcon: Record<MarketingPlatform, string> = {
  tiktok: 'i-lucide-music-2',
  instagram: 'i-lucide-instagram',
  youtube: 'i-lucide-youtube',
  whatsapp: 'i-lucide-message-circle',
  facebook: 'i-lucide-facebook',
}

/** Brand names: the same in every language. */
export const platformLabel: Record<MarketingPlatform, string> = {
  tiktok: 'TikTok',
  instagram: 'Instagram',
  youtube: 'YouTube Shorts',
  whatsapp: 'WhatsApp',
  facebook: 'Facebook',
}

/** Caption limits per network (TikTok allows more, but Kuulis keeps captions short). */
export const CAPTION_MAX = 2200

// Caracas is UTC-4 all year (no daylight saving), so conversions are plain arithmetic.
const CARACAS_OFFSET_MS = -4 * 3_600_000
const pad = (n: number) => String(n).padStart(2, '0')

/** ISO timestamp → `YYYY-MM-DDTHH:mm` in Caracas time (what a `datetime-local` input binds). */
export function toCaracasInput(value: string | null | undefined): string {
  if (!value) return ''
  const time = new Date(value).getTime()
  if (Number.isNaN(time)) return ''
  const d = new Date(time + CARACAS_OFFSET_MS)
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`
}

/** `datetime-local` value read as Caracas time → ISO timestamp (UTC), null when empty or invalid. */
export function fromCaracasInput(value: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null
  const time = new Date(`${value}:00-04:00`).getTime()
  return Number.isNaN(time) ? null : new Date(time).toISOString()
}

/** Caracas day (YYYY-MM-DD) of a timestamp. */
export function caracasDayOf(value: string): string {
  return toCaracasInput(value).slice(0, 10)
}

/** "19:30" in Caracas. */
export function formatCaracasTime(value: string | null | undefined, locale: string): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', timeZone: 'America/Caracas' }).format(new Date(value))
}

/** "mar 4 nov, 19:30" in Caracas. */
export function formatCaracasDateTime(value: string | null | undefined, locale: string): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(locale, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/Caracas',
  }).format(new Date(value))
}

/** "#Caracas motorizados, #caracas" → ["Caracas", "motorizados"] (no sign, no repeats ignoring case). */
export function parseHashtags(text: string): string[] {
  const seen: string[] = []
  for (const raw of text.split(/[\s,]+/)) {
    const tag = raw.replace(/^#+/, '').trim()
    if (tag && !seen.some(t => t.toLowerCase() === tag.toLowerCase())) seen.push(tag)
  }
  return seen
}

export function formatHashtags(tags: string[]): string {
  return tags.map(t => (t.startsWith('#') ? t : `#${t}`)).join(' ')
}

export const METRIC_FIELDS = [
  'views',
  'reach',
  'avg_watch_s',
  'completion_rate',
  'likes',
  'comments',
  'shares',
  'saves',
  'follows',
  'profile_visits',
  'link_clicks',
] as const satisfies readonly (keyof MarketingMetricFields)[]

/** Blank inputs are undefined (what a number input's v-model binds when empty). */
export type MetricForm = Record<typeof METRIC_FIELDS[number], number | undefined>

export function emptyMetricForm(): MetricForm {
  return Object.fromEntries(METRIC_FIELDS.map(k => [k, undefined])) as MetricForm
}

/** Form values → request body: the completion rate is typed as a percentage, sent as 0..1. */
export function metricBody(form: MetricForm): Partial<MarketingMetricFields> {
  const body: Partial<MarketingMetricFields> = {}
  for (const key of METRIC_FIELDS) {
    const value = form[key]
    if (typeof value !== 'number' || !Number.isFinite(value)) continue
    body[key] = key === 'completion_rate' ? Math.min(1, Math.max(0, value / 100)) : value
  }
  return body
}

export interface PerformanceTotals {
  publications: number
  views: number
  likes: number
  comments: number
  shares: number
  saves: number
  /** Average completion of the rows that have it, 0..1, or null. */
  completion: number | null
}

export function performanceTotals(rows: MarketingPerformanceRow[]): PerformanceTotals {
  const sum = (key: 'views' | 'likes' | 'comments' | 'shares' | 'saves') =>
    rows.reduce((acc, r) => acc + (r.latest?.[key] ?? 0), 0)
  const rates = rows.map(r => r.latest?.completion_rate).filter((v): v is number => typeof v === 'number')
  return {
    publications: rows.length,
    views: sum('views'),
    likes: sum('likes'),
    comments: sum('comments'),
    shares: sum('shares'),
    saves: sum('saves'),
    completion: rates.length ? rates.reduce((a, b) => a + b, 0) / rates.length : null,
  }
}

/** Uploaded files a variant can use: videos/images for the post, images for the cover. */
export function usableAssets(assets: MarketingAsset[], purpose: 'file' | 'cover'): MarketingAsset[] {
  return assets.filter(a => a.uploaded_at && (purpose === 'cover' ? a.kind === 'imagen' : a.kind !== 'audio'))
}

/** What a variant still needs before the piece can be approved (mirrors the API's check). */
export function variantMissing(variant: MarketingVariant, assets: MarketingAsset[]): ('asset_id' | 'scheduled_at')[] {
  const missing: ('asset_id' | 'scheduled_at')[] = []
  const asset = assets.find(a => a.id === variant.asset_id)
  if (!asset?.uploaded_at) missing.push('asset_id')
  if (!variant.scheduled_at) missing.push('scheduled_at')
  return missing
}

export function formatBytes(bytes: number, locale: string): string {
  const mb = bytes / (1024 * 1024)
  if (mb >= 1) return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(mb)} MB`
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(bytes / 1024)} KB`
}

/** "2026-11" → "2026-10" / "2026-12". */
export function shiftMonth(month: string, n: number): string {
  const [y, m] = month.split('-').map(Number)
  const index = (y ?? 2026) * 12 + (m ?? 1) - 1 + n
  return `${Math.floor(index / 12)}-${pad((index % 12) + 1)}`
}

/** 15.2 → "0:15", 75 → "1:15". */
export function formatClock(seconds: number | null | undefined): string {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) return ''
  const total = Math.round(seconds)
  return `${Math.floor(total / 60)}:${pad(total % 60)}`
}

/** The list's tabs: "active" is everything still in play (not archived or discarded). */
export const PIECE_TABS = ['activas', 'idea', 'guion', 'revisado', 'producido', 'aprobado', 'publicado', 'archivado', 'descartado'] as const
export type PieceTab = typeof PIECE_TABS[number]
const CLOSED: MarketingStatus[] = ['archivado', 'descartado']

/** Status sent to the API for a tab (none for "active", which is filtered in the browser). */
export function tabStatus(tab: PieceTab): MarketingStatus | undefined {
  return tab === 'activas' ? undefined : tab
}

export function inTab(status: MarketingStatus, tab: PieceTab): boolean {
  return tab === 'activas' ? !CLOSED.includes(status) : status === tab
}

export interface ScriptScene {
  from: number | null
  to: number | null
  shot: string
  voice: string
  text: string
}

export interface ScriptPrompt {
  shot: string
  model: string
  prompt: string
  tool: string
  costUsd: number | null
  requestId: string
}

/** The parts of a script the piece page shows as text (the raw JSON stays one click away). */
export interface ReadableScript {
  idea: string
  cta: string
  scenes: ScriptScene[]
  prompts: ScriptPrompt[]
  facts: string[]
}

const text = (value: unknown) => (typeof value === 'string' ? value.trim() : '')
const num = (value: unknown) => (typeof value === 'number' && Number.isFinite(value) ? value : null)
const records = (value: unknown) =>
  (Array.isArray(value) ? value : []).filter((v): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v))

/** Reads the agents' script format (docs/marketing/09: idea, cta, escenas, prompts, hechos). */
export function readableScript(script: Record<string, unknown> | null | undefined): ReadableScript {
  const s = script ?? {}
  return {
    idea: text(s.idea),
    cta: text(s.cta),
    scenes: records(s.escenas).map(e => ({ from: num(e.desde_s), to: num(e.hasta_s), shot: text(e.plano), voice: text(e.voz), text: text(e.texto) })),
    prompts: records(s.prompts).map(p => ({
      shot: text(p.plano),
      model: text(p.modelo),
      prompt: text(p.prompt),
      tool: text(p.herramienta),
      costUsd: num(p.costo_lista_usd),
      requestId: text(p.request_id),
    })).filter(p => p.prompt),
    facts: (Array.isArray(s.hechos) ? s.hechos : []).filter((h): h is string => typeof h === 'string'),
  }
}

/** Videos and images that can be watched on the piece page, newest first, finals before the rest. */
export function playableAssets(assets: MarketingAsset[]): MarketingAsset[] {
  const rank = (a: MarketingAsset) => (a.role === 'final' ? 0 : a.role === 'portada' ? 2 : 1) + (a.kind === 'video' ? 0 : 3)
  return assets
    .filter(a => a.uploaded_at && a.download_url && a.kind !== 'audio')
    .sort((a, b) => rank(a) - rank(b) || b.created_at.localeCompare(a.created_at))
}
