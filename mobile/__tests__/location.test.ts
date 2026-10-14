import { describe, expect, it } from '@jest/globals';

import { modelHeader } from '@/lib/deviceId';
import { isMockedLocation, isMockLocationError, mockLocationTookOffline, positionBody } from '@/lib/location';

describe('mocked flag (doc 16)', () => {
  it('counts only an explicit mocked: true as simulated', () => {
    expect(isMockedLocation({ mocked: true })).toBe(true);
    expect(isMockedLocation({ mocked: false })).toBe(false);
    expect(isMockedLocation({})).toBe(false);
    expect(isMockedLocation({ mocked: null })).toBe(false);
    expect(isMockedLocation(null)).toBe(false);
    expect(isMockedLocation(undefined)).toBe(false);
  });

  it('builds the position body with mocked always present', () => {
    expect(positionBody({ lat: 10.5, lng: -66.9 })).toEqual({ lat: 10.5, lng: -66.9, mocked: false });
    expect(positionBody({ lat: 10.5, lng: -66.9, mocked: true })).toEqual({ lat: 10.5, lng: -66.9, mocked: true });
    expect(positionBody({ lat: 1, lng: 2, heading: 89.6, speed: 4.26, mocked: false })).toEqual({
      lat: 1,
      lng: 2,
      heading: 90,
      speed: 4.3,
      mocked: false,
    });
  });

  it('leaves out unknown or negative heading and speed', () => {
    expect(positionBody({ lat: 1, lng: 2, heading: -1, speed: -1 })).toEqual({ lat: 1, lng: 2, mocked: false });
    expect(positionBody({ lat: 1, lng: 2, heading: null, speed: null })).toEqual({ lat: 1, lng: 2, mocked: false });
    expect(positionBody({ lat: 1, lng: 2, heading: 0, speed: 0 })).toEqual({ lat: 1, lng: 2, heading: 0, speed: 0, mocked: false });
  });

  it('reads driver.mock_location: only online false means taken offline', () => {
    expect(mockLocationTookOffline({ online: false })).toBe(true);
    expect(mockLocationTookOffline({ online: null })).toBe(false);
    expect(mockLocationTookOffline({})).toBe(false);
    expect(mockLocationTookOffline(null)).toBe(false);
    expect(mockLocationTookOffline('x')).toBe(false);
  });

  it('spots the 409 mock_location error', () => {
    expect(isMockLocationError({ status: 409, code: 'mock_location' })).toBe(true);
    expect(isMockLocationError({ code: 'document_expired' })).toBe(false);
    expect(isMockLocationError(new Error('x'))).toBe(false);
    expect(isMockLocationError(null)).toBe(false);
  });
});

describe('X-Device-Model header', () => {
  it('sends the trimmed model name, up to 80 characters', () => {
    expect(modelHeader('Pixel 7')).toEqual({ 'X-Device-Model': 'Pixel 7' });
    expect(modelHeader('  SM-A515F  ')).toEqual({ 'X-Device-Model': 'SM-A515F' });
    expect(modelHeader('x'.repeat(100))['X-Device-Model']).toHaveLength(80);
  });

  it('leaves the header out when the model is unknown', () => {
    expect(modelHeader(null)).toEqual({});
    expect(modelHeader(undefined)).toEqual({});
    expect(modelHeader('   ')).toEqual({});
  });
});
