import { describe, expect, it } from '@jest/globals';

import { ApiError } from '@/lib/api';
import {
  activePause,
  cancelRateTone,
  formatCountdown,
  formatPercent,
  isTemporarilyPaused,
  LEVEL_TONE,
  meterPosition,
  parseQualityPaused,
  pauseFromError,
  pauseFromQuality,
  pauseRules,
} from '@/lib/quality';

const NOW = Date.parse('2026-10-13T15:00:00Z');
const UNTIL = '2026-10-13T15:12:34Z';

const thresholds = {
  window_days: 30,
  min_rides: 10,
  cancel_warn: 0.15,
  cancel_low_priority: 0.25,
  cancel_review: 0.35,
  rating_review_below: 4.3,
  rating_min_count: 20,
  cancel_burst: 3,
  decline_streak: 5,
  pause_minutes: 15,
  pickup_wait_minutes: 5,
};

describe('pause errors', () => {
  it('reads a 403 temporarily_paused', () => {
    const error = new ApiError(403, 'temporarily_paused', '', { until: UNTIL, reason: 'cancel_burst' });
    expect(isTemporarilyPaused(error)).toBe(true);
    expect(pauseFromError(error)).toEqual({ until: UNTIL, reason: 'cancel_burst' });
  });

  it('keeps the pause with an unknown reason and ignores other errors', () => {
    expect(pauseFromError(new ApiError(403, 'temporarily_paused', '', { until: UNTIL, reason: 'new_rule' }))).toEqual({
      until: UNTIL,
      reason: null,
    });
    expect(pauseFromError(new ApiError(403, 'temporarily_paused', '', {}))).toBeNull();
    expect(pauseFromError(new ApiError(403, 'account_suspended', '', { until: UNTIL }))).toBeNull();
    expect(pauseFromError(new Error('network'))).toBeNull();
    expect(isTemporarilyPaused(null)).toBe(false);
  });
});

describe('parseQualityPaused', () => {
  it('reads a pause and a lifted one', () => {
    expect(parseQualityPaused({ role: 'driver', reason: 'decline_streak', until: UNTIL })).toEqual({
      role: 'driver',
      reason: 'decline_streak',
      until: UNTIL,
    });
    expect(parseQualityPaused({ role: 'passenger', reason: 'no_shows', until: null })).toEqual({
      role: 'passenger',
      reason: 'no_shows',
      until: null,
    });
  });

  it('rejects malformed events', () => {
    expect(parseQualityPaused(null)).toBeNull();
    expect(parseQualityPaused({ role: 'admin', until: UNTIL })).toBeNull();
    expect(parseQualityPaused({ role: 'driver', until: 'soon' })).toBeNull();
  });
});

describe('activePause', () => {
  it('keeps a pause until it ends', () => {
    const pause = { until: UNTIL, reason: null };
    expect(activePause(pause, NOW)).toBe(pause);
    expect(activePause(pause, Date.parse(UNTIL))).toBeNull();
    expect(activePause(null, NOW)).toBeNull();
  });

  it('builds the pause the quality panel reports', () => {
    expect(pauseFromQuality({ paused_until: UNTIL, pause_reason: 'cancel_burst' })).toEqual({ until: UNTIL, reason: 'cancel_burst' });
    expect(pauseFromQuality({ paused_until: null, pause_reason: null })).toBeNull();
    expect(pauseFromQuality(undefined)).toBeNull();
  });
});

describe('formatting', () => {
  it('formats the countdown', () => {
    expect(formatCountdown(754)).toBe('12:34');
    expect(formatCountdown(59.9)).toBe('0:59');
    expect(formatCountdown(3725)).toBe('1:02:05');
    expect(formatCountdown(-5)).toBe('0:00');
    expect(formatCountdown(Number.NaN)).toBe('0:00');
  });

  it('formats rates as percentages', () => {
    expect(formatPercent(0.153)).toBe('15%');
    expect(formatPercent(1)).toBe('100%');
    expect(formatPercent(0)).toBe('0%');
    expect(formatPercent(null)).toBe('—');
  });
});

describe('levels and thresholds', () => {
  it('maps levels to tones', () => {
    expect(LEVEL_TONE.ok).toBe('success');
    expect(LEVEL_TONE.warn).toBe('warning');
    expect(LEVEL_TONE.low_priority).toBe('danger');
  });

  it('colors the cancellation rate like the server levels', () => {
    expect(cancelRateTone({ cancel_rate: 0.05, accepted: 20 }, thresholds)).toBe('success');
    expect(cancelRateTone({ cancel_rate: 0.15, accepted: 20 }, thresholds)).toBe('warning');
    expect(cancelRateTone({ cancel_rate: 0.3, accepted: 20 }, thresholds)).toBe('danger');
    // Not enough rides yet, or nothing to measure.
    expect(cancelRateTone({ cancel_rate: 0.5, accepted: 4 }, thresholds)).toBe('neutral');
    expect(cancelRateTone({ cancel_rate: null, accepted: 20 }, thresholds)).toBe('neutral');
  });

  it('says which disconnection rules are on', () => {
    expect(pauseRules(thresholds)).toEqual({ key: 'both', declines: 5, cancels: 3 });
    expect(pauseRules({ cancel_burst: 0, decline_streak: 5 }).key).toBe('declines');
    expect(pauseRules({ cancel_burst: 3, decline_streak: 0 }).key).toBe('cancels');
    expect(pauseRules({ cancel_burst: 0, decline_streak: 0 })).toEqual({ key: 'none', declines: null, cancels: null });
  });

  it('places a rate on the meter', () => {
    expect(meterPosition(0, thresholds)).toBe(0);
    expect(meterPosition(0.35, thresholds)).toBeCloseTo(0.8);
    expect(meterPosition(0.9, thresholds)).toBe(1);
    expect(meterPosition(null, thresholds)).toBe(0);
  });
});
