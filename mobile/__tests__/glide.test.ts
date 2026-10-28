import { describe, expect, it } from '@jest/globals';

import { bearing, distanceM, lerpAngle, lerpCoordinate, MIN_TURN_M, nextRotation } from '@/components/map/glide';

const A = { latitude: 10.49, longitude: -66.88 };

describe('live moto math (doc 01-A)', () => {
  it('points north, east, south and west', () => {
    expect(bearing(A, { ...A, latitude: 10.5 })).toBeCloseTo(0, 0);
    expect(bearing(A, { ...A, longitude: -66.87 })).toBeCloseTo(90, 0);
    expect(bearing(A, { ...A, latitude: 10.48 })).toBeCloseTo(180, 0);
    expect(bearing(A, { ...A, longitude: -66.89 })).toBeCloseTo(270, 0);
  });

  it('turns the short way round', () => {
    expect(lerpAngle(350, 10, 0.5)).toBeCloseTo(0, 5);
    expect(lerpAngle(10, 350, 0.5)).toBeCloseTo(0, 5);
    expect(lerpAngle(90, 180, 0.5)).toBeCloseTo(135, 5);
  });

  it('glides in a straight line', () => {
    const B = { latitude: 10.5, longitude: -66.86 };
    expect(lerpCoordinate(A, B, 0)).toEqual(A);
    expect(lerpCoordinate(A, B, 1)).toEqual(B);
    expect(lerpCoordinate(A, B, 0.5).latitude).toBeCloseTo(10.495, 6);
  });

  it('uses the GPS heading, then the travel direction, and ignores jitter', () => {
    const north = { ...A, latitude: A.latitude + 0.001 }; // ~110 m
    expect(nextRotation(A, north, 45, 0)).toBe(45);
    expect(nextRotation(A, north, null, 200)).toBeCloseTo(0, 0);
    const jitter = { ...A, latitude: A.latitude + 0.00002 }; // ~2 m
    expect(distanceM(A, jitter)).toBeLessThan(MIN_TURN_M);
    expect(nextRotation(A, jitter, undefined, 123)).toBe(123);
  });
});
