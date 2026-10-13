import { describe, expect, it } from 'vitest'
import type { DocumentKind } from '../app/types/api'
import { changedSettings, defaultSettings, parseNoticeDays, settingsFromConfig, settingsToPayload, validateSettings } from '../app/utils/settings'
import {
  checkChecklist,
  checklistComplete,
  checklistKey,
  checkNeedsExpiry,
  checkReasons,
  checkSuspends,
  daysBetween,
  DEFAULT_VERIFICATION,
  documentChecklist,
  documentReasons,
  expiryBadge,
  expiryUnconfirmed,
  nearestExpiry,
  nextInQueue,
  rotateBy,
  shortcutFor,
  zoomBy,
  ZOOM_MAX,
  ZOOM_MIN,
} from '../app/utils/verification'

const expiring = DEFAULT_VERIFICATION.expiring_documents
const today = '2026-10-13'
const doc = (kind: DocumentKind, expires_on: string | null = null) => ({ kind, expires_on })

describe('expiry badges (doc 12)', () => {
  it('counts calendar days', () => {
    expect(daysBetween(today, '2026-10-14')).toBe(1)
    expect(daysBetween(today, '2026-10-01')).toBe(-12)
    expect(daysBetween(today, '2026-11-12')).toBe(30)
  })

  it('labels expired, today, soon, valid and missing dates', () => {
    expect(expiryBadge(doc('drivers_license', '2026-10-01'), today, expiring)).toEqual({ key: 'expired', days: -12, color: 'error' })
    expect(expiryBadge(doc('drivers_license', today), today, expiring)).toEqual({ key: 'today', days: 0, color: 'error' })
    expect(expiryBadge(doc('drivers_license', '2026-10-18'), today, expiring)).toEqual({ key: 'soon', days: 5, color: 'error' })
    expect(expiryBadge(doc('medical_certificate', '2026-11-01'), today, expiring)).toEqual({ key: 'soon', days: 19, color: 'warning' })
    expect(expiryBadge(doc('vehicle_registration', '2027-06-01'), today, expiring)?.key).toBe('valid')
    expect(expiryBadge(doc('drivers_license'), today, expiring)).toEqual({ key: 'noDate', days: null, color: 'warning' })
    // Kinds that do not expire get no badge unless a date was typed anyway.
    expect(expiryBadge(doc('id_card'), today, expiring)).toBeNull()
    expect(expiryBadge(doc('id_card', '2026-10-20'), today, expiring)?.key).toBe('soon')
  })

  it('flags dates nobody confirmed', () => {
    expect(expiryUnconfirmed({ expires_on: '2027-01-01', expiry_confirmed: false })).toBe(true)
    expect(expiryUnconfirmed({ expires_on: '2027-01-01', expiry_confirmed: true })).toBe(false)
    expect(expiryUnconfirmed({ expires_on: null })).toBe(false)
  })

  it('picks the most urgent expiry for the list', () => {
    expect(nearestExpiry(null)).toBeNull()
    const state = {
      expired: ['drivers_license'] as DocumentKind[],
      expiring: [
        { kind: 'medical_certificate' as const, expires_on: '2026-10-20', days_left: 7, renewal_pending: false },
        { kind: 'drivers_license' as const, expires_on: '2026-10-10', days_left: -3, renewal_pending: true },
      ],
      missing_expiry: [],
      required_check_id: null,
      required_check_kind: null,
      can_go_online: false,
    }
    expect(nearestExpiry(state)?.kind).toBe('drivers_license')
  })

  it('asks for a date on renewals of expiring documents and moto changes', () => {
    expect(checkNeedsExpiry('vehicle_change', null, expiring)).toBe(true)
    expect(checkNeedsExpiry('document_renewal', 'drivers_license', expiring)).toBe(true)
    expect(checkNeedsExpiry('document_renewal', 'id_card', expiring)).toBe(false)
    expect(checkNeedsExpiry('selfie', null, expiring)).toBe(false)
  })
})

describe('review checklists and reasons', () => {
  it('adds "vigente" only to expiring kinds', () => {
    expect(documentChecklist('drivers_license', expiring)).toEqual(['legible', 'nameMatches', 'numberMatches', 'valid'])
    expect(documentChecklist('id_card', expiring)).not.toContain('valid')
    expect(documentChecklist('id_card', ['id_card'])).toContain('valid')
  })

  it('has a checklist per check kind', () => {
    expect(checkChecklist('selfie', null, expiring)).toEqual(['clearPhoto', 'live', 'faceMatchesSelfie', 'faceMatchesId'])
    expect(checkChecklist('reverification', null, expiring)).toContain('plateMatches')
    expect(checkChecklist('document_renewal', 'medical_certificate', expiring)).toEqual(['legible', 'nameMatches', 'valid'])
    expect(checkChecklist('vehicle_change', null, expiring)).toContain('valid')
  })

  it('needs every item ticked', () => {
    const items = ['legible', 'valid']
    expect(checklistComplete(items, {})).toBe(false)
    expect(checklistComplete(items, { legible: true, valid: false })).toBe(false)
    expect(checklistComplete(items, { legible: true, valid: true })).toBe(true)
    expect(checklistComplete([], {})).toBe(true)
  })

  it('offers predefined reasons with "other" last', () => {
    expect(documentReasons('selfie', expiring)).toEqual(['blurry', 'notLive', 'faceMismatch', 'other'])
    expect(documentReasons('drivers_license', expiring)).toContain('expired')
    expect(documentReasons('id_card', expiring)).not.toContain('expired')
    expect(checkReasons('reverification', null, expiring).at(-1)).toBe('other')
    expect(checkReasons('document_renewal', 'vehicle_registration', expiring)).toContain('plateMismatch')
  })

  it('suspends only for selfies and re-verifications', () => {
    expect(checkSuspends('selfie')).toBe(true)
    expect(checkSuspends('reverification')).toBe(true)
    expect(checkSuspends('document_renewal')).toBe(false)
    expect(checkSuspends('vehicle_change')).toBe(false)
  })
})

