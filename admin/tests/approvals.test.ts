import { describe, expect, it } from 'vitest'
import { approvalLink, isHeld } from '../app/utils/approvals'

describe('approvals', () => {
  it('recognises a held answer', () => {
    expect(isHeld({ status: 'pending_approval', approval: {} })).toBe(true)
    expect(isHeld({ status: 'approved' })).toBe(false)
    expect(isHeld(null)).toBe(false)
  })

  it('links to the record a request is about', () => {
    expect(approvalLink({ action: 'wallet.adjust', entity_id: 'abc' })).toBe('/wallets/abc')
    expect(approvalLink({ action: 'config.update', entity_id: null })).toBe('/settings')
    expect(approvalLink({ action: 'campaign.send', entity_id: 'c1' })).toBe('/campaigns/c1')
    expect(approvalLink({ action: 'notification.broadcast', entity_id: null })).toBeNull()
  })
})
