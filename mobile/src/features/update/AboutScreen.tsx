import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { ChevronLeft, Hash, Info, RotateCcw, Smartphone, Sparkles } from '@/components/icons';
import { Button, Card, ErrorText, IconButton, IconTile, ListRow, Notice, Row, Screen, Txt, Wordmark } from '@/components/ui';
import { useAppUpdate } from '@/hooks/useAppUpdate';
import { useJsUpdate } from '@/hooks/useJsUpdate';
import i18n, { apiErrorMessage } from '@/i18n';
import { appVersion, formatMegabytes } from '@/lib/appVersion';
import { space } from '@/theme';

import { RestartControls } from './RestartControls';
import { InstallControls } from './UpdateControls';

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

const KNOWN_CHANNELS = ['qa', 'beta', 'production'];

/** Perfil → Acerca de: which build and JS update this is, and "Buscar actualizaciones" (doc 09). */
export function AboutScreen() {
  const { t } = useTranslation();
  const update = useAppUpdate();
  const js = useJsUpdate();
  const [checking, setChecking] = useState(false);
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<string>();
  const [jsReady, setJsReady] = useState(false);

  async function check() {
    setChecking(true);
    setError(undefined);
    let failed: string | undefined;
    if (update.enabled) {
      const result = await update.query.refetch().catch((e: unknown) => ({ error: e }));
      if (result.error) failed = apiErrorMessage(result.error);
    }
    if (js.enabled) {
      const outcome = await js.check();
      if (outcome === 'ready') setJsReady(true);
      if (outcome === 'error' && !failed) failed = t('about.jsError');
    }
    setError(failed);
    setChecked(true);
    setChecking(false);
  }

  const latest = update.latest;
  const supported = update.enabled || js.enabled;
  const ready = js.enabled && (js.pending || jsReady);
  const channel = (js.enabled && js.running.channel) || appVersion.channel;
  const runningUpdate = js.running.embedded
    ? t('about.embedded')
    : js.running.createdAt
      ? t('about.running', {
          id: js.running.shortId,
          date: js.running.createdAt.toLocaleString(i18n.language, {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          }),
        })
      : js.running.shortId;
  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
        </Row>
      }>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={Info} tone="primary" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('about.title')}
        </Txt>
        <Wordmark size={28} />
      </View>

      <Card style={{ paddingVertical: space.xxs }}>
        <ListRow icon={Smartphone} iconTone="neutral" title={t('about.version')} subtitle={appVersion.version || 'dev'} divider />
        <ListRow icon={Hash} iconTone="neutral" title={t('about.build')} subtitle={appVersion.build ? String(appVersion.build) : '—'} divider />
        {js.enabled ? (
          <ListRow icon={Sparkles} iconTone="neutral" title={t('about.update')} subtitle={runningUpdate} divider />
        ) : null}
        <ListRow
          icon={RotateCcw}
          iconTone="neutral"
          title={t('about.channel')}
          subtitle={KNOWN_CHANNELS.includes(channel) ? t(`about.channels.${channel}`) : channel}
        />
      </Card>

      <View style={{ marginTop: space.xl, gap: space.md }}>
        {!supported ? (
          <Notice tone="info">{t('about.unsupported')}</Notice>
        ) : update.available && latest ? (
          <Notice tone={update.required ? 'warning' : 'info'} title={t('about.available', { version: latest.version })}>
            <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
              {latest.notes || t('about.availableBody', { size: formatMegabytes(latest.size) })}
            </Txt>
          </Notice>
        ) : ready ? (
          <Notice tone="success">{t('about.jsReady')}</Notice>
        ) : checked && !error ? (
          <Notice tone="success">{t('about.upToDate')}</Notice>
        ) : null}
        <ErrorText>{error}</ErrorText>
        {ready && !(update.enabled && update.available && latest) ? <RestartControls /> : null}
        {update.enabled && update.available && latest ? (
          <InstallControls />
        ) : (
          <Button
            title={t('about.check')}
            variant="secondary"
            icon={RotateCcw}
            loading={checking}
            disabled={!supported}
            onPress={() => void check()}
          />
        )}
      </View>
    </Screen>
  );
}