describe('review shortcuts', () => {
  it('maps keys to actions', () => {
    expect(shortcutFor({ key: 'a' })).toBe('approve')
    expect(shortcutFor({ key: 'R' })).toBe('reject')
    expect(shortcutFor({ key: '+' })).toBe('zoomIn')
    expect(shortcutFor({ key: '=' })).toBe('zoomIn')
    expect(shortcutFor({ key: '-' })).toBe('zoomOut')
    expect(shortcutFor({ key: 'o' })).toBe('rotate')
    expect(shortcutFor({ key: 'ArrowLeft' })).toBe('prev')
    expect(shortcutFor({ key: 'ArrowRight' })).toBe('next')
    expect(shortcutFor({ key: 'n' })).toBe('nextCheck')
    expect(shortcutFor({ key: 'x' })).toBeNull()
  })

  it('ignores typing in fields and modifier combos', () => {
    expect(shortcutFor({ key: 'a', target: { tagName: 'TEXTAREA' } })).toBeNull()
    expect(shortcutFor({ key: 'a', target: { tagName: 'input' } })).toBeNull()
    expect(shortcutFor({ key: 'a', target: { tagName: 'DIV', isContentEditable: true } })).toBeNull()
    expect(shortcutFor({ key: 'r', ctrlKey: true })).toBeNull()
    expect(shortcutFor({ key: 'a', target: { tagName: 'BUTTON' } })).toBe('approve')
  })

  it('ticks checklist items with 1-9', () => {
    expect(checklistKey({ key: '1' }, 4)).toBe(0)
    expect(checklistKey({ key: '4' }, 4)).toBe(3)
    expect(checklistKey({ key: '5' }, 4)).toBeNull()
    expect(checklistKey({ key: '0' }, 4)).toBeNull()
    expect(checklistKey({ key: '1', target: { tagName: 'INPUT' } }, 4)).toBeNull()
  })

  it('finds the next check in the queue', () => {
    expect(nextInQueue(['a', 'b', 'c'], 'a')).toBe('b')
    expect(nextInQueue(['a', 'b', 'c'], 'c')).toBe('a')
    expect(nextInQueue(['a', 'b'], 'x')).toBe('a')
    expect(nextInQueue(['a'], 'a')).toBeNull()
    expect(nextInQueue([], 'a')).toBeNull()
  })

  it('zooms and rotates within bounds', () => {
    expect(zoomBy(1, 1)).toBe(1.25)
    expect(zoomBy(1, -1)).toBe(0.8)
    expect(zoomBy(ZOOM_MAX, 1)).toBe(ZOOM_MAX)
    expect(zoomBy(ZOOM_MIN, -1)).toBe(ZOOM_MIN)
    expect(rotateBy(0)).toBe(90)
    expect(rotateBy(270)).toBe(0)
    expect(rotateBy(0, -90)).toBe(270)
  })
})

describe('verification settings', () => {
  it('accepts the defaults and sends only what changed', () => {
    const form = defaultSettings()
    expect(validateSettings(form)).toEqual([])
    expect(form.driver_required_documents).not.toContain('criminal_record')
    const original = settingsToPayload(form)
    form.verification.expiry_notice_days = [1, 30, 7, 7]
    form.verification.expiring_documents = ['vehicle_registration', 'drivers_license']
    const payload = settingsToPayload(form)
    expect(payload.verification.expiry_notice_days).toEqual([30, 7, 1])
    expect(payload.verification.expiring_documents).toEqual(['drivers_license', 'vehicle_registration'])
    form.verification.selfie_every_days = 0
    expect(changedSettings(settingsToPayload(form), original)).toEqual({ verification: { ...settingsToPayload(form).verification } })
  })

  it('validates the numbers and notice days', () => {
    const form = defaultSettings()
    form.verification.selfie_every_days = 91
    form.verification.expiry_notice_days = [200]
    expect(validateSettings(form).map(i => i.key)).toEqual(['noticeDays', 'verificationNumber'])
  })

  it('reads an older API without the verification block', () => {
    const config = settingsToPayload(defaultSettings()) as unknown as Record<string, unknown>
    delete config.verification
    expect(settingsFromConfig(config as never).verification).toEqual(DEFAULT_VERIFICATION)
  })

  it('parses the notice days', () => {
    expect(parseNoticeDays('30, 7, 1')).toEqual([30, 7, 1])
    expect(parseNoticeDays('')).toEqual([])
    expect(parseNoticeDays('30, siete')).toBeNull()
  })
})
