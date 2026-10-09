import { getLocales } from 'expo-localization';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import { setApiLocale } from '@/lib/api';
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

export default i18n;
