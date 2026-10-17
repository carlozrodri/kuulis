import { describe, expect, it } from 'vitest'
import { appInviteLink, formatInviteCode, normalizeInviteCode } from '../app/utils/invite'

describe('invite page', () => {
  it('normalizes and formats codes', () => {
    expect(normalizeInviteCode(' ab3-k7q ')).toBe('AB3K7Q')
    expect(formatInviteCode('ab3k7q')).toBe('AB3 K7Q')
    expect(formatInviteCode('abc')).toBe('ABC')
  })

  it('links to the invite screen of the app', () => {
    expect(appInviteLink('ab3-k7q')).toBe('kuulis://profile/invite?code=AB3K7Q')
  })
})
