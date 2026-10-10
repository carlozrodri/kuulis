/**
 * Pure profile logic (no React, no network) so it can be unit tested.
 */
import type { User } from './types';

/** "Ana María Pérez" -> "AM"; falls back to the email, then "?". */
export function initials(name: string | null | undefined, email?: string | null): string {
  const source = name?.trim() || email?.trim() || '';
  const parts = source.split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || '?';
}

/** First name for greetings ("Ana María Pérez" -> "Ana"). */
export const firstName = (name: string | null | undefined) => name?.trim().split(/\s+/)[0] ?? '';

/** "2026-10-09T…" -> "oct 2026" / "Oct 2026". */
export function memberSince(iso: string | null | undefined, locale = 'es'): string {
  const date = iso ? new Date(iso) : null;
  if (!date || !Number.isFinite(date.getTime())) return '';
  return date.toLocaleDateString(locale, { month: 'short', year: 'numeric' }).replace('.', '');
}

/** Whole kilometres for the stats strip: 9400 -> "9", 125300 -> "125", 1_250_000 -> "1.250" (es). */
export function formatKm(metres: number | null | undefined, locale = 'es'): string {
  const km = Math.round((metres ?? 0) / 1000);
  return Math.max(0, km).toLocaleString(locale);
}

/** Rating to show next to the name: one decimal, or null with no ratings yet. */
export function ratingValue(rating: number | string | null | undefined): number | null {
  const value = typeof rating === 'number' ? rating : Number.parseFloat(rating ?? '');
  return Number.isFinite(value) && value > 0 ? Math.round(value * 10) / 10 : null;
}

export type ProfileStep = 'photo' | 'name' | 'email';

/** What is still missing for a complete profile, in the order it is shown. */
export function missingProfileSteps(user: Pick<User, 'avatar_key' | 'full_name' | 'is_verified'> | null): ProfileStep[] {
  if (!user) return [];
  const steps: ProfileStep[] = [];
  if (!user.avatar_key) steps.push('photo');
  if (user.full_name.trim().split(/\s+/).filter(Boolean).length < 2) steps.push('name');
  if (!user.is_verified) steps.push('email');
  return steps;
}

export const PROFILE_STEPS_TOTAL = 3;
