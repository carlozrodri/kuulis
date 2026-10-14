/**
 * Doc 15: cancellations and quality. Temporary pauses (too many cancellations or declined offers, passengers who
 * do not show up), the driver's rates and the rules behind them. Pure helpers, unit tested.
 */
import { ApiError } from './api';
import type {
  DriverQuality,
  PauseReason,
  QualityLevel,
  QualityPause,
  QualityPausedEvent,
  QualityThresholds,
} from './types';

const PAUSE_REASONS: readonly PauseReason[] = ['cancel_burst', 'decline_streak', 'no_shows'];

const pauseReason = (value: unknown): PauseReason | null =>
  PAUSE_REASONS.includes(value as PauseReason) ? (value as PauseReason) : null;

const validIso = (value: unknown): value is string => typeof value === 'string' && !Number.isNaN(Date.parse(value));

/** 403 temporarily_paused from going online (driver), the quote or the ride request (passenger). */
export const isTemporarilyPaused = (error: unknown): error is ApiError =>
  error instanceof ApiError && error.code === 'temporarily_paused';

/** The pause a 403 temporarily_paused describes, or null for any other error. */
export function pauseFromError(error: unknown): QualityPause | null {
  if (!isTemporarilyPaused(error)) return null;
  const details = (error.details ?? {}) as Record<string, unknown>;
  if (!validIso(details.until)) return null;
  return { until: details.until, reason: pauseReason(details.reason) };
}

/** WS `quality.paused`, checked: `until` null means the pause was lifted. */
export function parseQualityPaused(data: unknown): QualityPausedEvent | null {
  if (!data || typeof data !== 'object') return null;
  const record = data as Record<string, unknown>;
  if (record.role !== 'driver' && record.role !== 'passenger') return null;
  const until = validIso(record.until) ? record.until : null;
  if (record.until != null && until === null) return null;
  return { role: record.role, reason: pauseReason(record.reason), until };
}

/** The pause still in force at `now`, or null (a pause ends by itself). */
export function activePause(pause: QualityPause | null | undefined, now: number = Date.now()): QualityPause | null {
  if (!pause) return null;
  const until = Date.parse(pause.until);
  return Number.isNaN(until) || until <= now ? null : pause;
}

/** The pause the driver's quality panel reports, if any. */
export function pauseFromQuality(quality: Pick<DriverQuality, 'paused_until' | 'pause_reason'> | null | undefined) {
  return quality?.paused_until ? { until: quality.paused_until, reason: pauseReason(quality.pause_reason) } : null;
}

/** 754 -> "12:34", 3_725 -> "1:02:05". For the pause countdown. */
export function formatCountdown(seconds: number): string {
  const total = Math.max(0, Math.floor(Number.isFinite(seconds) ? seconds : 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = String(total % 60).padStart(2, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`;
}

/** 0.153 -> "15%"; null (nothing to measure yet) -> "—". */
export function formatPercent(rate: number | null | undefined): string {
  if (rate == null || !Number.isFinite(rate)) return '—';
  return `${Math.round(rate * 100)}%`;
}

export type QualityTone = 'success' | 'warning' | 'danger' | 'neutral';

export const LEVEL_TONE: Record<QualityLevel, QualityTone> = {
  ok: 'success',
  warn: 'warning',
  low_priority: 'danger',
  review: 'danger',
};

/** How the cancellation rate looks against the thresholds (neutral until there are enough rides to measure). */
export function cancelRateTone(
  quality: Pick<DriverQuality, 'cancel_rate' | 'accepted'>,
  thresholds: Pick<QualityThresholds, 'cancel_warn' | 'cancel_low_priority' | 'min_rides'>,
): QualityTone {
  const rate = quality.cancel_rate;
  if (rate == null || quality.accepted < thresholds.min_rides) return 'neutral';
  if (rate >= thresholds.cancel_low_priority) return 'danger';
  if (rate >= thresholds.cancel_warn) return 'warning';
  return 'success';
}

/** The automatic disconnection rules in force (a threshold of 0 switches that rule off). */
export function pauseRules(thresholds: Pick<QualityThresholds, 'cancel_burst' | 'decline_streak'>) {
  const declines = thresholds.decline_streak > 0 ? thresholds.decline_streak : null;
  const cancels = thresholds.cancel_burst > 0 ? thresholds.cancel_burst : null;
  const key = declines && cancels ? 'both' : declines ? 'declines' : cancels ? 'cancels' : 'none';
  return { key, declines, cancels } as const;
}

/** Position (0..1) of a rate on the cancellation meter, which ends a bit past the review threshold. */
export function meterPosition(rate: number | null | undefined, thresholds: Pick<QualityThresholds, 'cancel_review'>): number {
  const end = Math.max(thresholds.cancel_review * 1.25, 0.05);
  if (rate == null || !Number.isFinite(rate)) return 0;
  return Math.min(1, Math.max(0, rate / end));
}
