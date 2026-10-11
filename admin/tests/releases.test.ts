import { describe, expect, it } from 'vitest'
import type { AdminRelease } from '../app/types/api'
import { channelsOfferingBuild, formatMegabytes, latestByChannel, shortHash } from '../app/utils/releases'

function release(over: Partial<AdminRelease>): AdminRelease {
  return {
    id: 'r', platform: 'android', channel: 'qa', version: '1.0.0', build: 1, size: 0, sha256: '', md5: '',
    notes: null, is_mandatory: false, created_at: '2026-10-01T00:00:00Z', withdrawn_at: null, file_key: 'k',
    published_by_email: null, download_url: null, ...over,
  }
}

describe('release helpers', () => {
  it('formats sizes in MB', () => {
    expect(formatMegabytes(50_000_000, 'en')).toBe('50 MB')
    expect(formatMegabytes(1_500_000, 'en')).toBe('1.5 MB')
    expect(formatMegabytes(null, 'en')).toBe('—')
  })

  it('shortens hashes', () => {
    expect(shortHash('0123456789abcdef0123')).toBe('01234567…0123')
    expect(shortHash('abc')).toBe('abc')
  })

  it('picks the highest build not withdrawn per channel', () => {
    const latest = latestByChannel([
      release({ id: 'a', build: 3, withdrawn_at: '2026-10-02T00:00:00Z' }),
      release({ id: 'b', build: 2 }),
      release({ id: 'c', build: 1 }),
      release({ id: 'd', build: 2, channel: 'production' }),
    ])
    expect(latest.get('android:qa')?.id).toBe('b')
    expect(latest.get('android:production')?.id).toBe('d')
    expect(channelsOfferingBuild(latest, 'android', 2).sort()).toEqual(['production', 'qa'])
    expect(channelsOfferingBuild(latest, 'android', 3)).toEqual([])
  })
})
