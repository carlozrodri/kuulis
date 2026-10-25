import { describe, expect, it } from 'vitest'
import type { MarketingAsset, MarketingPerformanceRow, MarketingVariant } from '../app/types/api'
import { MARKETING_PLATFORMS, MARKETING_STATUSES } from '../app/types/api'
import {
  caracasDayOf,
  emptyMetricForm,
  formatClock,
  formatHashtags,
  fromCaracasInput,
  inTab,
  marketingStatusColor,
  metricBody,
  parseHashtags,
  performanceTotals,
  platformIcon,
  platformLabel,
  playableAssets,
  readableScript,
  shiftMonth,
  tabStatus,
  toCaracasInput,
  usableAssets,
  variantMissing,
} from '../app/utils/marketing'
import en from '../i18n/locales/en.json'
import es from '../i18n/locales/es.json'

const asset = (over: Partial<MarketingAsset>): MarketingAsset => ({
  id: 'a1',
  kind: 'video',
  role: 'final',
  source: 'remotion',
  model: null,
  prompt: null,
  credits_used: null,
  cost_usd: null,
  rights: null,
  s3_key: 'k',
  filename: 'v.mp4',
  content_type: 'video/mp4',
  size: 10,
  width: null,
  height: null,
  duration_s: null,
  uploaded_at: '2026-11-04T10:00:00Z',
  created_at: '2026-11-04T10:00:00Z',
  download_url: null,
  ...over,
})

const variant = (over: Partial<MarketingVariant>): MarketingVariant => ({
  id: 'v1',
  platform: 'tiktok',
  account: '@kuulis',
  hook_index: 0,
  title: null,
  caption: '',
  hashtags: [],
  checklist: [],
  ai_label: true,
  duration_s: null,
  asset_id: null,
  cover_asset_id: null,
  scheduled_at: null,
  utm_url: '',
  publication: null,
  ...over,
})

describe('Caracas times', () => {
  it('shows and reads datetime-local values in Caracas (UTC-4)', () => {
    expect(toCaracasInput('2026-11-04T23:30:00Z')).toBe('2026-11-04T19:30')
    expect(toCaracasInput('2026-11-05T02:00:00Z')).toBe('2026-11-04T22:00')
    expect(fromCaracasInput('2026-11-04T19:30')).toBe('2026-11-04T23:30:00.000Z')
    expect(fromCaracasInput('')).toBeNull()
    expect(fromCaracasInput('mañana')).toBeNull()
    expect(toCaracasInput(null)).toBe('')
  })

  it('finds the Caracas day of a late-night post', () => {
    expect(caracasDayOf('2026-11-05T02:00:00Z')).toBe('2026-11-04')
  })
})

describe('hashtags', () => {
  it('parses typed text without signs or repeats', () => {
    expect(parseHashtags('#Caracas motorizados, #caracas  ##moto')).toEqual(['Caracas', 'motorizados', 'moto'])
    expect(parseHashtags('   ')).toEqual([])
  })

  it('formats them with the sign', () => {
    expect(formatHashtags(['Caracas', '#moto'])).toBe('#Caracas #moto')
  })
})

describe('metrics', () => {
  it('sends only typed numbers and the completion as 0..1', () => {
    const form = { ...emptyMetricForm(), views: 1500, completion_rate: 42, likes: 0 }
    expect(metricBody(form)).toEqual({ views: 1500, completion_rate: 0.42, likes: 0 })
    expect(metricBody({ ...emptyMetricForm(), completion_rate: 140 })).toEqual({ completion_rate: 1 })
  })

  it('adds up the latest numbers of each post', () => {
    const row = (views: number | null, rate: number | null): MarketingPerformanceRow => ({
      publication_id: 'p',
      content_id: 'c',
      code: 'K',
      title: 'T',
      pillar: null,
      format: null,
      platform: 'tiktok',
      hook_index: 0,
      url: null,
      published_at: '2026-11-04T23:30:00Z',
      snapshots: 1,
      latest: views === null
        ? null
        : { id: 'm', taken_at: '', age_h: 24, source: 'manual', views, reach: null, avg_watch_s: null, completion_rate: rate, likes: 2, comments: null, shares: null, saves: null, follows: null, profile_visits: null, link_clicks: null },
    })
    const totals = performanceTotals([row(1000, 0.5), row(500, null), row(null, null)])
    expect(totals).toMatchObject({ publications: 3, views: 1500, likes: 4, completion: 0.5 })
    expect(performanceTotals([]).completion).toBeNull()
  })
})

