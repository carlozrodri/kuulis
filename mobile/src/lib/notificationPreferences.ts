/** Doc 14: Perfil → Ajustes → Notificaciones. Only marketing can be turned off; quiet hours only hold it back. */
import type { NotificationPreferences, NotificationPreferencesUpdate } from './types';

/** Every half hour of the day, "00:00" … "23:30". */
export const QUIET_TIME_OPTIONS: readonly string[] = Array.from(
  { length: 48 },
  (_, i) => `${String(Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`,
);

/** "21:00:00" or "9:00" → "21:00" / "09:00"; null when it is not a time. */
export function normalizeClock(value: string | null | undefined): string | null {
  const match = /^(\d{1,2}):(\d{2})/.exec(value ?? '');
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 23 || minutes > 59) return null;
  return `${String(hours).padStart(2, '0')}:${match[2]}`;
}

/** The user kept the default window (or never changed it). */
export const usesDefaultQuiet = (prefs: NotificationPreferences) =>
  normalizeClock(prefs.quiet_start) === normalizeClock(prefs.default_quiet_start) &&
  normalizeClock(prefs.quiet_end) === normalizeClock(prefs.default_quiet_end);

/** Same start and end: no quiet hours. */
export const quietOff = (start: string, end: string) => normalizeClock(start) === normalizeClock(end);

/** The optimistic copy shown while a change is saved. */
export const withUpdate = (prefs: NotificationPreferences, update: NotificationPreferencesUpdate): NotificationPreferences => ({
  ...prefs,
  ...update,
});

/** "Usar el horario recomendado": the update that puts the default window back. */
export const defaultQuietUpdate = (prefs: NotificationPreferences): NotificationPreferencesUpdate => ({
  quiet_start: normalizeClock(prefs.default_quiet_start) ?? prefs.default_quiet_start,
  quiet_end: normalizeClock(prefs.default_quiet_end) ?? prefs.default_quiet_end,
});
