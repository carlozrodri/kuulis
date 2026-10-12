import { describe, expect, it } from 'vitest'
import type { AdminUpdate } from '../app/types/api'
import {
  channelsServingUpdate, clampPercent, currentUpdates, isCurrentUpdate, rolloutState, shortId, updateSlot,
} from '../app/utils/updates'

const RUNTIME = 'a'.repeat(40)

function update(over: Partial<AdminUpdate>): AdminUpdate {
  return {
    id: 'u', platform: 'android', channel: 'qa', runtime_version: RUNTIME, kind: 'update', commit: null,
    message: null, rollout_percent: 100, reverted_from_id: null, created_at: '2026-10-01T00:00:00Z',
    withdrawn_at: null, published_by_email: null, ...over,
  }
}

describe('update helpers', () => {
  it('shortens ids', () => {
    expect(shortId('0123456789abcdef')).toBe('01234567')
    expect(shortId('abc')).toBe('abc')
  })

  it('picks the newest update not withdrawn per channel and runtime', () => {
    const rows = [
      update({ id: 'a', created_at: '2026-10-04T00:00:00Z', withdrawn_at: '2026-10-05T00:00:00Z' }),
      update({ id: 'b', created_at: '2026-10-03T00:00:00Z' }),
      update({ id: 'c', created_at: '2026-10-02T00:00:00Z' }),
      update({ id: 'd', created_at: '2026-10-01T00:00:00Z', runtime_version: 'b'.repeat(40) }),
      update({ id: 'e', created_at: '2026-10-01T00:00:00Z', channel: 'production', kind: 'rollback' }),
    ]
    const current = currentUpdates(rows)
    expect(current.get(updateSlot(rows[1]!))?.id).toBe('b')
    expect(current.size).toBe(3)
    expect(isCurrentUpdate(current, rows[1]!)).toBe(true)
    expect(isCurrentUpdate(current, rows[2]!)).toBe(false)
    expect(isCurrentUpdate(current, rows[0]!)).toBe(false)
    expect(isCurrentUpdate(current, rows[3]!)).toBe(true)
    expect(channelsServingUpdate(current, 'b')).toEqual(['qa'])
    expect(channelsServingUpdate(current, 'c')).toEqual([])
    expect(channelsServingUpdate(current, 'embedded')).toEqual(['production'])
  })

  it('labels the rollout', () => {
    expect(rolloutState(0)).toBe('paused')
    expect(rolloutState(10)).toBe('partial')
    expect(rolloutState(100)).toBe('full')
  })

  it('clamps percentages', () => {
    expect(clampPercent(150)).toBe(100)
    expect(clampPercent(-3)).toBe(0)
    expect(clampPercent(12.6)).toBe(13)
    expect(clampPercent('50')).toBe(50)
    expect(clampPercent('')).toBeNull()
    expect(clampPercent(Number.NaN)).toBeNull()
  })
})
