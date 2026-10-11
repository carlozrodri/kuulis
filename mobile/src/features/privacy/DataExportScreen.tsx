import { useQuery, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { ChevronLeft, Download } from '@/components/icons';
import { Button, ErrorText, IconButton, IconTile, Notice, Row, Screen, Txt } from '@/components/ui';
import { apiErrorMessage } from '@/i18n';
import { api } from '@/lib/api';
import type { DataExport } from '@/lib/types';
import { useAuth } from '@/providers/AuthProvider';
import { space } from '@/theme';

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));
const KEY = ['privacy', 'export'];

type ExportState = { last: DataExport | null; waitUntil: Date | null };

/** Read at fetch time: the screen refetches on every visit, so the button unlocks on the next one. */
function withWait(last: DataExport | null): ExportState {
  const next = last?.next_at ? new Date(last.next_at) : null;
  return { last, waitUntil: next && next.getTime() > Date.now() ? next : null };
}

/** Perfil → Seguridad → Descargar mis datos: a JSON copy of everything Kuulis keeps, sent by email (once a day). */
export function DataExportScreen() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: KEY,
    queryFn: async () => withWait(await api<DataExport | null>('/users/me/export')),
  });
  const last = data?.last;
  const waitUntil = data?.waitUntil ?? null;
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  const time = (iso: Date) =>
    iso.toLocaleString(i18n.language, { weekday: 'short', hour: '2-digit', minute: '2-digit' });

  async function request() {
    setSaving(true);
    setError(undefined);
    try {
      const created = await api<DataExport>('/users/me/export', { method: 'POST' });
      queryClient.setQueryData(KEY, withWait(created));
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
        </Row>
      }
      footer={
        <View style={{ gap: space.xs }}>
          <ErrorText>{error}</ErrorText>
          <Button
            title={t('privacy.export.button')}
            icon={Download}
            loading={saving}
            disabled={!!waitUntil}
            onPress={() => void request()}
          />
        </View>
      }>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={Download} tone="primary" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('privacy.export.title')}
        </Txt>
        <Txt color="muted">{t('privacy.export.body')}</Txt>
      </View>
      {last?.status === 'ready' || last?.status === 'pending' ? (
        <Notice tone="success" title={t('privacy.export.sentTitle')}>
          {t('privacy.export.sentBody', { email: user?.email ?? '' })}
        </Notice>
      ) : last?.status === 'failed' ? (
        <Notice tone="danger">{t('privacy.export.failed')}</Notice>
      ) : null}
      {waitUntil ? (
        <Txt variant="caption" color="muted" style={{ marginTop: space.md }}>
          {t('privacy.export.next', { time: time(waitUntil) })}
        </Txt>
      ) : null}
    </Screen>
  );
}
