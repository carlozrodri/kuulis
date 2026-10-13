import { getLocales } from 'expo-localization';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import { ApiError, setApiLocale } from '@/lib/api';
import { formatEta, localize, type Notice, parseNotice } from '@/lib/bootstrap';
import { pauseFromError } from '@/lib/quality';
import { suspensionEnd } from '@/lib/suspension';
import en from './locales/en.json';
import es from './locales/es.json';

export const SUPPORTED_LOCALES = ['es', 'en'] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

function deviceLocale(): Locale {
  const code = getLocales()[0]?.languageCode;
  return code === 'en' ? 'en' : 'es';
}

i18n.use(initReactI18next).init({
  resources: { es: { translation: es }, en: { translation: en } },
  lng: deviceLocale(),
  fallbackLng: 'es',
  interpolation: { escapeValue: false },
});

setApiLocale(i18n.language);
i18n.on('languageChanged', setApiLocale);

/** Maps an API error code to a translated message. */
export function errorMessage(code: string | undefined): string {
  if (code && i18n.exists(`errors.${code}`)) return i18n.t(`errors.${code}`);
  return i18n.t('common.error');
}

/**
 * Why rides are stopped, in the app language (English falls back to Spanish), with the estimated time back
 * in local time: "Pausamos los pedidos por lluvia fuerte. Volvemos hacia las 16:30."
 */
export function noticeText(notice: Notice, language: string = i18n.language): string {
  const message =
    localize(notice.message, language) ||
    i18n.t(notice.kind === 'maintenance' ? 'control.maintenance.defaultBody' : 'control.pause.defaultBody');
  const eta = formatEta(notice.eta, language);
  return eta ? `${message} ${i18n.t('control.etaSentence', { time: eta })}` : message;
}

/** When a quality pause ends (doc 15): "hasta las 3:45 p. m." today, else "hasta el 15 de octubre a las 3:45 p. m.". */
export function pauseUntilText(until: string, language: string = i18n.language, now: Date = new Date()): string {
  const end = suspensionEnd({ until }, now);
  if (end.kind === 'indefinite') return '';
  const time = end.date.toLocaleTimeString(language, { hour: 'numeric', minute: '2-digit' });
  if (end.sameDay) return i18n.t('quality.pause.untilToday', { time });
  const date = end.date.toLocaleDateString(language, { day: 'numeric', month: 'long' });
  return i18n.t('quality.pause.untilDate', { date, time });
}

/**
 * Human message for any error thrown by `api()`. The API does not localize messages, so we translate by
 * error code (with `details` such as {min_year} as interpolation values), falling back to its message.
 */
export function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'service_paused') {
      const notice = parseNotice(error.details);
      if (notice) return noticeText(notice);
    }
    if (error.code === 'temporarily_paused') {
      const pause = pauseFromError(error);
      return pause ? i18n.t('errors.temporarily_paused', { until: pauseUntilText(pause.until) }) : i18n.t('quality.pause.generic');
    }
    if (i18n.exists(`errors.${error.code}`)) {
      const values = error.details && typeof error.details === 'object' && !Array.isArray(error.details) ? error.details : {};
      return i18n.t(`errors.${error.code}`, values as Record<string, unknown>);
    }
    if (error.status >= 500) return i18n.t('errors.server');
    if (error.message && !error.code.startsWith('http_')) return error.message;
    return i18n.t('common.error');
  }
  return i18n.t('errors.network');
}

/** Field errors from a 422 `validation_error` envelope: details = [{loc: ["body", "plate"], msg}]. */
export function apiFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || !Array.isArray(error.details)) return {};
  const fields: Record<string, string> = {};
  for (const item of error.details as { loc?: unknown[]; msg?: string }[]) {
    const field = item?.loc?.[item.loc.length - 1];
    if (typeof field === 'string') fields[field] = i18n.t('validation.invalid');
  }
  return fields;
}

/**
 * Splits an API error for a form: codes listed in `codeToField` (e.g. plate_taken → plate) and 422 details
 * become field errors; anything else becomes the form-level message.
 */
export function apiFormErrors<F extends string>(
  error: unknown,
  codeToField: Partial<Record<string, F>> = {},
): { fields: Partial<Record<F, string>>; message?: string } {
  const fields = apiFieldErrors(error) as Partial<Record<F, string>>;
  const field = error instanceof ApiError ? codeToField[error.code] : undefined;
  if (field) return { fields: { ...fields, [field]: apiErrorMessage(error) } };
  return { fields, message: apiErrorMessage(error) };
}

export default i18n;