describe('variants', () => {
  const assets = [asset({ id: 'v' }), asset({ id: 'img', kind: 'imagen' }), asset({ id: 'aud', kind: 'audio' }), asset({ id: 'pending', uploaded_at: null })]

  it('offers only uploaded files that fit', () => {
    expect(usableAssets(assets, 'file').map(a => a.id)).toEqual(['v', 'img'])
    expect(usableAssets(assets, 'cover').map(a => a.id)).toEqual(['img'])
  })

  it('lists what blocks approval, like the API', () => {
    expect(variantMissing(variant({}), assets)).toEqual(['asset_id', 'scheduled_at'])
    expect(variantMissing(variant({ asset_id: 'pending', scheduled_at: '2026-11-04T23:30:00Z' }), assets)).toEqual(['asset_id'])
    expect(variantMissing(variant({ asset_id: 'v', scheduled_at: '2026-11-04T23:30:00Z' }), assets)).toEqual([])
  })
})

describe('labels', () => {
  it('has a color, icon, label and translation for every status and platform', () => {
    for (const status of MARKETING_STATUSES) {
      expect(marketingStatusColor[status]).toBeTruthy()
      expect(es.marketing.statuses[status]).toBeTruthy()
      expect(en.marketing.statuses[status]).toBeTruthy()
      expect(es.marketing.moveTo[status]).toBeTruthy()
    }
    for (const platform of MARKETING_PLATFORMS) {
      expect(platformIcon[platform]).toMatch(/^i-lucide-/)
      expect(platformLabel[platform]).toBeTruthy()
    }
  })

  it('moves months across the year', () => {
    expect(shiftMonth('2026-12', 1)).toBe('2027-01')
    expect(shiftMonth('2026-01', -1)).toBe('2025-12')
  })
})

describe('marketing list', () => {
  it('shows lengths as a clock', () => {
    expect(formatClock(15.2)).toBe('0:15')
    expect(formatClock(75)).toBe('1:15')
    expect(formatClock(null)).toBe('')
  })

  it('hides archived and discarded pieces from the active tab only', () => {
    expect(inTab('guion', 'activas')).toBe(true)
    expect(inTab('descartado', 'activas')).toBe(false)
    expect(inTab('descartado', 'descartado')).toBe(true)
    expect(inTab('guion', 'producido')).toBe(false)
    expect(tabStatus('activas')).toBeUndefined()
    expect(tabStatus('aprobado')).toBe('aprobado')
  })
})

describe('piece page', () => {
  it('reads the agents\' script and ignores malformed parts', () => {
    const parts = readableScript({
      idea: ' El regateo de siempre ',
      cta: 'Descárgala',
      hechos: ['H7', 3],
      escenas: [{ desde_s: 0, hasta_s: 5, plano: 'Chacao', voz: '¿Cuánto?', texto: '' }, 'roto'],
      prompts: [{ plano: '0–5 s', modelo: 'wan-3.0', prompt: 'A woman asks', costo_lista_usd: 0.5, herramienta: 'higgsfield' }, { plano: 'sin prompt' }],
    })
    expect(parts.idea).toBe('El regateo de siempre')
    expect(parts.facts).toEqual(['H7'])
    expect(parts.scenes).toEqual([{ from: 0, to: 5, shot: 'Chacao', voice: '¿Cuánto?', text: '' }])
    expect(parts.prompts).toHaveLength(1)
    expect(parts.prompts[0]).toMatchObject({ model: 'wan-3.0', costUsd: 0.5, tool: 'higgsfield' })
    expect(readableScript(null)).toEqual({ idea: '', cta: '', scenes: [], prompts: [], facts: [] })
  })

  it('plays the newest final video first and skips audio and pending uploads', () => {
    const list = playableAssets([
      asset({ download_url: 'https://s3.test/f', id: 'cover', kind: 'imagen', role: 'portada' }),
      asset({ download_url: 'https://s3.test/f', id: 'take', role: 'fuente' }),
      asset({ download_url: 'https://s3.test/f', id: 'old', created_at: '2026-10-25T09:00:00Z' }),
      asset({ download_url: 'https://s3.test/f', id: 'new', created_at: '2026-10-25T11:00:00Z' }),
      asset({ download_url: 'https://s3.test/f', id: 'voice', kind: 'audio' }),
      asset({ download_url: 'https://s3.test/f', id: 'pending', uploaded_at: null }),
    ])
    expect(list.map(a => a.id)).toEqual(['new', 'old', 'take', 'cover'])
  })
})
