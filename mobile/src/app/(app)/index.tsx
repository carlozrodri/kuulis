import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { Body, Button, Screen, Title } from '@/components/ui';
import { useRealtime } from '@/hooks/useRealtime';
import { api } from '@/lib/api';
import { useAuth } from '@/providers/AuthProvider';

export default function HomeScreen() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const realtime = useRealtime(!!user);
  const [sent, setSent] = useState(false);

  return (
    <Screen>
      <Title>{t('home.greeting', { name: user?.full_name || user?.email })}</Title>
      {!user?.is_verified && (
        <View style={{ marginBottom: 16 }}>
          <Body muted>{t('home.verifyEmail')}</Body>
          {!sent && (
            <Button
              title={t('home.resend')}
              variant="ghost"
              onPress={() => api('/auth/verify-email/resend', { method: 'POST' }).then(() => setSent(true))}
            />
          )}
        </View>
      )}
      <Body muted>{t('home.realtime', { status: realtime })}</Body>
    </Screen>
  );
}
