import { useQuery, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, View } from 'react-native';

import { ErrorState } from '@/components/ErrorState';
import { ChevronLeft, MonitorSmartphone, Smartphone } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Card, IconButton, IconTile, ListRow, Row, Screen, Txt } from '@/components/ui';
import { apiErrorMessage } from '@/i18n';
import { api } from '@/lib/api';
import { space } from '@/theme';

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

export type SessionInfo = {
  id: string;
  current: boolean;
  device: string | null;
  platform: string | null;
  ip: string | null;
  created_at: string;
  last_used_at: string;
  admin: boolean;
};

const SESSIONS_KEY = ['auth', 'sessions'];

function lastUsed(iso: string, locale: string): string {
  return new Date(iso).toLocaleString(locale, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

/** Profile → Security → Active sessions: every signed-in device, each with its own "Sign out". */
export function SessionsScreen() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: SESSIONS_KEY, queryFn: () => api<SessionInfo[]>('/auth/sessions') });
  const [closing, setClosing] = useState<string | null>(null);

  async function close(session: SessionInfo) {
    setClosing(session.id);
    try {
      await api(`/auth/sessions/${session.id}`, { method: 'DELETE' });
      await queryClient.invalidateQueries({ queryKey: SESSIONS_KEY });
      showToast(t('profile.sessions.closed'), 'success');
    } catch (err) {
      showToast(apiErrorMessage(err), 'danger');
    } finally {
      setClosing(null);
    }
  }

  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
        </Row>
      }>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={MonitorSmartphone} tone="neutral" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('profile.sessions.title')}
        </Txt>
        <Txt color="muted">{t('profile.sessions.subtitle')}</Txt>
      </View>
      {isLoading ? <ActivityIndicator /> : null}
      {error && !data ? <ErrorState inline error={error} onRetry={() => refetch()} /> : null}
      {data ? (
        <Card style={{ paddingVertical: space.xxs }}>
          {data.map((session, index) => (
            <ListRow
              key={session.id}
              icon={session.platform === 'android' || session.platform === 'ios' ? Smartphone : MonitorSmartphone}
              iconTone={session.current ? 'primary' : 'neutral'}
              title={session.device ?? t('profile.sessions.unknownDevice')}
              subtitle={
                session.current
                  ? t('profile.sessions.thisDevice')
                  : t('profile.sessions.lastUsed', { time: lastUsed(session.last_used_at, i18n.language) })
              }
              divider={index < data.length - 1}
              right={
                session.current ? null : (
                  <Button
                    title={t('profile.sessions.close')}
                    variant="ghost"
                    loading={closing === session.id}
                    onPress={() => void close(session)}
                  />
                )
              }
            />
          ))}
        </Card>
      ) : null}
    </Screen>
  );
}
