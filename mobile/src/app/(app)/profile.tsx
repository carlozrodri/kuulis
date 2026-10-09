import * as Application from 'expo-application';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { Body, Button, Screen, Title } from '@/components/ui';
import { SUPPORTED_LOCALES, type Locale } from '@/i18n';
import { api } from '@/lib/api';
import { config } from '@/lib/config';
import { useAuth } from '@/providers/AuthProvider';

const LABELS: Record<Locale, string> = { es: 'Español', en: 'English' };

export default function ProfileScreen() {
  const { t, i18n } = useTranslation();
  const { user, signOut, refreshUser } = useAuth();

  async function changeLanguage(locale: Locale) {
    await i18n.changeLanguage(locale);
    await api('/users/me', { method: 'PATCH', body: { locale } });
    await refreshUser();
  }

  return (
    <Screen>
      <Title>{t('tabs.profile')}</Title>
      <Body>{user?.full_name}</Body>
      <Body muted>{user?.email}</Body>

      <View style={{ marginTop: 24 }}>
        <Body muted>{t('profile.language')}</Body>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {SUPPORTED_LOCALES.map((locale) => (
            <Button
              key={locale}
              title={LABELS[locale]}
              variant={i18n.language === locale ? 'primary' : 'ghost'}
              onPress={() => changeLanguage(locale)}
            />
          ))}
        </View>
      </View>

      <View style={{ marginTop: 24 }}>
        <Body muted>
          {t('profile.environment')}: {config.appEnv} · {t('profile.version')}: {Application.nativeApplicationVersion ?? 'dev'}
        </Body>
      </View>

      <Button title={t('auth.logout')} variant="ghost" onPress={signOut} />
    </Screen>
  );
}
