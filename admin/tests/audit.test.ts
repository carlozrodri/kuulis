import { describe, expect, it } from 'vitest'
import { auditChanges, auditEntityLink, auditValue } from '../app/utils/audit'

describe('audit helpers', () => {
  it('lines up before and after by key', () => {
    expect(auditChanges({ before: { a: 1 }, after: { a: 2, b: 'x' } })).toEqual([
      { key: 'a', before: 1, after: 2 },
      { key: 'b', before: undefined, after: 'x' },
    ])
    expect(auditChanges({ before: null, after: null })).toEqual([])
  })

  it('links the audited record', () => {
    expect(auditEntityLink({ entity_type: 'driver', entity_id: 'd1' })).toBe('/drivers/d1')
    expect(auditEntityLink({ entity_type: 'wallet', entity_id: 'u1' })).toBe('/wallets/u1')
    expect(auditEntityLink({ entity_type: 'config', entity_id: null })).toBe('/settings')
    expect(auditEntityLink({ entity_type: 'file', entity_id: 'k' })).toBeNull()
  })

  it('formats values', () => {
    expect(auditValue(null)).toBe('—')
    expect(auditValue({ x: 1 })).toBe('{"x":1}')
    expect(auditValue(undefined)).toBe('')
  })
})
